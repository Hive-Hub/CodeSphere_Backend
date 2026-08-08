import os
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))

def setup_loggers(app=None):
    """Set up rotating file loggers for API, Socket.IO, Celery, and Errors."""
    os.makedirs(LOG_DIR, exist_ok=True)
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(filename)s:%(lineno)d]: %(message)s"
    )
    
    # Helper to build rotating handler
    def create_handler(filename, level=logging.INFO):
        file_path = os.path.join(LOG_DIR, filename)
        handler = RotatingFileHandler(
            file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler

    # 1. API Logger
    api_logger = logging.getLogger("codesphere.api")
    api_logger.setLevel(logging.INFO)
    if not api_logger.handlers:
        api_logger.addHandler(create_handler("api.log", logging.INFO))
        
    # 2. Socket.IO Logger
    socketio_logger = logging.getLogger("codesphere.socketio")
    socketio_logger.setLevel(logging.INFO)
    if not socketio_logger.handlers:
        socketio_logger.addHandler(create_handler("socketio.log", logging.INFO))
        
    # 3. Celery Logger
    celery_logger = logging.getLogger("codesphere.celery")
    celery_logger.setLevel(logging.INFO)
    if not celery_logger.handlers:
        celery_logger.addHandler(create_handler("celery.log", logging.INFO))
        
    # 4. Error Logger
    error_logger = logging.getLogger("codesphere.error")
    error_logger.setLevel(logging.ERROR)
    if not error_logger.handlers:
        error_logger.addHandler(create_handler("error.log", logging.ERROR))

    # Also attach handlers to Flask app logger if provided
    if app:
        app.logger.addHandler(create_handler("api.log", logging.INFO))
        app.logger.addHandler(create_handler("error.log", logging.ERROR))
        
    return {
        "api": api_logger,
        "socketio": socketio_logger,
        "celery": celery_logger,
        "error": error_logger,
    }

loggers = setup_loggers()
api_logger = loggers["api"]
socketio_logger = loggers["socketio"]
celery_logger = loggers["celery"]
error_logger = loggers["error"]
