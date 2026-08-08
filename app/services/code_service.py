import json
from datetime import datetime, timezone
from flask import has_app_context
from app.extensions import db
from app.models.code_snapshot import CodeSnapshot
from app.models.activity_event import ActivityEvent
from app.services.redis_service import get_redis_client
from app.logger import api_logger, error_logger

MAX_CODE_SIZE_BYTES = 100 * 1024 # 100 KB max payload

def set_student_live_code(student_id: int, session_id: int, code: str, cursor: dict = None):
    """Store fast-changing student code and cursor position in Redis."""
    try:
        r = get_redis_client()
        code_key = f"student:{student_id}:code"
        cursor_key = f"student:{student_id}:cursor"
        activity_key = f"student:{student_id}:last_activity"
        set_key = f"session:{session_id}:active_students"

        now_str = datetime.now(timezone.utc).isoformat()

        r.set(code_key, code, ex=86400) # 24h TTL
        r.set(activity_key, now_str, ex=86400)
        r.sadd(set_key, str(student_id))

        if cursor and isinstance(cursor, dict):
            r.set(cursor_key, json.dumps(cursor), ex=86400)

        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_live_code failed for student {student_id}: {str(e)}")
        return False

def get_student_live_code(student_id: int) -> str:
    """Retrieve student's latest code from Redis or fall back to DB snapshot."""
    try:
        r = get_redis_client()
        code_key = f"student:{student_id}:code"
        code = r.get(code_key)
        if code is not None:
            return code
    except Exception as e:
        error_logger.warning(f"Redis get_student_live_code failed: {str(e)}")

    # Fallback to DB latest CodeSnapshot
    latest = CodeSnapshot.query.filter_by(student_id=student_id).order_by(CodeSnapshot.version.desc()).first()
    return latest.code if latest else ""

def get_student_live_cursor(student_id: int) -> dict:
    """Retrieve student's current cursor position from Redis."""
    try:
        r = get_redis_client()
        cursor_key = f"student:{student_id}:cursor"
        raw = r.get(cursor_key)
        if raw:
            return json.loads(raw)
    except Exception as e:
        error_logger.warning(f"Redis get_student_live_cursor failed: {str(e)}")
    return {"line": 1, "column": 1}

def set_student_typing_status(student_id: int, is_typing: bool, session_id: int = None):
    """Set student typing status in Redis and manage typing set."""
    try:
        r = get_redis_client()
        typing_key = f"student:{student_id}:typing"
        r.set(typing_key, "1" if is_typing else "0", ex=300)

        if not session_id and has_app_context():
            try:
                student = Student.query.get(student_id)
                if student:
                    session_id = student.session_id
            except Exception:
                pass

        if session_id:
            set_key = f"session:{session_id}:typing_students"
            if is_typing:
                r.sadd(set_key, str(student_id))
            else:
                r.srem(set_key, str(student_id))
        return True
    except Exception as e:
        error_logger.warning(f"Redis set_student_typing_status failed: {str(e)}")
        return False

def get_student_typing_status(student_id: int) -> bool:
    """Check if student is currently typing."""
    try:
        r = get_redis_client()
        typing_key = f"student:{student_id}:typing"
        val = r.get(typing_key)
        return val == "1"
    except Exception as e:
        return False

def save_code_snapshot(session_id: int, student_id: int, language: str, code: str):
    """Persist an incremented versioned code snapshot to PostgreSQL."""
    try:
        latest = CodeSnapshot.query.filter_by(
            session_id=session_id, student_id=student_id
        ).order_by(CodeSnapshot.version.desc()).first()

        next_version = (latest.version + 1) if latest else 1

        snapshot = CodeSnapshot(
            session_id=session_id,
            student_id=student_id,
            language=language,
            code=code,
            version=next_version
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Failed to save CodeSnapshot: {str(e)}")
        raise e

def record_activity_event(session_id: int, student_id: int, event_type: str, metadata: dict = None):
    """Record student activity event (copy, paste, tab blur, etc.) in DB."""
    try:
        event = ActivityEvent(
            session_id=session_id,
            student_id=student_id,
            event_type=event_type,
            metadata_json=json.dumps(metadata) if metadata else None
        )
        db.session.add(event)
        db.session.commit()
        return event
    except Exception as e:
        db.session.rollback()
        error_logger.warning(f"Failed to record ActivityEvent: {str(e)}")
        return None
