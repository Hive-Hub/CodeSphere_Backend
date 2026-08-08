from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_socketio import SocketIO
from celery import Celery

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])
socketio = SocketIO(cors_allowed_origins="*", async_mode="eventlet")
celery_app = Celery("codesphere_tasks")

def init_celery(app=None):
    """Configure Celery with Flask app context."""
    if app:
        broker_url = app.config["CELERY_BROKER_URL"]
        result_backend = app.config["CELERY_RESULT_BACKEND"]
        is_ssl = "rediss://" in broker_url
        
        celery_config = {
            "broker_url": broker_url,
            "result_backend": result_backend,
            "task_always_eager": app.config.get("CELERY_TASK_ALWAYS_EAGER", False),
            "task_eager_propagates": app.config.get("CELERY_TASK_EAGER_PROPAGATES", False),
            "accept_content": ["json"],
            "task_serializer": "json",
            "result_serializer": "json",
            "timezone": "UTC"
        }
        if is_ssl:
            celery_config["broker_use_ssl"] = {"ssl_cert_reqs": None}
            celery_config["redis_backend_use_ssl"] = {"ssl_cert_reqs": None}
            
        celery_app.conf.update(celery_config)

        class ContextTask(celery_app.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery_app.Task = ContextTask
    return celery_app
