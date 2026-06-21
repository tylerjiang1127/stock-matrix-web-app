"""
First-time database initialization — cleans databases and loads full OHLCV + indicators
for all stocks from NASDAQ/NYSE/AMEX at 1d/1wk/1mo intervals.

Minute/hour-level data is NOT loaded here; it's fetched on-demand when users request it.
"""

import asyncio
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

from data_sources.indicator_calculator import IndicatorCalculator
from data_sources.data_source_manager import DataSourceManager


class DataInitializer:

    INIT_INTERVALS = ['1d', '1wk', '1mo']
    BULK_CHUNK_SIZE = 500
    SAVE_CONCURRENCY = 5
    FETCH_CONCURRENCY = 10

    PG_TABLES = [
        'interval_1d_technical', 'interval_1wk_technical', 'interval_1mo_technical',
        'interval_60m_technical', 'interval_30m_technical', 'interval_15m_technical',
        'interval_5m_technical', 'interval_1m_technical',
    ]

    FUNDAMENTAL_CONCURRENCY = 10

    def __init__(self, data_source_manager: DataSourceManager, pg_repo,
                 stock_list_repo, mongo_db=None, stock_metadata_repo=None):
        self.dsm = data_source_manager
        self.pg_repo = pg_repo
        self.stock_list_repo = stock_list_repo
        self.mongo_db = mongo_db
        self.metadata_repo = stock_metadata_repo
        self.calculator = IndicatorCalculator()

    async def needs_initialization(self) -> bool:
        latest = await self.pg_repo.get_latest_dates('1d')
        return len(latest) == 0

    async def _reset_health_monitors(self):
        """Reset circuit breakers so failures in one step don't cascade to the next."""
        health = self.dsm.health
        for source in self.dsm.adapters:
            await health._set(f"health:{source}:circuit_state", "closed")
            await health._set(f"health:{source}:consecutive_failures", "0")
        print("  Health monitors reset")

    async def run(self) -> Dict[str, Any]:
        run_log = {
            'run_type': 'initialization',
            'status': 'running',
            'started_at': datetime.utcnow(),
            'completed_at': None,
            'duration_seconds': 0,
            'total_symbols': 0,
            'per_interval': {},
            'errors_summary': [],
        }
        start = time.time()

        try:
            # 1. Clean databases
            print("\n" + "=" * 70)
            print("INITIALIZATION — Step 1: Cleaning databases")
            print("=" * 70)
            await self._clean_databases()

            # 2. Fetch stock list from all exchanges
            print("\n" + "=" * 70)
            print("INITIALIZATION — Step 2: Fetching stock list (NASDAQ/NYSE/AMEX)")
            print("=" * 70)
            symbols = await self._load_stock_list()
            run_log['total_symbols'] = len(symbols)
            print(f"  Total symbols loaded: {len(symbols)}")

            # 3. Load full history for each interval
            for interval in self.INIT_INTERVALS:
                print(f"\n{'=' * 70}")
                print(f"INITIALIZATION — Step 3: Loading {interval} data ({len(symbols)} symbols)")
                print("=" * 70)
                await self._reset_health_monitors()
                interval_start = time.time()

                if interval == '1d':
                    stats = await self._load_daily_bulk(symbols)
                else:
                    stats = await self._load_per_symbol(symbols, interval)

                stats['duration_seconds'] = round(time.time() - interval_start, 1)
                run_log['per_interval'][interval] = stats
                print(f"  [{interval}] Done — {stats['success']} ok, "
                      f"{stats['failed']} failed in {stats['duration_seconds']}s")

            # 4. Load fundamental data (company overview + financial statements)
            if self.metadata_repo:
                print(f"\n{'=' * 70}")
                print(f"INITIALIZATION — Step 4: Loading fundamental data ({len(symbols)} symbols)")
                print("=" * 70)
                await self._reset_health_monitors()
                fund_start = time.time()
                fund_stats = await self._load_fundamentals(symbols)
                fund_stats['duration_seconds'] = round(time.time() - fund_start, 1)
                run_log['fundamentals'] = fund_stats
                print(f"  [fundamentals] Done — {fund_stats['success']} ok, "
                      f"{fund_stats['failed']} failed in {fund_stats['duration_seconds']}s")

            run_log['status'] = 'completed'

        except Exception as e:
            run_log['status'] = 'failed'
            run_log['errors_summary'].append(str(e))
            print(f"\nINITIALIZATION FAILED: {e}")
            import traceback
            traceback.print_exc()

        run_log['completed_at'] = datetime.utcnow()
        run_log['duration_seconds'] = round(time.time() - start, 1)

        if self.mongo_db is not None:
            try:
                await self.mongo_db['pipeline_runs'].insert_one(run_log)
            except Exception as e:
                print(f"Failed to save run log: {e}")

        self._print_summary(run_log)
        return run_log

    # ── Database cleanup ───────────────────────────────────

    async def _clean_databases(self):
        for table in self.PG_TABLES:
            try:
                await self.pg_repo.db.execute_command(f'TRUNCATE TABLE {table}')
                print(f"  Truncated PG table: {table}")
            except Exception as e:
                print(f"  Warning: could not truncate {table}: {e}")

        await self.stock_list_repo.collection.delete_many({})
        print("  Cleared MongoDB: stock_list")

        if self.mongo_db is not None:
            await self.mongo_db['stock_metadata'].delete_many({})
            print("  Cleared MongoDB: stock_metadata")

    # ── Stock list loading ─────────────────────────────────

    async def _load_stock_list(self) -> List[str]:
        from stock_list_manager import StockListManager
        slm = await asyncio.to_thread(StockListManager)
        stocks_df = slm.stock_list

        if stocks_df.empty:
            raise RuntimeError("StockListManager returned empty stock list")

        await self.stock_list_repo.create_stock_list(stocks_df)
        return stocks_df['Symbol'].tolist()

    # ── Daily bulk download ────────────────────────────────

    async def _load_daily_bulk(self, symbols: List[str]) -> Dict[str, Any]:
        stats = {'success': 0, 'failed': 0, 'failed_symbols': []}
        total = len(symbols)
        processed = 0

        for i in range(0, total, self.BULK_CHUNK_SIZE):
            chunk = symbols[i:i + self.BULK_CHUNK_SIZE]
            chunk_num = i // self.BULK_CHUNK_SIZE + 1
            total_chunks = (total + self.BULK_CHUNK_SIZE - 1) // self.BULK_CHUNK_SIZE
            print(f"  [1d] Bulk chunk {chunk_num}/{total_chunks} ({len(chunk)} symbols)...")

            dl_start = time.time()
            results = await self.dsm.fetch_bulk_daily_ohlcv(chunk)
            print(f"    Download: {time.time() - dl_start:.1f}s")

            sem = asyncio.Semaphore(self.SAVE_CONCURRENCY)

            async def compute_and_save(sym: str, fetch_result):
                async with sem:
                    if not fetch_result.success or fetch_result.data is None:
                        stats['failed'] += 1
                        stats['failed_symbols'].append({
                            'symbol': sym, 'error': fetch_result.error or 'no data'
                        })
                        return
                    try:
                        indicators = self.calculator.compute_all_indicators(
                            fetch_result.data, '1d'
                        )
                        await self.pg_repo.save_technical_data(sym, '1d', indicators)
                        stats['success'] += 1
                    except Exception as e:
                        stats['failed'] += 1
                        stats['failed_symbols'].append({'symbol': sym, 'error': str(e)})

            tasks = [compute_and_save(sym, r) for sym, r in results.items()]
            await asyncio.gather(*tasks)

            processed += len(chunk)
            print(f"    Progress: {processed}/{total} "
                  f"({stats['success']} ok, {stats['failed']} failed)")

        return stats

    # ── Per-symbol fetch (weekly/monthly) ──────────────────

    async def _load_per_symbol(self, symbols: List[str], interval: str) -> Dict[str, Any]:
        stats = {'success': 0, 'failed': 0, 'failed_symbols': []}
        total = len(symbols)
        progress_lock = asyncio.Lock()
        progress = [0]
        last_report = [time.time()]

        sem = asyncio.Semaphore(self.FETCH_CONCURRENCY)

        async def fetch_and_save(sym: str):
            async with sem:
                try:
                    result = await asyncio.wait_for(
                        self.dsm.fetch_ohlcv(sym, interval),
                        timeout=120,
                    )
                except asyncio.TimeoutError:
                    stats['failed'] += 1
                    stats['failed_symbols'].append({'symbol': sym, 'error': 'timeout'})
                    return

                if not result.success or result.data is None:
                    stats['failed'] += 1
                    err = result.error or 'no data'
                    if 'No data' not in err:
                        stats['failed_symbols'].append({'symbol': sym, 'error': err})
                    return

                try:
                    indicators = self.calculator.compute_all_indicators(
                        result.data, interval
                    )
                    await self.pg_repo.save_technical_data(sym, interval, indicators)
                    stats['success'] += 1
                except Exception as e:
                    stats['failed'] += 1
                    stats['failed_symbols'].append({'symbol': sym, 'error': str(e)})

                async with progress_lock:
                    progress[0] += 1
                    now = time.time()
                    if now - last_report[0] >= 10 or progress[0] == total:
                        pct = progress[0] / total * 100
                        print(f"  [{interval}] {progress[0]}/{total} ({pct:.0f}%) — "
                              f"{stats['success']} ok, {stats['failed']} failed")
                        last_report[0] = now

        tasks = [fetch_and_save(s) for s in symbols]
        await asyncio.gather(*tasks)
        return stats

    # ── Fundamental data loading ────────────────────────

    async def _load_fundamentals(self, symbols: List[str]) -> Dict[str, Any]:
        stats = {'success': 0, 'failed': 0, 'failed_symbols': []}
        total = len(symbols)
        progress_lock = asyncio.Lock()
        progress = [0]
        last_report = [time.time()]

        sem = asyncio.Semaphore(self.FUNDAMENTAL_CONCURRENCY)

        async def fetch_and_save(sym: str):
            async with sem:
                metadata = {}
                try:
                    overview_result = await asyncio.wait_for(
                        self.dsm.fetch_company_overview(sym), timeout=60,
                    )
                    if overview_result.success and overview_result.data:
                        metadata['company_overview'] = overview_result.data
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

                try:
                    fund_result = await asyncio.wait_for(
                        self.dsm.fetch_fundamentals(sym), timeout=60,
                    )
                    if fund_result.success and fund_result.data:
                        metadata['stock_fundamental'] = fund_result.data
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass

                if metadata:
                    try:
                        await self.metadata_repo.create_or_update_stock_metadata(
                            sym, metadata
                        )
                        stats['success'] += 1
                    except Exception as e:
                        stats['failed'] += 1
                        stats['failed_symbols'].append({'symbol': sym, 'error': str(e)})
                else:
                    stats['failed'] += 1
                    stats['failed_symbols'].append({'symbol': sym, 'error': 'no data'})

                async with progress_lock:
                    progress[0] += 1
                    now = time.time()
                    if now - last_report[0] >= 10 or progress[0] == total:
                        pct = progress[0] / total * 100
                        print(f"  [fundamentals] {progress[0]}/{total} ({pct:.0f}%) — "
                              f"{stats['success']} ok, {stats['failed']} failed")
                        last_report[0] = now

        tasks = [fetch_and_save(s) for s in symbols]
        await asyncio.gather(*tasks)
        return stats

    # ── Summary ────────────────────────────────────────────

    @staticmethod
    def _print_summary(run_log: Dict):
        dur = run_log['duration_seconds']
        minutes = dur / 60
        print(f"\n{'=' * 70}")
        print(f"INITIALIZATION {run_log['status'].upper()}")
        print(f"  Total symbols: {run_log['total_symbols']}")
        print(f"  Duration: {dur:.0f}s ({minutes:.1f} min)")
        all_stats = list(run_log.get('per_interval', {}).items())
        if 'fundamentals' in run_log:
            all_stats.append(('fundamentals', run_log['fundamentals']))
        for label, stats in all_stats:
            ok = stats.get('success', 0)
            fail = stats.get('failed', 0)
            idur = stats.get('duration_seconds', 0)
            print(f"  [{label}] {ok} ok, {fail} failed ({idur:.0f}s)")
            failed_syms = stats.get('failed_symbols', [])
            if failed_syms:
                sample = failed_syms[:5]
                print(f"    Sample errors: {sample}")
                if len(failed_syms) > 5:
                    print(f"    ... and {len(failed_syms) - 5} more")
        print("=" * 70)
