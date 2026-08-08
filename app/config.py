import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Config:
    """Base configuration settings."""
    SECRET_KEY = os.getenv("SECRET_KEY", "codesphere-default-dev-secret-key-change-in-prod")
    
    # JWT & Session Expiry
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "codesphere-default-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 60))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 30))
    )
    SESSION_COOKIE_MAX_AGE = int(os.getenv("SESSION_COOKIE_MAX_AGE_SECONDS", 86400))
    
    # Database Settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql://postgres:Sekh%402026@db.fsekrxkesaukfojpeecn.supabase.co:5432/postgres"
    )
    
    # Supabase Settings
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fsekrxkesaukfojpeecn.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "mock-supabase-key")
    
    # Redis & Celery
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    
    # Online Code Compiler API (OnlineCompiler.io REST API)
    ONLINE_COMPILER_API_KEY = os.getenv("ONLINE_COMPILER_API_KEY", "")
    ONLINE_COMPILER_BASE_URL = os.getenv("ONLINE_COMPILER_BASE_URL", "https://api.onlinecompiler.io")
    ONLINE_COMPILER_TIMEOUT = int(os.getenv("ONLINE_COMPILER_TIMEOUT", 35))
    
    # AI Integration Configuration (Google AI Studio Gemini, Groq & OpenAI)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Reporting & Export Configuration
    REPORT_EXPORT_DIR = os.getenv("REPORT_EXPORT_DIR", "./exports/reports")
    REPORT_MAX_ROWS = int(os.getenv("REPORT_MAX_ROWS", 50000))
    REPORT_RETENTION_DAYS = int(os.getenv("REPORT_RETENTION_DAYS", 90))
    
    # Security & CORS
    CORS_ALLOWED_ORIGINS = [
        o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",") if o.strip()
    ]
    RATELIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "200 per day;50 per hour")


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DEV_DATABASE_URL", "sqlite:///codesphere_dev.db"
    )


class TestingConfig(Config):
    """Testing environment configuration."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    
    @classmethod
    def init_app(cls, app):
        assert os.getenv("SECRET_KEY"), "SECRET_KEY must be set in Production!"
        assert os.getenv("DATABASE_URL"), "DATABASE_URL must be set in Production!"


def get_config(env_name=None):
    """Retrieve configuration object based on environment name."""
    if env_name is None:
        env_name = os.getenv("FLASK_ENV", "development")
    
    env_map = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
        "dev": DevelopmentConfig,
        "test": TestingConfig,
        "prod": ProductionConfig,
    }
    return env_map.get(env_name.lower(), DevelopmentConfig)
