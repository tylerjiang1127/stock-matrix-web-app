import os
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.mongodb_url = os.getenv("MONGODB_URL")
        self.redis_url = os.getenv("REDIS_URL")
        
    async def connect_mongodb(self):
        self.mongodb_client = AsyncIOMotorClient(self.mongodb_url)
        self.mongodb_db = self.mongodb_client.stock_data
        return self.mongodb_db
    
    async def connect_redis(self):
        self.redis_client = redis.from_url(self.redis_url)
        return self.redis_client
    
    async def close_connections(self):
        if hasattr(self, 'mongodb_client'):
            self.mongodb_client.close()
        if hasattr(self, 'redis_client'):
            await self.redis_client.close()

# global database instance
db = Database()