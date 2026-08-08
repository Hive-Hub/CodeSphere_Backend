from app.extensions import celery_app
from app.ai.ai_service import AIService
from app.logger import celery_logger, error_logger

@celery_app.task(name="app.tasks.ai_tasks.analyze_code_task", bind=True, max_retries=2)
def analyze_code_task(self, session_id: int, student_id: int):
    """Celery background task for AI code analysis."""
    try:
        celery_logger.info(f"Executing analyze_code_task for student {student_id} in session {session_id}")
        result = AIService.analyze_student_code(session_id, student_id)
        return result
    except Exception as e:
        error_logger.error(f"Error in analyze_code_task: {str(e)}")
        raise self.retry(exc=e, countdown=5)

@celery_app.task(name="app.tasks.ai_tasks.analyze_progress_task", bind=True, max_retries=2)
def analyze_progress_task(self, session_id: int, student_id: int):
    """Celery background task for AI progress estimation."""
    try:
        celery_logger.info(f"Executing analyze_progress_task for student {student_id} in session {session_id}")
        result = AIService.estimate_progress(session_id, student_id)
        return result
    except Exception as e:
        error_logger.error(f"Error in analyze_progress_task: {str(e)}")
        raise self.retry(exc=e, countdown=5)

@celery_app.task(name="app.tasks.ai_tasks.analyze_error_task", bind=True, max_retries=2)
def analyze_error_task(self, session_id: int, student_id: int, compiler_output: str):
    """Celery background task for AI compiler error analysis."""
    try:
        celery_logger.info(f"Executing analyze_error_task for student {student_id} in session {session_id}")
        result = AIService.analyze_compiler_error(session_id, student_id, compiler_output)
        return result
    except Exception as e:
        error_logger.error(f"Error in analyze_error_task: {str(e)}")
        raise self.retry(exc=e, countdown=5)

@celery_app.task(name="app.tasks.ai_tasks.generate_hint_task", bind=True, max_retries=2)
def generate_hint_task(self, session_id: int, student_id: int):
    """Celery background task for AI hint generation."""
    try:
        celery_logger.info(f"Executing generate_hint_task for student {student_id} in session {session_id}")
        result = AIService.generate_student_hint(session_id, student_id)
        return result
    except Exception as e:
        error_logger.error(f"Error in generate_hint_task: {str(e)}")
        raise self.retry(exc=e, countdown=5)

@celery_app.task(name="app.tasks.ai_tasks.detect_stuck_student_task", bind=True, max_retries=2)
def detect_stuck_student_task(self, session_id: int, student_id: int):
    """Celery background task for stuck student detection."""
    try:
        celery_logger.info(f"Executing detect_stuck_student_task for student {student_id} in session {session_id}")
        result = AIService.detect_stuck_student(session_id, student_id)
        return result
    except Exception as e:
        error_logger.error(f"Error in detect_stuck_student_task: {str(e)}")
        raise self.retry(exc=e, countdown=5)
