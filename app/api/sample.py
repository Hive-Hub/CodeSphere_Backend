from flask import request
from flask_restx import Namespace, Resource, fields
from app.services.online_compiler import OnlineCompilerService
from app.services.redis_service import redis_set, redis_get, redis_delete
from app.services.supabase_service import test_supabase_crud
from app.models.health_log import HealthLog
from app.tasks.sample_tasks import ping_task, execute_code_async
from app.utils.response import api_response, api_error

sample_ns = Namespace("sample", description="Verification sample endpoints for Phase 0 services")

code_req_model = sample_ns.model("CodeExecutionRequest", {
    "language": fields.String(required=True, example="python", description="Language: python, c, java"),
    "code": fields.String(required=True, example="print('Hello CodeSphere')", description="Source code"),
    "stdin": fields.String(required=False, example="", description="Standard input")
})

redis_req_model = sample_ns.model("RedisTestRequest", {
    "key": fields.String(required=True, example="test_key"),
    "value": fields.String(required=True, example="test_value")
})

@sample_ns.route("/execute")
class CodeExecutionResource(Resource):
    @sample_ns.expect(code_req_model)
    def post(self):
        """Execute code synchronously via OnlineCompilerService (Python, C, Java)."""
        data = request.get_json() or {}
        language = data.get("language")
        code = data.get("code")
        stdin = data.get("stdin", "")
        
        if not language or not code:
            return api_error("Language and code fields are required", error_code="VALIDATION_ERROR", status_code=400)
            
        result = OnlineCompilerService.execute_code(language, code, stdin)
        if result.get("success"):
            return api_response(data=result, message="Code executed successfully")
        else:
            return api_error(message=result.get("error", "Code execution failed"), error_code="EXECUTION_ERROR", status_code=400)

@sample_ns.route("/redis")
class RedisTestResource(Resource):
    @sample_ns.expect(redis_req_model)
    def post(self):
        """Test Redis write and read operations."""
        data = request.get_json() or {}
        key = data.get("key", "sample_test_key")
        val = data.get("value", "sample_test_value")
        
        set_ok = redis_set(key, val, ex=300)
        retrieved_val = redis_get(key) if set_ok else None
        redis_delete(key)
        
        if set_ok and retrieved_val == val:
            return api_response(
                data={"key": key, "value": retrieved_val, "status": "verified"},
                message="Redis read/write test succeeded"
            )
        return api_error("Redis read/write test failed", error_code="REDIS_ERROR", status_code=500)

@sample_ns.route("/db")
class DatabaseCrudTestResource(Resource):
    def post(self):
        """Test PostgreSQL ORM creation and Supabase CRUD operation."""
        # 1. PostgreSQL ORM test
        log_entry = HealthLog(service_name="PostgreSQL", status="healthy", message="Sample CRUD entry")
        log_entry.save()
        log_dict = log_entry.to_dict()
        log_entry.delete()
        
        # 2. Supabase CRUD test
        supabase_res = test_supabase_crud()
        
        return api_response(
            data={
                "postgres_orm": {"status": "success", "sample_record": log_dict},
                "supabase_crud": supabase_res
            },
            message="Database & Supabase CRUD tests completed successfully"
        )

@sample_ns.route("/celery")
class CeleryTestResource(Resource):
    def post(self):
        """Trigger background Celery sample task."""
        data = request.get_json() or {}
        msg = data.get("message", "Phase 0 Verification")
        task = ping_task.delay(msg)
        
        return api_response(
            data={"task_id": task.id, "state": task.state},
            message="Celery task dispatched successfully"
        )
