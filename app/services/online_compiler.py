from app.services.compiler_service import OnlineCompilerService

# Re-export for Phase 0 backward compatibility
SUPPORTED_LANGUAGES = ["python", "c", "java"]

def get_online_compiler_service():
    return OnlineCompilerService
