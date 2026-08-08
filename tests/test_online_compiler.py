import os
import pytest
from app.models.session import Session
from app.models.student import Student
from app.models.code_execution import CodeExecution
from app.services.compiler_service import (
    OnlineCompilerService, OnlineCompilerProvider, CompilerProvider
)

class MockTestCompilerProvider(CompilerProvider):
    """Custom Mock Provider for deterministic unit testing."""
    def __init__(self, mode="success"):
        self.mode = mode

    def execute(self, language: str, code: str, stdin: str = "") -> dict:
        if self.mode == "timeout":
            return {
                "success": False,
                "error_code": "COMPILER_TIMEOUT",
                "error": "Execution timed out after 35 seconds"
            }
        elif self.mode == "unavailable":
            return {
                "success": False,
                "error_code": "COMPILER_UNAVAILABLE",
                "error": "Online compiler is temporarily unavailable"
            }
        elif self.mode == "rate_limit":
            return {
                "success": False,
                "error_code": "COMPILER_RATE_LIMIT",
                "error": "Online compiler rate limit hit. Please retry shortly."
            }
        elif self.mode == "auth_error":
            return {
                "success": False,
                "error_code": "COMPILER_AUTH_ERROR",
                "error": "Compiler service authorization failed"
            }
        elif self.mode == "compilation_error":
            return {
                "success": True,
                "status": "compilation_error",
                "output": "",
                "error": "SyntaxError: error",
                "exit_code": 1,
                "execution_time": "0.01s",
                "memory": "5MB",
                "language": language
            }
        elif self.mode == "runtime_error":
            return {
                "success": True,
                "status": "runtime_error",
                "output": "",
                "error": "ZeroDivisionError: division by zero",
                "exit_code": 1,
                "execution_time": "0.02s",
                "memory": "8MB",
                "language": language
            }

        # Default success mode
        out = f"Hello {language.upper()} Output\n"
        if stdin:
            out += f"Input: {stdin}\n"
        return {
            "success": True,
            "status": "success",
            "output": out,
            "error": "",
            "exit_code": 0,
            "signal": None,
            "execution_time": "0.05s",
            "total_time": "0.05s",
            "memory": "12MB",
            "language": language
        }

    def get_supported_compilers(self) -> list:
        return ["python-3.14", "gcc-15", "openjdk-25"]

    def health_check(self) -> dict:
        return {
            "status": "healthy",
            "provider": "OnlineCompiler.io",
            "message": "Mock provider active"
        }

# ------------------------------------------------------------------------------
# 1. PROVIDER ABSTRACTION & UNIT TESTS
# ------------------------------------------------------------------------------

def test_python_execution(app):
    """1. Test Python execution engine via provider."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("python", "print('Hello Python')")
    assert res["success"] is True
    assert res["status"] == "success"
    assert "PYTHON" in res["output"]

def test_c_execution(app):
    """2. Test C compilation and execution via provider."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("c", '#include <stdio.h>\nint main() { printf("Hello C"); return 0; }')
    assert res["success"] is True
    assert res["status"] == "success"
    assert "C" in res["output"]

def test_java_execution(app):
    """3. Test Java compilation and execution via provider."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("java", 'public class Main { public static void main(String[] a) {} }')
    assert res["success"] is True
    assert res["status"] == "success"
    assert "JAVA" in res["output"]

def test_python_stdin(app):
    """4. Test Python stdin handling."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("python", "name = input()", stdin="Alice")
    assert res["success"] is True
    assert "Alice" in res["output"]

def test_c_stdin(app):
    """5. Test C stdin handling."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("c", 'scanf("%s", buf);', stdin="Bob")
    assert res["success"] is True
    assert "Bob" in res["output"]

def test_java_stdin(app):
    """6. Test Java stdin handling."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("java", 'Scanner sc = new Scanner(System.in);', stdin="Charlie")
    assert res["success"] is True
    assert "Charlie" in res["output"]

def test_successful_execution(app):
    """7. Test successful execution normalization."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.execute_code("python", "print('Success')")
    assert res["success"] is True
    assert "execution_time" in res
    assert "memory" in res

def test_compilation_error_handling(app):
    """8. Test compilation error normalization."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("compilation_error"))
    res = OnlineCompilerService.execute_code("python", "def invalid_syntax(")
    assert res["success"] is True
    assert res["status"] == "compilation_error"
    assert res["exit_code"] == 1
    assert "SyntaxError" in res["error"]

def test_runtime_error_handling(app):
    """9. Test runtime error normalization."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("runtime_error"))
    res = OnlineCompilerService.execute_code("python", "x = 1 / 0")
    assert res["success"] is True
    assert res["status"] == "runtime_error"
    assert "ZeroDivisionError" in res["error"]

def test_invalid_language_rejection(app):
    """10. Test rejection of unsupported language."""
    res = OnlineCompilerService.execute_code("brainfuck", "++++")
    assert res["success"] is False
    assert res["error_code"] == "UNSUPPORTED_LANGUAGE"

def test_code_too_large_rejection(app):
    """11. Test code payload size limit rejection (>100KB)."""
    huge_code = "print('X')\n" * 15000
    res = OnlineCompilerService.execute_code("python", huge_code)
    assert res["success"] is False
    assert res["error_code"] == "CODE_TOO_LARGE"

def test_input_too_large_rejection(app):
    """12. Test input payload size limit rejection (>100KB)."""
    huge_stdin = "data\n" * 25000
    res = OnlineCompilerService.execute_code("python", "print(1)", stdin=huge_stdin)
    assert res["success"] is False
    assert res["error_code"] == "INPUT_TOO_LARGE"

def test_compiler_timeout_handling(app):
    """17. Test compiler timeout error normalization."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("timeout"))
    res = OnlineCompilerService.execute_code("python", "while True: pass")
    assert res["success"] is False
    assert res["error_code"] == "COMPILER_TIMEOUT"

