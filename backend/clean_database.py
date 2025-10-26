#!/usr/bin/env python3
"""
Clean all database data for fresh initialization
"""

import asyncio
from postgres_database import postgres_db
from redis_database import redis_db
from database import db

async def clean_all_databases():
    print("🧹 Starting database cleanup...")
    
    try:
        # Connect to databases
        await db.connect_mongodb()
        await postgres_db.connect()
        await redis_db.connect()
        
        # Clean MongoDB
        print("🗑️ Cleaning MongoDB...")
        # Get the database and collections
        mongodb = db.mongodb_client['stock_data']
        stock_list_collection = mongodb['stock_list']
        stock_metadata_collection = mongodb['stock_metadata']
        
        # Delete all documents from collections
        await stock_list_collection.delete_many({})
        await stock_metadata_collection.delete_many({})
        print("✅ MongoDB cleaned")
        
        # Clean PostgreSQL
        print("🗑️ Cleaning PostgreSQL...")
        async with postgres_db.pool.acquire() as connection:
            await connection.execute("""
                TRUNCATE TABLE interval_1m_technical, interval_5m_technical, interval_15m_technical, 
                            interval_30m_technical, interval_60m_technical, interval_1d_technical, 
                            interval_1wk_technical, interval_1mo_technical;
            """)
        print("✅ PostgreSQL cleaned")
        
        # Clean Redis
        print("🗑️ Cleaning Redis...")
        await redis_db.redis.flushdb()
        print("✅ Redis cleaned")
        
        print("🎉 All databases cleaned successfully!")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Disconnect
        await db.close_connections()
        await postgres_db.disconnect()
        await redis_db.disconnect()

if __name__ == "__main__":
    asyncio.run(clean_all_databases())
