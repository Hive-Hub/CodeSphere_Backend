from app.extensions import celery_app
from app.services.report_v2_service import ReportV2Service
from app.logger import api_logger, error_logger

@celery_app.task(name="app.tasks.report_tasks.generate_report_job_async", bind=True)
def generate_report_job_async(self, job_id: str):
    """Celery background task to process PDF & Excel report job."""
    try:
        job = ReportV2Service.execute_report_job(job_id)
        if job and job.status == "ready":
            return {"status": "success", "job_id": job_id}
        else:
            return {"status": "failed", "job_id": job_id, "error": job.error_message if job else "Job not found"}
    except Exception as e:
        error_logger.error(f"Async report task failed for job {job_id}: {str(e)}")
        return {"status": "error", "error": str(e)}
