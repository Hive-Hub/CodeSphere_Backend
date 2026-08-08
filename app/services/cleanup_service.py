from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.activity_event import ActivityEvent
from app.models.code_execution import CodeExecution
from app.models.ai_review import AIReview
from app.services.redis_service import get_redis_client
from app.logger import api_logger, error_logger

class CleanupService:
    """Safe Session Cleanup Service."""

    @classmethod
    def cleanup_session(cls, session_id: int) -> bool:
        """Purge all session database records and Redis keys AFTER successful report generation."""
        session = Session.query.get(session_id)
        if not session:
            return False

        try:
            # 1. Fetch student IDs for Redis key cleanup
            students = Student.query.filter_by(session_id=session_id).all()
            student_ids = [s.id for s in students]

            # 2. Delete database records in child-to-parent order
            AIReview.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            CodeExecution.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            ActivityEvent.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            CodeSnapshot.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            Problem.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            Student.query.filter_by(session_id=session_id).delete(synchronize_session=False)

            # Mark session status as deleted & purge
            db.session.delete(session)
            db.session.commit()

            # 3. Purge Redis session & student keys
            try:
                r = get_redis_client()
                
                # Redis session sets & hashes
                session_patterns = [
                    f"session:{session_id}:online_students",
                    f"session:{session_id}:typing_students",
                    f"session:{session_id}:running_students",
                    f"session:{session_id}:report_status"
                ]
                for key in session_patterns:
                    r.delete(key)

                # Redis student keys
                for st_id in student_ids:
                    r.delete(f"student:{st_id}:code")
                    r.delete(f"student:{st_id}:cursor")
                    r.delete(f"student:{st_id}:typing")
                    r.delete(f"student:{st_id}:last_active")

            except Exception as re:
                error_logger.warning(f"Redis cleanup warning for session {session_id}: {str(re)}")

            api_logger.info(f"Session {session_id} successfully cleaned up")
            return True

        except Exception as e:
            db.session.rollback()
            error_logger.error(f"Failed to cleanup session {session_id}: {str(e)}")
            return False
