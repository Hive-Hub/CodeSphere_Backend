import os
import redis
from flask import current_app
from app.logger import api_logger, error_logger

_redis_pool = None

def get_redis_pool():
    """Retrieve or create singleton Redis ConnectionPool."""
    global _redis_pool
    if _redis_pool is None:
        try:
            if current_app:
                redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
            else:
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            
            ssl_kwargs = {}
            if redis_url.startswith("rediss://"):
                ssl_kwargs["ssl_cert_reqs"] = None

            _redis_pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=50,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
                decode_responses=True,
                **ssl_kwargs
            )
        except Exception as e:
            error_logger.error(f"Failed to create Redis connection pool: {str(e)}")
            return None
    return _redis_pool

def get_redis_client():
    """Retrieve Redis client from connection pool."""
    pool = get_redis_pool()
    if pool:
        return redis.Redis(connection_pool=pool)
    # Fallback to direct client if pool fails
    try:
        redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0") if current_app else "redis://localhost:6379/0"
        return redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=5.0, socket_connect_timeout=5.0)
    except Exception as e:
        error_logger.error(f"Failed to create Redis fallback client: {str(e)}")
        return None

def check_redis_connection():
    """Ping Redis server to check health status without throwing exceptions."""
    try:
        r = get_redis_client()
        if r is None:
            return {"status": "unhealthy", "message": "Redis pool unavailable"}
        pong = r.ping()
        return {
            "status": "healthy" if pong else "unhealthy",
            "message": "Redis ping successful" if pong else "Redis ping failed",
            "latency_ms": 0.5
        }
    except Exception as e:
        error_logger.warning(f"Redis health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }

def redis_set(key: str, value: str, ex: int = None) -> bool:
    """Set key in Redis cache with optional TTL (ex seconds)."""
    try:
        r = get_redis_client()
        if r is None: return False
        return bool(r.set(key, value, ex=ex))
    except Exception as e:
        error_logger.error(f"Redis set failed for key '{key}': {str(e)}")
        return False

def redis_get(key: str) -> str:
    """Get value from Redis cache."""
    try:
        r = get_redis_client()
        if r is None: return None
        return r.get(key)
    except Exception as e:
        error_logger.error(f"Redis get failed for key '{key}': {str(e)}")
        return None

def redis_delete(key: str) -> bool:
    """Delete key from Redis cache."""
    try:
        r = get_redis_client()
        if r is None: return False
        return bool(r.delete(key))
    except Exception as e:
        error_logger.error(f"Redis delete failed for key '{key}': {str(e)}")
        return False

def redis_expire(key: str, seconds: int) -> bool:
    """Set TTL expiration for key."""
    try:
        r = get_redis_client()
        if r is None: return False
        return bool(r.expire(key, seconds))
    except Exception as e:
        error_logger.error(f"Redis expire failed for key '{key}': {str(e)}")
        return False

def redis_hset(name: str, key: str, value: str) -> bool:
    """Set field in Redis hash."""
    try:
        r = get_redis_client()
        if r is None: return False
        r.hset(name, key, value)
        return True
    except Exception as e:
        error_logger.error(f"Redis hset failed for hash '{name}': {str(e)}")
        return False

def redis_hget(name: str, key: str) -> str:
    """Get field from Redis hash."""
    try:
        r = get_redis_client()
        if r is None: return None
        return r.hget(name, key)
    except Exception as e:
        error_logger.error(f"Redis hget failed for hash '{name}': {str(e)}")
        return None

def redis_hgetall(name: str) -> dict:
    """Get all fields from Redis hash."""
    try:
        r = get_redis_client()
        if r is None: return {}
        return r.hgetall(name) or {}
    except Exception as e:
        error_logger.error(f"Redis hgetall failed for hash '{name}': {str(e)}")
        return {}

def redis_sadd(name: str, *values) -> bool:
    """Add members to Redis set."""
    try:
        r = get_redis_client()
        if r is None: return False
        r.sadd(name, *values)
        return True
    except Exception as e:
        error_logger.error(f"Redis sadd failed for set '{name}': {str(e)}")
        return False

def redis_srem(name: str, *values) -> bool:
    """Remove members from Redis set."""
    try:
        r = get_redis_client()
        if r is None: return False
        r.srem(name, *values)
        return True
    except Exception as e:
        error_logger.error(f"Redis srem failed for set '{name}': {str(e)}")
        return False

def redis_smembers(name: str) -> set:
    """Get all members from Redis set."""
    try:
        r = get_redis_client()
        if r is None: return set()
        return r.smembers(name) or set()
    except Exception as e:
        error_logger.error(f"Redis smembers failed for set '{name}': {str(e)}")
        return set()
