from datetime import datetime, timezone
from app.extensions import celery_app, db, socketio
from app.models.session import Session
from app.services.report_service import ReportService
from app.services.cleanup_service import CleanupService
from app.logger import celery_logger, error_logger

@celery_app.task(name="app.tasks.session_tasks.check_session_expirations")
def check_session_expirations():
    """Periodic Celery task to auto-expire sessions past 24 hours, generate reports, and clean up."""
    celery_logger.info("Scanning for expired sessions...")
    now = datetime.now(timezone.utc)
    expired_count = 0

    try:
        active_sessions = Session.query.filter_by(status="active").all()
        for session in active_sessions:
            exp_time = session.expires_at
            if exp_time and exp_time.tzinfo is None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)

            if now >= exp_time:
                session.status = "expired"
                session.ended_at = now
                db.session.commit()
                expired_count += 1
                
                # Broadcast Socket.IO notification to session room
                room_name = f"session:{session.id}"
                socketio.emit("session_ended", {
                    "event": "session_ended",
                    "session_id": session.id,
                    "session_code": session.session_code,
                    "timestamp": now.isoformat(),
                    "reason": "24_hour_expired"
                }, to=room_name)

                # Generate PDF report before cleanup
                try:
                    ReportService.generate_session_report(session.id)
                except Exception as re:
                    error_logger.error(f"Automatic report generation failed for session {session.id}: {str(re)}")

        if expired_count > 0:
            celery_logger.info(f"Auto-expired {expired_count} session(s).")
    except Exception as e:
        db.session.rollback()
        error_logger.error(f"Error checking session expirations: {str(e)}")

    return {"status": "SUCCESS", "expired_count": expired_count}
