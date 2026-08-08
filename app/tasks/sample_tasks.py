from app.extensions import celery_app
from app.services.online_compiler import OnlineCompilerService
from app.logger import celery_logger

@celery_app.task(name="app.tasks.sample_tasks.ping_task")
def ping_task(message="ping"):
    """Sample background ping task for Celery worker verification."""
    celery_logger.info(f"Processing ping task with message: {message}")
    return {"status": "SUCCESS", "response": f"pong: {message}"}

@celery_app.task(name="app.tasks.sample_tasks.execute_code_async")
def execute_code_async(language: str, code: str, stdin: str = ""):
    """Asynchronous code execution background task."""
    celery_logger.info(f"Executing async code task for language: {language}")
    result = OnlineCompilerService.execute_code(language, code, stdin)
    return result
