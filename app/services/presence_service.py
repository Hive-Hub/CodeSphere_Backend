from datetime import datetime, timezone
from app.services.redis_service import get_redis_client
from app.logger import api_logger, error_logger

def set_student_online(session_id: int, student_id: int, sid: str = ""):
    """Mark student online in Redis set and presence hash."""
    try:
        r = get_redis_client()
        set_key = f"session:{session_id}:online_students"
        student_key = f"student:{student_id}:presence"
        now_str = datetime.now(timezone.utc).isoformat()

        # Add student_id to online set for this session
        r.sadd(set_key, str(student_id))
        
        # Set presence info
        r.hset(student_key, mapping={
            "session_id": str(session_id),
            "status": "online",
            "last_active": now_str,
            "sid": sid or ""
        })
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_online failed: {str(e)}")
        return False

def set_student_offline(session_id: int, student_id: int):
    """Mark student offline in Redis."""
    try:
        r = get_redis_client()
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
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_offline failed: {str(e)}")
        return False

def get_online_student_ids(session_id: int):
    """Get list of online student IDs for a given session."""
    try:
        r = get_redis_client()
        set_key = f"session:{session_id}:online_students"
        members = r.smembers(set_key)
        return set(int(m) for m in members if m.isdigit())
    except Exception as e:
        error_logger.warning(f"Redis get_online_student_ids failed: {str(e)}")
        return set()

def get_typing_student_ids(session_id: int):
    """Get list of currently typing student IDs in a session."""
    try:
        r = get_redis_client()
        set_key = f"session:{session_id}:typing_students"
        members = r.smembers(set_key)
        return set(int(m) for m in members if m.isdigit())
    except Exception as e:
        error_logger.warning(f"Redis get_typing_student_ids failed: {str(e)}")
        return set()

def get_running_student_ids(session_id: int):
    """Get set of students currently running code in a session."""
    try:
        r = get_redis_client()
        set_key = f"session:{session_id}:running_students"
        members = r.smembers(set_key)
        return set(int(m) for m in members if m.isdigit())
    except Exception as e:
        error_logger.warning(f"Redis get_running_student_ids failed: {str(e)}")
        return set()

def set_student_running_status(session_id: int, student_id: int, is_running: bool):
    """Set running code status in Redis."""
    try:
        r = get_redis_client()
        set_key = f"session:{session_id}:running_students"
        if is_running:
            r.sadd(set_key, str(student_id))
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
        set_key = f"session:{session_id}:online_students"
        return r.scard(set_key)
    except Exception as e:
        error_logger.warning(f"Redis get_online_count failed: {str(e)}")
        return 0

def update_student_heartbeat(session_id: int, student_id: int):
    """Update last_active timestamp for a student."""
    try:
        r = get_redis_client()
        student_key = f"student:{student_id}:presence"
        online_set_key = f"session:{session_id}:online_students"
        now_str = datetime.now(timezone.utc).isoformat()
        r.sadd(online_set_key, str(student_id))
        r.hset(student_key, mapping={
            "status": "online",
            "last_active": now_str
        })
        return True
    except Exception as e:
        error_logger.warning(f"Redis update_student_heartbeat failed: {str(e)}")
        return False
