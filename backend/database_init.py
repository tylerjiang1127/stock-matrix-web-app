import asyncio
import time
from typing import List, Dict, Any
import pandas as pd
from repositories import StockListRepository, StockMetadataRepository
from database import db
from postgres_database import postgres_db
from simple_postgres_models import SimpleTechnicalDataRepository
from redis_database import redis_db, cache_manager
from stock_metadata_fetcher import StockMetaDataFetcher

class DatabaseInitializer:
    def __init__(self):
        self.stock_list_repo = None
        self.stock_metadata_repo = None
        self.technical_data_repo = None

    async def initialize_repositories(self):
        """Initialize database repositories"""
        # Connect to MongoDB
        mongodb = await db.connect_mongodb()
        self.stock_list_repo = StockListRepository(mongodb)
        self.stock_metadata_repo = StockMetadataRepository(mongodb)
        
        # Connect to PostgreSQL
        await postgres_db.connect()
        self.technical_data_repo = SimpleTechnicalDataRepository(postgres_db)
        
        # Connect to Redis
        await redis_db.connect()

    async def initialize_stock_list(self, alpha_vantage_api_key: str, max_stocks: int = None) -> bool:
        """Initialize stock list table"""
        try:
            print("🔄 Initializing stock list...")
            
            # Import StockListManager from your existing code
            from stock_list_manager import StockListManager
            
            stock_manager = StockListManager(max_stocks=max_stocks)
            stocks_df = stock_manager.stock_list
            
            if stocks_df.empty:
                print("❌ No stock data retrieved")
                return False
            
            # Save to database
            success = await self.stock_list_repo.create_stock_list(stocks_df)
            
            if success:
                print(f"✅ Stock list initialized with {len(stocks_df)} stocks")
                return True
            else:
                print("❌ Failed to save stock list to database")
                return False
                
        except Exception as e:
            print(f"❌ Error initializing stock list: {e}")
            return False

    async def _fetch_stock_data(self, stock, alpha_vantage_api_key: str, stock_num: int, total_stocks: int):
        """Fetch stock data from API only (step 1 of optimized pipeline)
        
        Returns:
            dict with stock data or None if failed
        """
        try:
            print(f"\n📈 Fetching API data {stock_num}/{total_stocks}: {stock.symbol}")
            fetch_start = time.time()
            
            # Run synchronous StockMetaDataFetcher in thread pool executor
            loop = asyncio.get_event_loop()
            fetcher = await loop.run_in_executor(
                None,  # Use default executor
                lambda: StockMetaDataFetcher(stock.symbol, alpha_vantage_api_key)
            )
            
            fetch_time = time.time() - fetch_start
            print(f"   ⏱️  API fetch completed in {fetch_time:.1f}s for {stock.symbol}")
            
            # Return the fetched data for later database insertion
            return {
                'symbol': stock.symbol,
                'metadata': fetcher.stock_metadata,
                'fetch_time': fetch_time,
                'stock_num': stock_num,
                'total_stocks': total_stocks
            }
            
        except Exception as e:
            print(f"❌ Error fetching {stock.symbol}: {e}")
            return None
    
    async def _save_stock_data_to_db(self, stock_data):
        """Save fetched stock data to databases (step 2 of optimized pipeline)
        
        Args:
            stock_data: dict returned from _fetch_stock_data
            
        Returns:
            dict with success status
        """
        if not stock_data:
            return {'success': False, 'symbol': 'unknown'}
        
        try:
            symbol = stock_data['symbol']
            metadata = stock_data['metadata']
            
            print(f"💾 Saving to database: {symbol}")
            save_start = time.time()
            
            # Save company overview and fundamental data to MongoDB
            mongo_metadata = {
                'company_overview': metadata.get('company_overview', {}),
                'stock_fundamental': metadata.get('stock_fundamental', {})
            }
            
            mongo_success = await self.stock_metadata_repo.create_or_update_stock_metadata(
                symbol, mongo_metadata
            )
            
            # Save technical data to PostgreSQL
            technical_data = metadata.get('stock_technical_data', {})
            postgres_success_count = 0
            postgres_fail_count = 0
            
            for interval, interval_data in technical_data.items():
                # Check if interval_data is not empty
                if interval_data is not None and len(interval_data) > 0:
                    success = await self.technical_data_repo.save_technical_data(
                        symbol, interval, interval_data
                    )
                    if success:
                        postgres_success_count += 1
                    else:
                        postgres_fail_count += 1
                        print(f"⚠️ Failed to save {interval} technical data for {symbol}")
            
            save_time = time.time() - save_start
            
            # Consider success if MongoDB saved AND at least one PostgreSQL interval saved
            # This allows partial success (e.g., 7/8 intervals saved is still success)
            overall_success = mongo_success and postgres_success_count > 0
            
            if overall_success:
                if postgres_fail_count > 0:
                    print(f"✅ {symbol} saved to DB in {save_time:.1f}s ({postgres_success_count} intervals, {postgres_fail_count} skipped)")
                else:
                    print(f"✅ {symbol} saved to DB in {save_time:.1f}s (MongoDB + {postgres_success_count} intervals)")
                return {'success': True, 'symbol': symbol, 'save_time': save_time}
            else:
                if postgres_success_count == 0:
                    print(f"❌ Failed to save {symbol} metadata (no intervals saved)")
                else:
                    print(f"❌ Failed to save {symbol} metadata (MongoDB failed)")
                return {'success': False, 'symbol': symbol}
                
        except Exception as e:
            symbol = stock_data.get('symbol', 'unknown')
            print(f"❌ Error saving {symbol}: {e}")
            return {'success': False, 'symbol': symbol, 'error': str(e)}

    async def initialize_stock_metadata(self, alpha_vantage_api_key: str, 
                                      max_stocks: int = None, 
                                      batch_size: int = 3) -> bool:
        """Initialize stock metadata using OPTIMIZED pipeline with separated API and DB operations
        
        Strategy:
        1. API calls are batched and rate-limited (60s per batch)
        2. Database insertions run in parallel queue (no waiting)
        3. Once batch API calls finish, immediately start next batch
        4. Database queue processes items as they complete
        
        Args:
            alpha_vantage_api_key: API key for Alpha Vantage
            max_stocks: Maximum number of stocks to process (None for all)
            batch_size: Number of stocks to process concurrently per minute (default: 3 for safety)
        """
        try:
            print("🔄 Initializing stock metadata with OPTIMIZED PIPELINE...")
            print(f"⚡ API batch size: {batch_size} stocks per minute")
            print(f"💾 Database queue: Parallel insertion (no rate limit)")
            
            # Get all stocks from database
            stocks = await self.stock_list_repo.get_all_stocks()
            
            if not stocks:
                print("❌ No stocks found in database. Please initialize stock list first.")
                return False
            
            # Limit number of stocks if specified
            if max_stocks:
                stocks = stocks[:max_stocks]
                print(f"📊 Processing {max_stocks} stocks (limited)")
            else:
                print(f"📊 Processing {len(stocks)} stocks")
            
            # Split stocks into batches for API calls
            batches = [stocks[i:i + batch_size] for i in range(0, len(stocks), batch_size)]
            print(f"📦 Total API batches: {len(batches)}")
            
            # Queue for database insertions
            db_queue = asyncio.Queue()
            
            # Stats
            api_fetch_count = 0
            db_save_count = 0
            error_count = 0
            
            # Database insertion worker
            async def db_worker():
                """Worker that continuously processes database insertions from queue"""
                nonlocal db_save_count, error_count
                while True:
                    stock_data = await db_queue.get()
                    if stock_data is None:  # Poison pill to stop worker
                        db_queue.task_done()
                        break
                    
                    # Save to database with comprehensive error handling
                    try:
                        result = await self._save_stock_data_to_db(stock_data)
                        
                        if result.get('success'):
                            db_save_count += 1
                        else:
                            error_count += 1
                            print(f"⚠️ Database save failed for {stock_data.get('symbol', 'unknown')}")
                    
                    except asyncio.CancelledError:
                        # Handle cancellation gracefully - log and continue
                        symbol = stock_data.get('symbol', 'unknown')
                        print(f"⚠️ Database operation cancelled for {symbol} - continuing with next stock")
                        error_count += 1
                    
                    except Exception as worker_error:
                        # Catch any other errors to prevent worker crash
                        symbol = stock_data.get('symbol', 'unknown')
                        print(f"❌ Unexpected error saving {symbol}: {worker_error}")
                        error_count += 1
                    
                    finally:
                        # Always mark task as done to prevent queue deadlock
                        db_queue.task_done()
            
            # Start database worker task
            db_worker_task = asyncio.create_task(db_worker())
            
            print(f"\n{'='*60}")
            print(f"🚀 Starting OPTIMIZED pipeline")
            print(f"   Step 1: Batch API calls (rate-limited)")
            print(f"   Step 2: Database queue (parallel)")
            print(f"{'='*60}")
            
            # Process API batches
            pipeline_start = time.time()
            
            for batch_num, batch in enumerate(batches, 1):
                batch_start_time = time.time()
                print(f"\n{'='*60}")
                print(f"🌐 API Batch {batch_num}/{len(batches)} ({len(batch)} stocks)")
                print(f"{'='*60}")
                
                # Fetch all stocks in this batch concurrently (API calls only)
                fetch_tasks = []
                for idx, stock in enumerate(batch, 1):
                    global_idx = (batch_num - 1) * batch_size + idx
                    task = self._fetch_stock_data(
                        stock, 
                        alpha_vantage_api_key, 
                        global_idx, 
                        len(stocks)
                    )
                    fetch_tasks.append(task)
                
                # Wait for all API calls in this batch to complete
                fetched_data = await asyncio.gather(*fetch_tasks, return_exceptions=True)
                
                # Add successfully fetched data to database queue
                for data in fetched_data:
                    if isinstance(data, Exception):
                        error_count += 1
                        print(f"❌ API fetch exception: {data}")
                    elif data is not None:
                        api_fetch_count += 1
                        await db_queue.put(data)  # Add to queue for database insertion
                    else:
                        error_count += 1
                
                batch_elapsed = time.time() - batch_start_time
                print(f"\n⏱️  API Batch {batch_num} completed in {batch_elapsed:.2f}s")
                print(f"   📊 Fetched: {api_fetch_count}/{len(stocks)} stocks")
                print(f"   💾 DB Queue size: {db_queue.qsize()} waiting")
                print(f"   ✅ DB Saved: {db_save_count} stocks")
                
                # Rate limiting: Wait until 60 seconds have passed before starting next API batch
                # But database insertions continue in parallel during wait time
                if batch_num < len(batches):  # Don't wait after the last batch
                    if batch_elapsed < 60:
                        wait_time = 60 - batch_elapsed
                        print(f"⏳ Waiting {wait_time:.1f}s before next API batch (rate limit)...")
                        print(f"   💡 Database insertions continue during wait...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"✅ Batch took >60s, starting next API batch immediately")
            
            # All API calls done, wait for database queue to finish
            print(f"\n{'='*60}")
            print(f"🌐 All API calls completed!")
            print(f"💾 Waiting for database queue to finish ({db_queue.qsize()} remaining)...")
            print(f"{'='*60}")
            
            await db_queue.put(None)  # Poison pill to stop worker
            await db_worker_task  # Wait for worker to finish
            await db_queue.join()  # Wait for all items to be processed
            
            pipeline_elapsed = time.time() - pipeline_start
            
            print(f"\n{'='*60}")
            print(f"🎉 OPTIMIZED PIPELINE COMPLETED!")
            print(f"⏱️  Total time: {pipeline_elapsed:.2f}s")
            print(f"🌐 API fetched: {api_fetch_count} stocks")
            print(f"💾 DB saved: {db_save_count} stocks")
            print(f"❌ Errors: {error_count}")
            print(f"{'='*60}")
            
            return db_save_count > 0
            
        except Exception as e:
            print(f"❌ Error initializing stock metadata: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def initialize_database(self, alpha_vantage_api_key: str, 
                                max_stocks: int = None,
                                batch_size: int = 6) -> bool:
        """Initialize complete database with async batch processing
        
        Args:
            alpha_vantage_api_key: Your Alpha Vantage API key
            max_stocks: Maximum number of stocks to process (None for all)
            batch_size: Number of stocks to process concurrently per minute (default: 6)
        """
        try:
            print("🚀 Starting database initialization...")
            print(f"📊 Max stocks: {max_stocks}")
            print(f"⚡ Batch size: {batch_size} stocks per minute")
            
            # Initialize repositories
            print("🔌 Initializing repositories...")
            await self.initialize_repositories()
            print("✅ Repositories initialized")
            
            # Initialize stock list
            print("📋 Initializing stock list...")
            stock_list_success = await self.initialize_stock_list(alpha_vantage_api_key, max_stocks)
            if not stock_list_success:
                print("❌ Failed to initialize stock list")
                return False
            print("✅ Stock list initialized")
            
            # Initialize stock metadata with batch processing
            print("📈 Initializing stock metadata...")
            metadata_success = await self.initialize_stock_metadata(
                alpha_vantage_api_key, max_stocks, batch_size
            )
            if not metadata_success:
                print("❌ Failed to initialize stock metadata")
                return False
            print("✅ Stock metadata initialized")
            
            print("🎉 Database initialization completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during database initialization: {e}")
            return False

# Global initializer instance
db_initializer = DatabaseInitializer()
