import os
import pytest
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.ai_review import AIReview
from app.ai.ai_service import AIService
from app.ai.providers.mock_provider import MockAIProvider
from app.ai.validator import (
    validate_progress_output, validate_code_quality_output, validate_error_analysis_output
)
from app.tasks.ai_tasks import analyze_code_task, analyze_progress_task, generate_hint_task

def setup_test_session(client, mode="practice"):
    """Helper to set up a test session and student."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Dr. AI", "teacher_email": "ai@edu.com", "college": "Tech",
        "department": "CS", "subject": "AI Lab", "title": "AI Session",
        "language": "python", "mode": mode
    })
    s_data = s_res.get_json()["data"]
    t_token = s_data["teacher_token"]
    s_id = s_data["session"]["id"]
    s_code = s_data["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "AI Coder", "roll_number": "AI_001",
        "department": "CS", "year": "3rd", "section": "A"
    })
    j_data = j_res.get_json()["data"]
    st_token = j_data["student_token"]
    st_id = j_data["student"]["id"]

    return t_token, st_token, s_id, st_id

# ------------------------------------------------------------------------------
# 1. PROVIDER ABSTRACTION & VALIDATION TESTS
# ------------------------------------------------------------------------------

def test_ai_provider_abstraction(app):
    """1. Test AI provider abstraction and provider switching."""
    mock_p = MockAIProvider()
    AIService.set_provider(mock_p)
    assert AIService.get_provider() == mock_p

def test_mock_ai_provider(app):
    """2. Test MockAIProvider outputs."""
    p = MockAIProvider()
    res = p.analyze_code({}, "print('hello')", "python", "practice")
    assert "overall" in res
    assert res["overall"] == 85

def test_pydantic_output_validation(app):
    """3. Test output validation schemas."""
    # Test valid code quality
    q_data = validate_code_quality_output({"overall": 90, "logic": 9})
    assert q_data["overall"] == 90

    # Test progress low confidence null fallback
    prog_data = validate_progress_output({"progress": 80, "confidence": 30})
    assert prog_data["progress"] is None

# ------------------------------------------------------------------------------
# 2. AI SERVICE LOGIC & SAFETY TESTS
# ------------------------------------------------------------------------------

def test_code_analysis(client, db):
    """4. Test AIService code analysis."""
    AIService.set_provider(MockAIProvider())
    _, st_token, s_id, st_id = setup_test_session(client, "practice")

    # Set student code
    client.post(f"/api/v1/student/session/{s_id}/code/save",
                json={"code": "def solve(): return 42"},
                headers={"X-Student-Token": st_token})

    analysis = AIService.analyze_student_code(s_id, st_id)
    assert analysis is not None
    assert analysis["overall"] == 85

def test_progress_estimation_valid(client, db):
    """5. Test progress estimation in problem_solving mode."""
    AIService.set_provider(MockAIProvider())
    t_token, st_token, s_id, st_id = setup_test_session(client, "problem_solving")

    # Add problem
    client.post(f"/api/v1/teacher/session/{s_id}/problem", json={
        "title": "Sum Problem", "description": "Add 2 nums", "reference_solution": "def add(a,b): return a+b"
    }, headers={"X-Teacher-Token": t_token})

    client.post(f"/api/v1/student/session/{s_id}/code/save",
                json={"code": "def add(a, b): return a + b"},
                headers={"X-Student-Token": st_token})

    progress_data = AIService.estimate_progress(s_id, st_id)
    assert progress_data is not None
    assert progress_data["progress"] == 75

def test_student_hint_problem_solving_mode_restriction(client, db):
    """6. Test problem_solving mode hint safety check (no direct code solutions)."""
    AIService.set_provider(MockAIProvider())
    _, st_token, s_id, st_id = setup_test_session(client, "problem_solving")

    client.post(f"/api/v1/student/session/{s_id}/code/save",
                json={"code": "def solve(): pass"},
                headers={"X-Student-Token": st_token})

    hint_res = AIService.generate_student_hint(s_id, st_id)
    assert hint_res["hint_type"] == "conceptual"
    assert "def " not in hint_res["hint"]

def test_reference_solution_protection(client, db):
    """7. Test reference_solution is never exposed in AI response payload."""
    AIService.set_provider(MockAIProvider())
    t_token, st_token, s_id, st_id = setup_test_session(client, "problem_solving")

    ref_secret = "def TOP_SECRET_REFERENCE_SOLUTION(): return 999"
    client.post(f"/api/v1/teacher/session/{s_id}/problem", json={
        "title": "Secret Problem", "description": "Desc", "reference_solution": ref_secret
    }, headers={"X-Teacher-Token": t_token})

    hint_res = AIService.generate_student_hint(s_id, st_id)
    assert ref_secret not in str(hint_res)

def test_stuck_student_detection(client, db):
    """8. Test stuck student pattern detection."""
    AIService.set_provider(MockAIProvider())
    _, _, s_id, st_id = setup_test_session(client, "practice")

    res = AIService.detect_stuck_student(s_id, st_id)
    assert "stuck" in res

def test_redis_fingerprint_caching(client, db):
    """9. Test Redis fingerprint deduplication and caching."""
    AIService.set_provider(MockAIProvider())
    _, st_token, s_id, st_id = setup_test_session(client, "practice")

    client.post(f"/api/v1/student/session/{s_id}/code/save",
                json={"code": "print('fingerprint')"},
                headers={"X-Student-Token": st_token})

    res1 = AIService.analyze_student_code(s_id, st_id)
    res2 = AIService.analyze_student_code(s_id, st_id)
    assert res1 == res2

def test_celery_ai_tasks(app, db):
    """10. Test Celery AI background task execution."""
    AIService.set_provider(MockAIProvider())
    s = Session(session_code="999999", teacher_name="T", teacher_email="t@e.com", college="C", department="D", subject="S", title="T", language="python", mode="practice")
    s.save()
    st = Student(session_id=s.id, name="St", roll_number="R1", department="D", year="1", section="A")
    st.save()

    res = analyze_code_task.apply(args=[s.id, st.id]).get()
    assert res is not None

# ------------------------------------------------------------------------------
# 3. REST API ENDPOINT TESTS
# ------------------------------------------------------------------------------

def test_teacher_ai_overview_api(client, db):
    """11. Test GET /api/v1/ai/teacher/session/{session_id}/ai/overview."""
    AIService.set_provider(MockAIProvider())
    t_token, _, s_id, _ = setup_test_session(client, "practice")

    res = client.get(f"/api/v1/ai/teacher/session/{s_id}/ai/overview", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "summary" in data

def test_student_ai_hint_api(client, db):
    """12. Test POST /api/v1/ai/student/session/{session_id}/ai/hint."""
    AIService.set_provider(MockAIProvider())
    _, st_token, s_id, _ = setup_test_session(client, "practice")

    res = client.post(f"/api/v1/ai/student/session/{s_id}/ai/hint", headers={"X-Student-Token": st_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "hint" in data

def test_student_ai_review_rejected_in_problem_solving_mode(client, db):
    """13. Test code review rejection (403) in problem_solving mode."""
    AIService.set_provider(MockAIProvider())
    _, st_token, s_id, _ = setup_test_session(client, "problem_solving")

    res = client.post(f"/api/v1/ai/student/session/{s_id}/ai/review", headers={"X-Student-Token": st_token})
    assert res.status_code == 403

# ------------------------------------------------------------------------------
# 4. OPTIONAL LIVE OPENAI INTEGRATION TEST
# ------------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("OPENAI_INTEGRATION_TEST"), reason="Skipping live OpenAI integration test unless OPENAI_INTEGRATION_TEST=true")
def test_live_openai_integration(app):
    """Optional live integration test against OpenAI API."""
    provider = OpenAIProvider()
    res = provider.analyze_code({"title": "Test"}, "print('hello')", "python", "practice")
    assert "overall" in res
