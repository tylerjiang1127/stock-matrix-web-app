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

    async def initialize_stock_metadata(self, alpha_vantage_api_key: str, 
                                      max_stocks: int = None, 
                                      delay_between_requests: int = 12) -> bool:
        """Initialize stock metadata using hybrid storage (MongoDB + PostgreSQL + Redis)"""
        try:
            print("🔄 Initializing stock metadata with hybrid storage...")
            
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
            
            success_count = 0
            error_count = 0
            
            for i, stock in enumerate(stocks, 1):
                try:
                    print(f"\n📈 Processing {i}/{len(stocks)}: {stock.symbol}")
                    
                    # Create StockMetaDataFetcher instance
                    fetcher = StockMetaDataFetcher(stock.symbol, alpha_vantage_api_key)
                    
                    # Get the metadata
                    metadata = fetcher.stock_metadata
                    
                    # Save company overview and fundamental data to MongoDB
                    mongo_metadata = {
                        'company_overview': metadata.get('company_overview', {}),
                        'stock_fundamental': metadata.get('stock_fundamental', {})
                    }
                    
                    mongo_success = await self.stock_metadata_repo.create_or_update_stock_metadata(
                        stock.symbol, mongo_metadata
                    )
                    
                    # Save technical data to PostgreSQL
                    technical_data = metadata.get('stock_technical_data', {})
                    postgres_success = True
                    
                    for interval, interval_data in technical_data.items():
                        # Check if interval_data is not empty (handle both dict and DataFrame)
                        if interval_data is not None and len(interval_data) > 0:
                            success = await self.technical_data_repo.save_technical_data(
                                stock.symbol, interval, interval_data
                            )
                            if not success:
                                postgres_success = False
                                print(f"⚠️ Failed to save {interval} technical data for {stock.symbol}")
                    
                    # Cache metadata in Redis (only if MongoDB save was successful)
                    if mongo_success:
                        try:
                            await cache_manager.cache_stock_metadata(stock.symbol, mongo_metadata, expire=3600)
                            print(f"📦 Cached metadata for {stock.symbol} in Redis")
                        except Exception as e:
                            print(f"⚠️ Failed to cache {stock.symbol} in Redis: {e}")
                    
                    if mongo_success and postgres_success:
                        success_count += 1
                        print(f"✅ {stock.symbol} metadata saved successfully (MongoDB + PostgreSQL + Redis)")
                    else:
                        error_count += 1
                        print(f"❌ Failed to save {stock.symbol} metadata")
                    
                    # Rate limiting - now it's premium API which allows 75 requests per minute, so we don't need to sleep
                    ##if i < len(stocks):  # Don't sleep after the last request
                        ##print(f"⏳ Waiting {delay_between_requests} seconds...")
                        ##await asyncio.sleep(delay_between_requests)
                        
                except Exception as e:
                    error_count += 1
                    print(f"❌ Error processing {stock.symbol}: {e}")
                    continue
            
            print(f"\n🎉 Stock metadata initialization completed!")
            print(f"✅ Successfully processed: {success_count} stocks")
            print(f"❌ Errors: {error_count} stocks")
            
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error initializing stock metadata: {e}")
            return False

    async def initialize_database(self, alpha_vantage_api_key: str, 
                                max_stocks: int = None) -> bool:
        """Initialize complete database"""
        try:
            print("🚀 Starting database initialization...")
            print(f"📊 Max stocks: {max_stocks}")
            
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
            
            # Initialize stock metadata
            print("📈 Initializing stock metadata...")
            metadata_success = await self.initialize_stock_metadata(
                alpha_vantage_api_key, max_stocks
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
