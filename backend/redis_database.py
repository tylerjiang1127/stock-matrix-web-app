"""
Redis database connection and configuration for caching
"""

import redis.asyncio as aioredis
import json
from typing import Optional, Any, Dict
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
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
            value = json.dumps(value, default=self._json_serializer)
        
        await self.redis.set(key, value, ex=expire)
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime and other non-serializable objects"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
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
        elif isinstance(obj, (datetime, date)):
            # Handle Python datetime and date objects
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
        # Convert to serializable format to handle datetime objects and other non-serializable types
        serializable_data = self._convert_to_serializable(data)
        await self.redis.set(key, serializable_data, expire)
    
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

class SessionManager:
    """Manage user sessions in Redis"""
    
    def __init__(self, redis_db: RedisDatabase):
        self.redis = redis_db
        self.session_expire = int(os.getenv('SESSION_EXPIRE_DAYS', 7)) * 24 * 60 * 60  # Convert days to seconds
    
    async def create_session(self, user_id: str, user_data: Dict[str, Any]) -> str:
        """
        Create a new session for a user
        
        Args:
            user_id: User's UUID
            user_data: User data to store in session (username, email, etc.)
            
        Returns:
            session_id: Generated session ID
        """
        import uuid
        
        session_id = str(uuid.uuid4())
        key = f"session:{session_id}"
        
        session_data = {
            'user_id': user_id,
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'created_at': datetime.now(_ET).isoformat()
        }
        
        await self.redis.set(key, session_data, expire=self.session_expire)
        print(f"✅ Session created for user {user_id}: {session_id}")
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data by session ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data if exists and not expired, None otherwise
        """
        key = f"session:{session_id}"
        return await self.redis.get(key)
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (logout)
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        key = f"session:{session_id}"
        
        if await self.redis.exists(key):
            await self.redis.delete(key)
            print(f"✅ Session deleted: {session_id}")
            return True
        
        return False
    
    async def refresh_session(self, session_id: str) -> bool:
        """
        Refresh session expiry time
        
        Args:
            session_id: Session ID to refresh
            
        Returns:
            True if refreshed, False otherwise
        """
        key = f"session:{session_id}"
        
        if await self.redis.exists(key):
            await self.redis.expire(key, self.session_expire)
            return True
        
        return False
    
    async def delete_user_sessions(self, user_id: str) -> int:
        """
        Delete all sessions for a user
        
        Args:
            user_id: User's UUID
            
        Returns:
            Number of sessions deleted
        """
        pattern = "session:*"
        keys = await self.redis.get_keys(pattern)
        
        deleted_count = 0
        for key in keys:
            session_data = await self.redis.get(key)
            if session_data and session_data.get('user_id') == user_id:
                await self.redis.delete(key)
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"✅ Deleted {deleted_count} sessions for user {user_id}")
        
        return deleted_count


# Global Redis instance
redis_db = RedisDatabase()
cache_manager = StockCacheManager(redis_db)
session_manager = SessionManager(redis_db)