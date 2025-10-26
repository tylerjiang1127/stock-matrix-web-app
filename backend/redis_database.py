"""
Redis database connection and configuration for caching
"""

import aioredis
import json
from typing import Optional, Any, Dict
import os
from dotenv import load_dotenv

load_dotenv()

class RedisDatabase:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        
    async def connect(self):
        """Connect to Redis database"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis = aioredis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            await self.redis.ping()
            print("✅ Connected to Redis database")
            
        except Exception as e:
            print(f"❌ Error connecting to Redis: {e}")
            raise e
    
    async def disconnect(self):
        """Disconnect from Redis database"""
        if self.redis:
            await self.redis.close()
            print("✅ Disconnected from Redis database")
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        """Set a key-value pair in Redis"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        # Convert value to JSON string if it's not a string
        if not isinstance(value, str):
            value = json.dumps(value)
        
        await self.redis.set(key, value, ex=expire)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        value = await self.redis.get(key)
        if value is None:
            return None
        
        # Try to parse as JSON, fallback to string
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    async def delete(self, key: str):
        """Delete a key from Redis"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        await self.redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        return await self.redis.exists(key)
    
    async def expire(self, key: str, seconds: int):
        """Set expiration time for a key"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        await self.redis.expire(key, seconds)
    
    async def get_keys(self, pattern: str = "*") -> list:
        """Get all keys matching a pattern"""
        if not self.redis:
            raise Exception("Redis not connected")
        
        return await self.redis.keys(pattern)

class StockCacheManager:
    def __init__(self, redis_db: RedisDatabase):
        self.redis = redis_db
        
    async def cache_stock_metadata(self, symbol: str, metadata: Dict[str, Any], expire: int = 3600):
        """Cache stock metadata in Redis"""
        key = f"stock_metadata:{symbol}"
        
        # Convert DataFrames to serializable format
        serializable_metadata = self._convert_to_serializable(metadata)
        await self.redis.set(key, serializable_metadata, expire)
    
    def _convert_to_serializable(self, obj):
        """Convert objects to JSON serializable format"""
        import pandas as pd
        import numpy as np
        
        if isinstance(obj, pd.DataFrame):
            return {
                'data': obj.to_dict('records'),
                'columns': obj.columns.tolist(),
                'index': [str(idx) for idx in obj.index.tolist()]
            }
        elif isinstance(obj, pd.Series):
            return {
                'data': obj.to_dict(),
                'index': [str(idx) for idx in obj.index.tolist()]
            }
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, dict):
            return {str(k): self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(item) for item in obj]
        else:
            return obj
    
    async def get_cached_stock_metadata(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached stock metadata from Redis"""
        key = f"stock_metadata:{symbol}"
        return await self.redis.get(key)
    
    async def cache_technical_data(self, symbol: str, interval: str, data: Dict[str, Any], expire: int = 1800):
        """Cache technical data in Redis"""
        key = f"technical_data:{symbol}:{interval}"
        await self.redis.set(key, data, expire)
    
    async def get_cached_technical_data(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get cached technical data from Redis"""
        key = f"technical_data:{symbol}:{interval}"
        return await self.redis.get(key)
    
    async def cache_real_time_price(self, symbol: str, price_data: Dict[str, Any], expire: int = 60):
        """Cache real-time price data"""
        key = f"realtime_price:{symbol}"
        await self.redis.set(key, price_data, expire)
    
    async def get_cached_real_time_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached real-time price data"""
        key = f"realtime_price:{symbol}"
        return await self.redis.get(key)
    
    async def invalidate_stock_cache(self, symbol: str):
        """Invalidate all cache entries for a stock"""
        patterns = [
            f"stock_metadata:{symbol}",
            f"technical_data:{symbol}:*",
            f"realtime_price:{symbol}"
        ]
        
        for pattern in patterns:
            keys = await self.redis.get_keys(pattern)
            if keys:
                await self.redis.redis.delete(*keys)

# Global Redis instance
redis_db = RedisDatabase()
cache_manager = StockCacheManager(redis_db)
