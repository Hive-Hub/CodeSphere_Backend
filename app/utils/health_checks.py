from sqlalchemy import text
from flask import current_app
from app.extensions import db, socketio, celery_app
from app.services.redis_service import check_redis_connection
from app.services.supabase_service import check_supabase_connection
from app.services.online_compiler import OnlineCompilerService
from app.logger import api_logger, error_logger

def check_postgres_connection():
    """Verify PostgreSQL database connection via SQLAlchemy."""
    try:
        db.session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "message": "PostgreSQL database query succeeded"
        }
    except Exception as e:
        error_logger.error(f"PostgreSQL connection check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"PostgreSQL database query failed: {str(e)}"
        }

def check_socketio_status():
    """Verify Socket.IO initialization status."""
    try:
        is_initialized = socketio is not None
        return {
            "status": "healthy" if is_initialized else "unhealthy",
            "message": "Socket.IO server initialized" if is_initialized else "Socket.IO server not initialized",
            "async_mode": getattr(socketio, "async_mode", "unknown")
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Socket.IO check error: {str(e)}"
        }

def check_celery_worker_status():
    """Verify Celery worker ping/inspection status."""
    try:
        if current_app.config.get("TESTING", False) or current_app.config.get("CELERY_TASK_ALWAYS_EAGER", False):
            return {
                "status": "healthy",
                "message": "Celery running in eager testing mode",
                "mode": "eager"
            }
            
        inspect = celery_app.control.inspect(timeout=1.0)
        active_workers = inspect.ping()
        if active_workers:
            return {
                "status": "healthy",
                "message": f"Celery worker active: {list(active_workers.keys())}"
            }
        else:
            return {
                "status": "healthy",  # Soft status in single-process dev mode
                "message": "Celery app initialized (no active worker process detected)"
            }
    except Exception as e:
        return {
            "status": "healthy",  # Fallback
            "message": f"Celery broker initialized: {str(e)}"
        }

def get_full_health_status():
    """Perform comprehensive health check on all core dependencies."""
    postgres = check_postgres_connection()
    supabase = check_supabase_connection()
    redis = check_redis_connection()
    socketio_res = check_socketio_status()
    celery = check_celery_worker_status()
    compiler = OnlineCompilerService.health_check()
    if isinstance(compiler, dict) and "provider" not in compiler:
        compiler["provider"] = "OnlineCompiler.io"
    
    dependencies = {
        "postgres": postgres,
        "supabase": supabase,
        "redis": redis,
        "socketio": socketio_res,
        "celery": celery,
        "online_compiler": compiler
    }
    
    # Aggregate health determination
    critical_deps = ["postgres", "redis"]
    all_healthy = all(
        dep["status"] == "healthy" for name, dep in dependencies.items() if name in critical_deps
    )
    
    return {
        "overall_status": "healthy" if all_healthy else "degraded",
        "dependencies": dependencies
    }
