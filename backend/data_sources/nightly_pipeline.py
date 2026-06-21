"""
Nightly incremental pipeline — runs at midnight to update 1d/1wk/1mo data.
Minute/hour data is NOT fetched here; it's loaded on-demand when users request it.
"""

import time
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from data_sources.indicator_calculator import IndicatorCalculator
from data_sources.data_source_manager import DataSourceManager


class NightlyPipeline:

    BULK_CHUNK_SIZE = 500
    COMPUTE_CONCURRENCY = 20

    PIPELINE_INTERVALS = ['1d', '1wk', '1mo']

    LOOKBACK_DAYS = {
        '1d': 365,
        '1wk': 500,
        '1mo': 1200,
    }

    FUNDAMENTAL_CONCURRENCY = 35
    FUNDAMENTAL_STALE_DAYS = 95

    def __init__(self, data_source_manager: DataSourceManager, pg_repo,
                 stock_list_repo, mongo_db=None, stock_metadata_repo=None):
        self.dsm = data_source_manager
        self.pg_repo = pg_repo
        self.stock_list_repo = stock_list_repo
        self.mongo_db = mongo_db
        self.metadata_repo = stock_metadata_repo
        self.calculator = IndicatorCalculator()

    # ── Main entry point ────────────────────────────────────

    async def run_nightly_update(self, intervals: List[str] = None) -> Dict[str, Any]:
        if intervals is None:
            intervals = self.PIPELINE_INTERVALS

        start = time.time()
        new_count = await self._discover_new_stocks()

        stocks = await self.stock_list_repo.get_all_stocks()
        symbols = [s.symbol for s in stocks]
        total = len(symbols)

        run_log = {
            'run_type': 'nightly',
            'run_date': datetime.utcnow().isoformat(),
            'started_at': datetime.utcnow(),
            'total_symbols': total,
            'new_stocks_added': new_count,
            'intervals': intervals,
            'success': 0,
            'skipped_up_to_date': 0,
            'failed_validation': 0,
            'retried_with_fallback': 0,
            'retry_success': 0,
            'dead_letter': 0,
            'failed_symbols': [],
            'per_interval': {},
            'duration_seconds': 0,
            'status': 'running',
        }

        try:
            for interval in intervals:
                await self.dsm.health.reset_all()
                interval_start = time.time()
                latest_dates = await self.pg_repo.get_latest_dates(interval)

                existing = [s for s in symbols if s in latest_dates]
                new = [s for s in symbols if s not in latest_dates]

                print(f"[{interval}] {len(existing)} existing, {len(new)} new symbols")

                if existing:
                    await self._run_incremental_bulk(existing, interval, latest_dates, run_log)
                if new:
                    await self._run_bulk_new(new, interval, run_log)

                interval_stats = {
                    'duration': round(time.time() - interval_start, 1),
                    'existing': len(existing),
                    'new': len(new),
                }
                run_log['per_interval'][interval] = interval_stats
                print(f"  [{interval}] done in {interval_stats['duration']}s")

            # ── Fundamental data incremental update ────────
            if self.metadata_repo:
                print(f"\n  [fundamentals] Checking for stale/missing data...")
                fund_start = time.time()
                fund_stats = await self._update_fundamentals(symbols)
                fund_stats['duration'] = round(time.time() - fund_start, 1)
                run_log['fundamentals'] = fund_stats
                print(f"  [fundamentals] done in {fund_stats['duration']}s — "
                      f"{fund_stats['updated']} updated, "
                      f"{fund_stats['up_to_date']} up-to-date, "
                      f"{fund_stats['failed']} failed")

            # ── News sentiment update ─────────────────────
            if self.metadata_repo:
                print(f"\n  [news] Refreshing news sentiment...")
                news_start = time.time()
                news_stats = await self._update_news_sentiment(symbols)
                news_stats['duration'] = round(time.time() - news_start, 1)
                run_log['news_sentiment'] = news_stats
                print(f"  [news] done in {news_stats['duration']}s — "
                      f"{news_stats['updated']} updated, "
                      f"{news_stats['skipped']} skipped, "
                      f"{news_stats['failed']} failed")

            run_log['status'] = 'completed'

        except Exception as e:
            run_log['status'] = 'failed'
            run_log['error'] = str(e)
            print(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()

        run_log['completed_at'] = datetime.utcnow()
        run_log['duration_seconds'] = round(time.time() - start, 1)

        if self.mongo_db is not None:
            try:
                await self.mongo_db['pipeline_runs'].insert_one(run_log)
            except Exception as e:
                print(f"Failed to log pipeline run: {e}")

        self._print_health_report(run_log)
        return run_log

    # ── New stock discovery ─────────────────────────────────

    async def _discover_new_stocks(self) -> int:
        try:
            from stock_list_manager import StockListManager
            slm = await asyncio.to_thread(StockListManager)
            stocks_df = slm.stock_list

            if stocks_df.empty:
                print("[Discovery] StockListManager returned empty, skipping")
                return 0

            existing = await self.stock_list_repo.get_all_stocks()
            existing_symbols = {s.symbol for s in existing}

            new_stocks = []
            for _, row in stocks_df.iterrows():
                sym = row['Symbol']
                if sym not in existing_symbols:
                    new_stocks.append({
                        'symbol': sym,
                        'name': row.get('Name', sym),
                        'exchange': row.get('Exchange', 'UNKNOWN'),
                        'market_cap': row.get('Market_Cap'),
                    })

            if new_stocks:
                added = await self.stock_list_repo.upsert_stocks(new_stocks)
                if added:
                    print(f"[Discovery] {added} new stocks: "
                          f"{[s['symbol'] for s in new_stocks[:10]]}")
                return added
            print("[Discovery] No new stocks found")
            return 0
        except Exception as e:
            print(f"[Discovery] Failed (non-fatal): {e}")
            return 0

    # ── Concurrent compute+save for a chunk ──────────────────

    async def _process_chunk_results(self, results: Dict, interval: str,
                                      run_log: Dict, latest_dates: Dict = None):
        sem = asyncio.Semaphore(self.COMPUTE_CONCURRENCY)
        lock = asyncio.Lock()

        async def process_one(symbol, result):
            if not (result.success and result.data is not None):
                async with lock:
                    run_log['failed_validation'] += 1
                    run_log['failed_symbols'].append({
                        'symbol': symbol, 'interval': interval,
                        'error': result.error or 'unknown', 'stage': 'bulk_fetch',
                    })
                return

            async with sem:
                try:
                    indicators = await asyncio.to_thread(
                        self.calculator.compute_all_indicators, result.data, interval
                    )
                    if latest_dates is not None:
                        cutoff = latest_dates.get(symbol)
                        if cutoff is not None:
                            indicators = self._filter_after_cutoff(indicators, cutoff)
                    if indicators['stock_price'] is not None and not indicators['stock_price'].empty:
                        await self.pg_repo.save_technical_data(symbol, interval, indicators)
                        async with lock:
                            run_log['success'] += 1
                    else:
                        async with lock:
                            run_log['skipped_up_to_date'] += 1
                except Exception as e:
                    async with lock:
                        run_log['failed_validation'] += 1
                        run_log['failed_symbols'].append({
                            'symbol': symbol, 'interval': interval,
                            'error': str(e), 'stage': 'compute/save',
                        })

        await asyncio.gather(*[process_one(s, r) for s, r in results.items()])

    # ── Incremental bulk (all intervals) ─────────────────────

    async def _run_incremental_bulk(self, symbols: List[str], interval: str,
                                     latest_dates: Dict, run_log: Dict):
        earliest_latest = min(latest_dates[s] for s in symbols if s in latest_dates)
        lookback = timedelta(days=self.LOOKBACK_DAYS.get(interval, 365))
        start_date = (pd.Timestamp(earliest_latest) - lookback).strftime('%Y-%m-%d')

        today = pd.Timestamp(datetime.utcnow().date())
        all_up_to_date = all(
            pd.Timestamp(latest_dates[s]).date() >= today.date()
            for s in symbols if s in latest_dates
        )
        if all_up_to_date:
            print(f"  [{interval}] All {len(symbols)} existing symbols up to date, skipping")
            run_log['skipped_up_to_date'] += len(symbols)
            return

        print(f"  [{interval}] Incremental bulk from {start_date} ({len(symbols)} symbols)")

        for i in range(0, len(symbols), self.BULK_CHUNK_SIZE):
            chunk = symbols[i:i + self.BULK_CHUNK_SIZE]
            results = await self.dsm.fetch_bulk_ohlcv(chunk, interval, start_date=start_date)
            await self._process_chunk_results(results, interval, run_log, latest_dates)

        print(f"  [{interval}] Incremental done")

    # ── Full bulk (new symbols) ────────────────────────────

    async def _run_bulk_new(self, symbols: List[str], interval: str, run_log: Dict):
        for i in range(0, len(symbols), self.BULK_CHUNK_SIZE):
            chunk = symbols[i:i + self.BULK_CHUNK_SIZE]
            print(f"  [{interval}] Full fetch for {len(chunk)} new symbols")
            results = await self.dsm.fetch_bulk_ohlcv(chunk, interval)
            await self._process_chunk_results(results, interval, run_log)

    # ── Fundamental data incremental ─────────────────────

    async def _update_fundamentals(self, symbols: List[str]) -> Dict[str, Any]:
        stats = {'updated': 0, 'up_to_date': 0, 'failed': 0, 'failed_symbols': []}
        sem = asyncio.Semaphore(self.FUNDAMENTAL_CONCURRENCY)

        async def check_and_update(sym: str):
            async with sem:
                try:
                    existing = await self.metadata_repo.get_stock_metadata(sym)

                    if existing and not self._fundamentals_stale(existing):
                        stats['up_to_date'] += 1
                        return

                    metadata = existing or {}
                    updated = False

                    overview, fund = await asyncio.gather(
                        self.dsm.fetch_company_overview(sym),
                        self.dsm.fetch_fundamentals(sym),
                    )

                    if overview.success and overview.data:
                        metadata['company_overview'] = overview.data
                        updated = True

                    if fund.success and fund.data:
                        new_fund = fund.data
                        old_fund = metadata.get('stock_fundamental', {})
                        merged = self._merge_fundamentals(old_fund, new_fund)
                        if merged:
                            metadata['stock_fundamental'] = merged
                            updated = True

                    if updated:
                        await self.metadata_repo.create_or_update_stock_metadata(
                            sym, metadata
                        )
                        stats['updated'] += 1
                    else:
                        stats['up_to_date'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['failed_symbols'].append({'symbol': sym, 'error': str(e)})

        tasks = [check_and_update(s) for s in symbols]
        await asyncio.gather(*tasks)
        return stats

    NEWS_CONCURRENCY = 35

    async def _update_news_sentiment(self, symbols: List[str]) -> Dict[str, Any]:
        stats = {'updated': 0, 'skipped': 0, 'failed': 0}
        sem = asyncio.Semaphore(self.NEWS_CONCURRENCY)
        lock = asyncio.Lock()

        async def fetch_news(sym: str):
            async with sem:
                try:
                    existing = await self.metadata_repo.get_stock_metadata(sym)
                    if existing:
                        cached = existing.get('news_sentiment')
                        if cached and cached.get('fetched_at'):
                            age = (datetime.utcnow() - cached['fetched_at']).total_seconds()
                            if age < 86400:
                                async with lock:
                                    stats['skipped'] += 1
                                return

                    result = await self.dsm.fetch_news_sentiment(sym)
                    if result.success and result.data:
                        news = result.data
                        news['fetched_at'] = datetime.utcnow()
                        metadata = existing or {'ticker': sym}
                        metadata['news_sentiment'] = news
                        await self.metadata_repo.create_or_update_stock_metadata(sym, metadata)
                        async with lock:
                            stats['updated'] += 1
                    else:
                        async with lock:
                            stats['skipped'] += 1
                except Exception:
                    async with lock:
                        stats['failed'] += 1

        await asyncio.gather(*[fetch_news(s) for s in symbols])
        return stats

    def _fundamentals_stale(self, metadata: Dict) -> bool:
        fund = metadata.get('stock_fundamental', {})
        if not fund:
            return True
        try:
            quarterly = fund.get('quarterly', {})
            income = quarterly.get('income_statement', {})
            data_list = income.get('data', []) if isinstance(income, dict) else []
            if not data_list:
                return True
            last_date_val = data_list[0].get('fiscalDateEnding')
            if not last_date_val:
                return True
            if isinstance(last_date_val, str):
                last_date = datetime.strptime(last_date_val[:10], '%Y-%m-%d')
            elif isinstance(last_date_val, datetime):
                last_date = last_date_val
            else:
                return True
            return (datetime.utcnow() - last_date).days > self.FUNDAMENTAL_STALE_DAYS
        except Exception:
            return True

    @staticmethod
    def _merge_fundamentals(old: Dict, new: Dict) -> Optional[Dict]:
        if not new:
            return None
        merged = dict(old) if old else {}
        has_content = False
        for period in ('annual', 'quarterly'):
            if period not in merged:
                merged[period] = {}
            if period in new:
                for stmt in ('income_statement', 'balance_sheet', 'cash_flow'):
                    new_stmt = new[period].get(stmt)
                    if isinstance(new_stmt, pd.DataFrame) and not new_stmt.empty:
                        merged[period][stmt] = new_stmt
                        has_content = True
        return merged if has_content else None

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _filter_after_cutoff(technical_data: Dict[str, Any], cutoff) -> Dict[str, Any]:
        cutoff_ts = pd.Timestamp(cutoff)
        if cutoff_ts.tz is not None:
            cutoff_ts = cutoff_ts.tz_localize(None)
        filtered = {}

        for key, value in technical_data.items():
            if isinstance(value, pd.DataFrame):
                filtered[key] = value[value.index > cutoff_ts]
            elif isinstance(value, dict):
                filtered_dict = {}
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, pd.Series):
                        filtered_dict[sub_key] = sub_value[sub_value.index > cutoff_ts]
                    else:
                        filtered_dict[sub_key] = sub_value
                filtered[key] = filtered_dict
            else:
                filtered[key] = value
        return filtered

    @staticmethod
    def _print_health_report(run_log: Dict):
        dur = run_log['duration_seconds']
        status = run_log['status'].upper()
        print(f"\n{'=' * 70}")
        print(f"NIGHTLY PIPELINE {status} — {dur:.0f}s ({dur / 60:.1f} min)")
        print(f"  Symbols: {run_log['total_symbols']}  "
              f"New: {run_log.get('new_stocks_added', 0)}")
        print(f"  Success: {run_log['success']}  "
              f"Skipped (up-to-date): {run_log['skipped_up_to_date']}")
        print(f"  Failed: {run_log['failed_validation']}  "
              f"Dead letter: {run_log['dead_letter']}")
        print(f"  Retried: {run_log['retried_with_fallback']}  "
              f"Retry success: {run_log['retry_success']}")

        failed = run_log.get('failed_symbols', [])
        if failed:
            print(f"\n  FAILED SYMBOLS ({len(failed)}):")
            for entry in failed[:20]:
                print(f"    {entry['symbol']} [{entry.get('interval','')}] "
                      f"— {entry.get('stage','')}: {entry.get('error','')}")
            if len(failed) > 20:
                print(f"    ... and {len(failed) - 20} more")

        for interval, stats in run_log.get('per_interval', {}).items():
            print(f"  [{interval}] {stats.get('existing', 0)} existing, "
                  f"{stats.get('new', 0)} new — {stats.get('duration', 0)}s")

        fund = run_log.get('fundamentals')
        if fund:
            print(f"  [fundamentals] {fund.get('updated', 0)} updated, "
                  f"{fund.get('up_to_date', 0)} up-to-date, "
                  f"{fund.get('failed', 0)} failed — {fund.get('duration', 0)}s")

        print("=" * 70)
