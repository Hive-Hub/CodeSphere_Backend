from app.extensions import celery_app
from app.services.code_service import save_code_snapshot, get_student_live_code
from app.models.code_snapshot import CodeSnapshot
from app.logger import celery_logger

@celery_app.task(name="app.tasks.code_tasks.persist_debounced_code_snapshot")
def persist_debounced_code_snapshot(session_id: int, student_id: int, language: str, code: str = None):
    """Background task to save debounced code snapshot 3-5s after last student keystroke."""
    celery_logger.info(f"Processing debounced snapshot task for student {student_id} in session {session_id}")
    try:
        # If code not explicitly passed, fetch latest live code from Redis
        if code is None:
            code = get_student_live_code(student_id)

        if not code:
            return {"status": "SKIPPED", "reason": "Empty code payload"}

        # Compare with latest saved DB snapshot to avoid duplicate versions
        latest = CodeSnapshot.query.filter_by(
            session_id=session_id, student_id=student_id
        ).order_by(CodeSnapshot.version.desc()).first()

        if latest and latest.code == code:
            return {"status": "SKIPPED", "reason": "Code unchanged", "version": latest.version}

        snapshot = save_code_snapshot(session_id, student_id, language, code)
        celery_logger.info(f"Saved CodeSnapshot v{snapshot.version} for student {student_id}")
        return {
            "status": "SUCCESS",
            "version": snapshot.version,
            "snapshot_id": snapshot.id
        }
    except Exception as e:
        celery_logger.error(f"Error in debounced snapshot task: {str(e)}")
        return {"status": "ERROR", "error": str(e)}