def test_provider_unavailable_handling(app):
    """18. Test third-party provider unavailable error handling."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("unavailable"))
    res = OnlineCompilerService.execute_code("python", "print(1)")
    assert res["success"] is False
    assert res["error_code"] == "COMPILER_UNAVAILABLE"

def test_rate_limit_handling(app):
    """19. Test HTTP 429 rate limit error handling."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("rate_limit"))
    res = OnlineCompilerService.execute_code("python", "print(1)")
    assert res["success"] is False
    assert res["error_code"] == "COMPILER_RATE_LIMIT"

def test_api_key_missing_or_auth_error(app):
    """20. Test missing/invalid API key authorization error."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("auth_error"))
    res = OnlineCompilerService.execute_code("python", "print(1)")
    assert res["success"] is False
    assert res["error_code"] == "COMPILER_AUTH_ERROR"

def test_compiler_health_check(app):
    """21. Test health check endpoint reporting for OnlineCompiler."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = OnlineCompilerService.health_check()
    assert res["status"] == "healthy"
    assert res["provider"] == "OnlineCompiler.io"

# ------------------------------------------------------------------------------
# 2. REST API EXECUTION TESTS
# ------------------------------------------------------------------------------

def test_student_code_run_api_success(client, db):
    """Test POST /api/student/session/{session_id}/code/run endpoint."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Run",
        "teacher_email": "run@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Python",
        "title": "Run Session",
        "language": "python",
        "mode": "practice"
    })
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Runner",
        "roll_number": "RUN_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = j_res.get_json()["data"]["student_token"]
    student_id = j_res.get_json()["data"]["student"]["id"]

    run_res = client.post(
        f"/api/v1/student/session/{session_id}/code/run",
        json={"language": "python", "code": "print('Run Test')", "stdin": ""},
        headers={"X-Student-Token": s_token}
    )
    assert run_res.status_code == 200
    json_data = run_res.get_json()
    assert json_data["success"] is True
    assert "output" in json_data["data"]

    # Verify CodeExecution log created in DB
    exec_record = CodeExecution.query.filter_by(student_id=student_id).first()
    assert exec_record is not None
    assert exec_record.language == "python"

def test_student_code_run_unauthorized(client):
    """13. Test unauthorized student token check."""
    response = client.post("/api/v1/student/session/1/code/run", json={"code": "print(1)"})
    assert response.status_code == 401

def test_student_code_run_ended_session(client, db):
    """15. Test execution rejection on ended session."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. End",
        "teacher_email": "end@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "C",
        "title": "End Session",
        "language": "c",
        "mode": "practice"
    })
    t_token = s_res.get_json()["data"]["teacher_token"]
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Student",
        "roll_number": "END_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = j_res.get_json()["data"]["student_token"]

    # Teacher ends session
    client.post(f"/api/v1/teacher/session/{session_id}/end", headers={"X-Teacher-Token": t_token})

    # Student attempts run -> HTTP 400 SESSION_INACTIVE
    run_res = client.post(
        f"/api/v1/student/session/{session_id}/code/run",
        json={"language": "c", "code": "int main() {}"},
        headers={"X-Student-Token": s_token}
    )
    assert run_res.status_code == 400
    assert run_res.get_json()["error"]["code"] == "SESSION_INACTIVE"

# ------------------------------------------------------------------------------
# 3. SOCKET.IO EVENTS & BROADCAST TESTS
# ------------------------------------------------------------------------------

def test_socket_run_code_and_compiler_events(socket_client, app, db):
    """22, 23, 24. Test Socket.IO run_code event and compiler_started/completed broadcasts."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))

    s_res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Socket",
        "teacher_email": "sock@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Java",
        "title": "Socket Session",
        "language": "java",
        "mode": "practice"
    })
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Socket Coder",
        "roll_number": "SOCK_RUN_01",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    student_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": session_id, "student_id": student_id})
    socket_client.get_received() # Clear join broadcasts

    # Emit run_code
    socket_client.emit("run_code", {
        "session_id": session_id,
        "student_id": student_id,
        "language": "java",
        "code": "public class Main { public static void main(String[] a) {} }",
        "stdin": ""
    })

    received = socket_client.get_received()
    assert len(received) >= 2
    event_names = [r["name"] for r in received]
    
    assert "compiler_started" in event_names
    assert "execution_result" in event_names or "compiler_completed" in event_names

    # Check compiler_started payload
    start_evt = [r for r in received if r["name"] == "compiler_started"][0]
    assert start_evt["args"][0]["student_id"] == student_id
    assert start_evt["args"][0]["language"] == "java"

    # Check compiler_completed payload
    comp_evt = [r for r in received if r["name"] == "compiler_completed"][0]
    assert comp_evt["args"][0]["student_id"] == student_id
    assert comp_evt["args"][0]["status"] == "success"

# ------------------------------------------------------------------------------
# 4. OPTIONAL LIVE INTEGRATION TEST
# ------------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("ONLINE_COMPILER_INTEGRATION_TEST"), reason="Skipping live API integration test unless ONLINE_COMPILER_INTEGRATION_TEST=true")
def test_live_online_compiler_integration(app):
    """Optional live integration test against OnlineCompiler.io REST API."""
    provider = OnlineCompilerProvider()
    res = provider.execute("python", "print('Hello Live OnlineCompiler')")
    assert res["success"] is True
    assert "Hello Live OnlineCompiler" in res["output"]
