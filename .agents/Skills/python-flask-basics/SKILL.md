---
name: python-flask-basics
description: Core architecture standards, application factory pattern, modular Blueprint structures, and configuration management for Python Flask backend applications.
---

# Python Flask Application Basics

This skill provides architectural guidelines and code patterns for building maintainable, enterprise-ready Python Flask backend applications.

## 1. Project Directory Structure

Use a modular, blueprint-driven project directory structure:

```text
c:\projects\CodeSphere_Backend\
├── app/
│   ├── __init__.py           # Application Factory (create_app)
│   ├── config.py             # Configuration classes (Dev, Test, Prod)
│   ├── extensions.py         # Third-party extensions initialization (db, jwt, cors)
│   ├── blueprints/           # Feature Blueprints
│   │   ├── __init__.py
│   │   ├── auth/             # Auth blueprint
│   │   │   ├── routes.py
│   │   │   └── services.py
│   │   └── api/              # API blueprint
│   ├── models/               # SQLAlchemy Models
│   ├── schemas/              # Request/Response Validation Schemas
│   └── utils/                # Utility helpers & custom middleware
├── tests/                    # Pytest test suite
├── migrations/               # Alembic database migrations
├── .env.example              # Environment variable template
├── config.py
├── wsgi.py                   # Entrypoint for WSGI server (gunicorn/uwsgi)
└── requirements.txt
```

---

## 2. Application Factory Pattern

Always construct the Flask application using the **Application Factory** pattern (`create_app`). Do not instantiate global `app` objects at module import time.

### `app/__init__.py`
```python
import os
from flask import Flask
from app.config import get_config
from app.extensions import db, jwt, cors, migrate

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_CONFIG", "development")

    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Initialize Extensions
    init_extensions(app)

    # Register Blueprints
    register_blueprints(app)

    # Register Error Handlers & Teardowns
    register_error_handlers(app)

    return app

def init_extensions(app):
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app)
    migrate.init_app(app, db)

def register_blueprints(app):
    from app.blueprints.auth import auth_bp
    from app.blueprints.health import health_bp
    
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
```

---

## 3. Configuration Management

Separate configuration into environment-specific classes loaded via environment variables.

### `app/config.py`
```python
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URL", "sqlite:///dev.db"
    )

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    
    @classmethod
    def init_app(cls, app):
        assert os.getenv("SECRET_KEY"), "SECRET_KEY environment variable is required in Production!"

def get_config(env_name):
    configs = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig
    }
    return configs.get(env_name, DevelopmentConfig)
```

---

## 4. Extension Initialization

Keep extensions decoupled in `app/extensions.py` to prevent circular dependencies.

### `app/extensions.py`
```python
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate

db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()
migrate = Migrate()
```

---

## 5. WSGI Entrypoint

### `wsgi.py`
```python
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```
