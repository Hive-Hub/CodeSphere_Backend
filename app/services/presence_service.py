from datetime import datetime, timezone
from app.services.redis_service import get_redis_client
from app.logger import api_logger, error_logger

PRESENCE_TTL = 3600 # 1 hour
SESSION_KEY_TTL = 86400 # 24 hours

def set_student_online(session_id: int, student_id: int, sid: str = ""):
    """Mark student online in Redis set and presence hash with TTL."""
    try:
        r = get_redis_client()
        if not r: return False
        set_key = f"session:{session_id}:online_students"
        student_key = f"student:{student_id}:presence"
        now_str = datetime.now(timezone.utc).isoformat()

        r.sadd(set_key, str(student_id))
        r.expire(set_key, SESSION_KEY_TTL)
        
        r.hset(student_key, mapping={
            "session_id": str(session_id),
            "status": "online",
            "last_active": now_str,
            "sid": sid or ""
        })
        r.expire(student_key, PRESENCE_TTL)
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_online failed: {str(e)}")
        return False

def set_student_offline(session_id: int, student_id: int):
    """Mark student offline in Redis."""
    try:
        r = get_redis_client()
        if not r: return False
        set_key = f"session:{session_id}:online_students"
        typing_set_key = f"session:{session_id}:typing_students"
        running_set_key = f"session:{session_id}:running_students"
        student_key = f"student:{student_id}:presence"
        now_str = datetime.now(timezone.utc).isoformat()

        r.srem(set_key, str(student_id))
        r.srem(typing_set_key, str(student_id))
        r.srem(running_set_key, str(student_id))
        r.hset(student_key, mapping={
            "status": "offline",
            "last_active": now_str
        })
        r.expire(student_key, PRESENCE_TTL)
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_offline failed: {str(e)}")
        return False

def get_online_student_ids(session_id: int):
    """Get set of online student IDs for a given session."""
    try:
        r = get_redis_client()
        if not r: return set()
        set_key = f"session:{session_id}:online_students"
        members = r.smembers(set_key)
        result = set()
        for m in members:
            s = m.decode('utf-8') if isinstance(m, bytes) else str(m)
            if s.isdigit():
                result.add(int(s))
        return result
    except Exception as e:
        error_logger.warning(f"Redis get_online_student_ids failed: {str(e)}")
        return set()

def get_typing_student_ids(session_id: int):
    """Get set of currently typing student IDs in a session."""
    try:
        r = get_redis_client()
        if not r: return set()
        set_key = f"session:{session_id}:typing_students"
        members = r.smembers(set_key)
        result = set()
        for m in members:
            s = m.decode('utf-8') if isinstance(m, bytes) else str(m)
            if s.isdigit():
                result.add(int(s))
        return result
    except Exception as e:
        error_logger.warning(f"Redis get_typing_student_ids failed: {str(e)}")
        return set()

def get_running_student_ids(session_id: int):
    """Get set of students currently running code in a session."""
    try:
        r = get_redis_client()
        if not r: return set()
        set_key = f"session:{session_id}:running_students"
        members = r.smembers(set_key)
        result = set()
        for m in members:
            s = m.decode('utf-8') if isinstance(m, bytes) else str(m)
            if s.isdigit():
                result.add(int(s))
        return result
    except Exception as e:
        error_logger.warning(f"Redis get_running_student_ids failed: {str(e)}")
        return set()

def set_student_running_status(session_id: int, student_id: int, is_running: bool):
    """Set running code status in Redis."""
    try:
        r = get_redis_client()
        if not r: return False
        set_key = f"session:{session_id}:running_students"
        if is_running:
            r.sadd(set_key, str(student_id))
            r.expire(set_key, SESSION_KEY_TTL)
        else:
            r.srem(set_key, str(student_id))
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_running_status failed: {str(e)}")
        return False

def get_online_count(session_id: int) -> int:
    """Get count of online students in a session."""
    try:
        r = get_redis_client()
        if not r: return 0
        set_key = f"session:{session_id}:online_students"
        return r.scard(set_key)
    except Exception as e:
        error_logger.warning(f"Redis get_online_count failed: {str(e)}")
        return 0

def update_student_heartbeat(session_id: int, student_id: int):
    """Update last_active timestamp for a student."""
    try:
        r = get_redis_client()
        if not r: return False
        student_key = f"student:{student_id}:presence"
        online_set_key = f"session:{session_id}:online_students"
        now_str = datetime.now(timezone.utc).isoformat()
        r.sadd(online_set_key, str(student_id))
        r.expire(online_set_key, SESSION_KEY_TTL)
        r.hset(student_key, mapping={
            "status": "online",
            "last_active": now_str
        })
        r.expire(student_key, PRESENCE_TTL)
        return True
    except Exception as e:
        error_logger.warning(f"Redis update_student_heartbeat failed: {str(e)}")
        return False
