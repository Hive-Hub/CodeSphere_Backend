import os
from flask import Flask
from app.config import get_config
from app.extensions import (
    db, jwt, cors, limiter, migrate, socketio, celery_app, init_celery
)
from app.logger import setup_loggers
from app.utils.errors import register_error_handlers
from app.api import api_bp
import app.websockets # Import Socket.IO handlers

def create_app(config_name=None):
    """Application Factory for CodeSphere AI Backend."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    config_cls = get_config(config_name)
    app.config.from_object(config_cls)
    
    # Initialize Loggers
    setup_loggers(app)

    # Initialize Extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ALLOWED_ORIGINS"]}})
    limiter.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Initialize Celery with Flask app context
    init_celery(app)

    # Register Blueprints & Namespaces
    from app.api import api_bp, api_legacy_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(api_legacy_bp)

    # Register Centralized Error Handlers
    register_error_handlers(app)

    # Startup Configuration Check
    from app.utils.config_validation import validate_config
    validate_config(app)

    # Ensure tables exist in app context
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"Database table creation skipped/deferred: {str(e)}")

    return app
