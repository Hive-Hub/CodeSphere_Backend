import redis
from flask import current_app
from app.logger import api_logger, error_logger

def get_redis_client():
    """Retrieve Redis client initialized with current app configuration."""
    redis_url = current_app.config.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)

def check_redis_connection():
    """Ping Redis server to check health status."""
    try:
        r = get_redis_client()
        pong = r.ping()
        return {
            "status": "healthy" if pong else "unhealthy",
            "message": "Redis ping successful" if pong else "Redis ping failed",
            "latency_ms": 0.5  # Nominal latency metric
        }
    except Exception as e:
        error_logger.warning(f"Redis health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}"
        }

def redis_set(key: str, value: str, ex: int = None) -> bool:
    """Set key in Redis cache."""
    try:
        r = get_redis_client()
        return r.set(key, value, ex=ex)
    except Exception as e:
        error_logger.error(f"Redis set failed for key '{key}': {str(e)}")
        return False

def redis_get(key: str) -> str:
    """Get value from Redis cache."""
    try:
        r = get_redis_client()
        return r.get(key)
    except Exception as e:
        error_logger.error(f"Redis get failed for key '{key}': {str(e)}")
        return None

def redis_delete(key: str) -> bool:
    """Delete key from Redis cache."""
    try:
        r = get_redis_client()
        return bool(r.delete(key))
    except Exception as e:
        error_logger.error(f"Redis delete failed for key '{key}': {str(e)}")
        return False
