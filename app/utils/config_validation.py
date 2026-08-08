import os
from app.logger import api_logger

def validate_config(app):
    """Validate environment configuration at application startup without exposing secret values."""
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL")
    redis_url = app.config.get("REDIS_URL") or os.getenv("REDIS_URL")
    compiler_key = app.config.get("ONLINE_COMPILER_API_KEY") or os.getenv("ONLINE_COMPILER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    db_status = "PASS" if db_url else "WARN (Using SQLite)"
    redis_status = "PASS" if redis_url else "WARN (Redis fallback)"
    compiler_status = "PASS" if compiler_key else "WARN (Missing API Key)"
    ai_status = "PASS" if (openai_key or gemini_key) else "WARN (Mock AI Mode)"

    api_logger.info("==========================================")
    api_logger.info("CONFIGURATION CHECK")
    api_logger.info(f"Database: {db_status}")
    api_logger.info(f"Redis: {redis_status}")
    api_logger.info(f"OnlineCompiler: {compiler_status}")
    api_logger.info(f"AI Service (OpenAI/Gemini): {ai_status}")
    api_logger.info("==========================================")

    return {
        "database": db_status,
        "redis": redis_status,
        "online_compiler": compiler_status,
        "ai_service": ai_status
    }
