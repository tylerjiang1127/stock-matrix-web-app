"""
PostgreSQL database connection and configuration
"""

import asyncio
import asyncpg
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class PostgreSQLDatabase:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Connect to PostgreSQL database"""
        try:
            # Database connection parameters
            database_url = os.getenv(
                "POSTGRES_URL", 
                "postgresql://stock_user:stock_password123@localhost:5432/stock_technical_data"
            )
            
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=3,
                max_size=40,
                max_inactive_connection_lifetime=60,  # recycle idle connections after 60s
                command_timeout=600,
                timeout=10,
            )
            print("✅ Connected to PostgreSQL database")
            
        except Exception as e:
            print(f"❌ Error connecting to PostgreSQL: {e}")
            raise e
    
    async def reset_pool(self):
        """Close and recreate the connection pool to clear stale connections."""
        if self.pool:
            await self.pool.close()
            await self.connect()
            print("✅ PostgreSQL connection pool reset")

    async def disconnect(self):
        """Disconnect from PostgreSQL database"""
        if self.pool:
            await self.pool.close()
            print("✅ Disconnected from PostgreSQL database")
    
    async def execute_query(self, query: str, *args):
        if not self.pool:
            raise Exception("Database not connected")
        async with self.pool.acquire(timeout=10) as connection:
            return await connection.fetch(query, *args)

    async def execute_command(self, command: str, *args):
        if not self.pool:
            raise Exception("Database not connected")
        async with self.pool.acquire(timeout=10) as connection:
            return await connection.execute(command, *args)

    async def fetch_one(self, query: str, *args):
        if not self.pool:
            raise Exception("Database not connected")
        async with self.pool.acquire(timeout=10) as connection:
            return await connection.fetchrow(query, *args)

    async def fetch_many(self, query: str, *args):
        if not self.pool:
            raise Exception("Database not connected")
        async with self.pool.acquire(timeout=10) as connection:
            return await connection.fetch(query, *args)

# Global database instance
postgres_db = PostgreSQLDatabase()
