from app.services.online_compiler import OnlineCompilerService

def test_online_compiler_python(app):
    """Test Python execution engine via OnlineCompilerService."""
    with app.app_context():
        code = "print('Hello CodeSphere Python')"
        result = OnlineCompilerService.execute_code("python", code)
        assert result["success"] is True
        assert result["language"] in ("python", "python3")
        assert "Hello" in result["output"] or "Simulated" in result["output"]

def test_online_compiler_c(app):
    """Test C execution engine via OnlineCompilerService."""
    with app.app_context():
        code = '#include <stdio.h>\nint main() { printf("Hello CodeSphere C"); return 0; }'
        result = OnlineCompilerService.execute_code("c", code)
        assert result["success"] is True
        assert result["language"] == "c"
        assert "Hello" in result["output"] or "Simulated" in result["output"]

def test_online_compiler_java(app):
    """Test Java execution engine via OnlineCompilerService."""
    with app.app_context():
        code = 'public class Main { public static void main(String[] args) { System.out.println("Hello CodeSphere Java"); } }'
        result = OnlineCompilerService.execute_code("java", code)
        assert result["success"] is True
        assert result["language"] == "java"
        assert "Hello" in result["output"] or "Simulated" in result["output"]

def test_online_compiler_unsupported_language(app):
    """Test rejection of unsupported programming languages."""
    with app.app_context():
        result = OnlineCompilerService.execute_code("ruby", "puts 'Hello'")
        assert result["success"] is False
        assert "Unsupported language" in result["error"]

def test_online_compiler_sample_endpoint(client):
    """Test POST /api/v1/sample/execute endpoint."""
    response = client.post("/api/v1/sample/execute", json={
        "language": "python",
        "code": "print('Sample Endpoint Python')"
    })
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["success"] is True
