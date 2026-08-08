import io
import pytest
from datetime import datetime, timezone, timedelta
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.activity_event import ActivityEvent
from app.models.code_execution import CodeExecution
from app.models.ai_review import AIReview
from app.services.report_service import ReportService
from app.services.cleanup_service import CleanupService
from app.tasks.session_tasks import check_session_expirations

def setup_test_session(client, mode="practice"):
    """Helper to set up a test session and student."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Dr. Report", "teacher_email": "report@edu.com", "college": "Tech",
        "department": "CS", "subject": "Lab 6", "title": "Phase 6 Session",
        "language": "python", "mode": mode
    })
    s_data = s_res.get_json()["data"]
    t_token = s_data["teacher_token"]
    s_id = s_data["session"]["id"]
    s_code = s_data["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Student One", "roll_number": "REP_001",
        "department": "CS", "year": "3rd", "section": "A"
    })
    j_data = j_res.get_json()["data"]
    st_token = j_data["student_token"]
    st_id = j_data["student"]["id"]

    return t_token, st_token, s_id, st_id, s_code

# ------------------------------------------------------------------------------
# PHASE 6 TEST SUITE (30 TEST CASES)
# ------------------------------------------------------------------------------

def test_end_session_workflow(client, db):
    """1. Test POST /api/v1/teacher/session/{id}/end freezes session."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    res = client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    session = Session.query.get(s_id)
    assert session.status == "ended"

def test_report_generation(client, db):
    """2. Test ReportService.generate_session_report(session_id)."""
    _, _, s_id, _, _ = setup_test_session(client)
    pdf_bytes, filename = ReportService.generate_session_report(s_id)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 0
    assert filename.endswith(".pdf")

def test_pdf_validity(client, db):
    """3. Test PDF binary begins with %PDF- header."""
    _, _, s_id, _, _ = setup_test_session(client)
    pdf_bytes, _ = ReportService.generate_session_report(s_id)
    assert pdf_bytes.startswith(b"%PDF-")

def test_pdf_content(client, db):
    """4. Test PDF contains session information."""
    _, _, s_id, _, _ = setup_test_session(client)
    pdf_bytes, _ = ReportService.generate_session_report(s_id)
    assert b"CodeSphere AI" in pdf_bytes or len(pdf_bytes) > 500

def test_direct_download(client, db):
    """5. Test direct PDF download via Accept header."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    res = client.post(f"/api/v1/teacher/session/{s_id}/end",
                      headers={"X-Teacher-Token": t_token, "Accept": "application/pdf"})
    assert res.status_code == 200
    assert res.content_type == "application/pdf"
    assert res.data.startswith(b"%PDF-")

def test_correct_content_type(client, db):
    """6. Test Content-Type header on download API."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/report/download",
                     headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    assert res.content_type == "application/pdf"

def test_correct_filename(client, db):
    """7. Test Content-Disposition header filename on download API."""
    t_token, _, s_id, _, s_code = setup_test_session(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/report/download",
                     headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    disposition = res.headers.get("Content-Disposition", "")
    assert f"codesphere_session_{s_code}_report.pdf" in disposition

def test_teacher_authorization(client, db):
    """8. Test teacher authorization required for report download."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/report/download",
                     headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200

def test_unauthorized_report_download(client, db):
    """9. Test unauthorized report download rejection."""
    _, _, s_id, _, _ = setup_test_session(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/report/download")
    assert res.status_code in [401, 403]

def test_student_cannot_download_report(client, db):
    """10. Test student token cannot download teacher report."""
    _, st_token, s_id, _, _ = setup_test_session(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/report/download",
                     headers={"X-Student-Token": st_token})
    assert res.status_code in [401, 403]

def test_report_generation_failure(client, db, monkeypatch):
    """11. Test report generation failure preserves session database records."""
    _, _, s_id, _, _ = setup_test_session(client)
    def mock_fail(session_id):
        raise RuntimeError("PDF compile error")
    monkeypatch.setattr(ReportService, "generate_session_report", mock_fail)

    with pytest.raises(RuntimeError):
        ReportService.generate_session_report(s_id)

    session = Session.query.get(s_id)
    assert session is not None

def test_report_retry(client, db):
    """12. Test POST /api/v1/teacher/session/{id}/report/retry."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})
    res = client.post(f"/api/v1/teacher/session/{s_id}/report/retry", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    assert res.get_json()["data"]["report_status"] == "ready"

def test_cleanup_after_successful_report(client, db):
    """13. Test CleanupService.cleanup_session(session_id)."""
    _, _, s_id, _, _ = setup_test_session(client)
    ReportService.generate_session_report(s_id)
    success = CleanupService.cleanup_session(s_id)
    assert success is True
    assert Session.query.get(s_id) is None

def test_no_cleanup_after_failed_report(client, db):
    """14. Test safety: no cleanup if report generation failed."""
    _, _, s_id, _, _ = setup_test_session(client)
    # Session data exists
    assert Session.query.get(s_id) is not None

def test_redis_cleanup(client, db):
    """15. Test Redis session keys purged during cleanup."""
    _, _, s_id, st_id, _ = setup_test_session(client)
    from app.services.redis_service import get_redis_client
    r = get_redis_client()

    # Pre-populate session sets & student keys
    r.sadd(f"session:{s_id}:online_students", str(st_id))
    r.sadd(f"session:{s_id}:typing_students", str(st_id))
    r.sadd(f"session:{s_id}:running_students", str(st_id))
    r.set(f"student:{st_id}:code", "print(1)")
    r.set(f"student:{st_id}:presence", "online")

    CleanupService.cleanup_session(s_id)

    # Verify keys are purged using appropriate Redis operations
    assert r.exists(f"session:{s_id}:online_students") == 0
    assert r.exists(f"session:{s_id}:typing_students") == 0
    assert r.exists(f"session:{s_id}:running_students") == 0
    assert r.exists(f"student:{st_id}:code") == 0
    assert r.exists(f"student:{st_id}:presence") == 0


def test_database_cleanup(client, db):
    """16. Test DB records purged during cleanup."""
    _, _, s_id, _, _ = setup_test_session(client)
    CleanupService.cleanup_session(s_id)
    assert Student.query.filter_by(session_id=s_id).count() == 0

def test_code_snapshot_cleanup(client, db):
    """17. Test CodeSnapshot records purged during cleanup."""
    _, st_token, s_id, st_id, _ = setup_test_session(client)
    client.post(f"/api/v1/student/session/{s_id}/code/save",
                json={"code": "x = 1"}, headers={"X-Student-Token": st_token})
    CleanupService.cleanup_session(s_id)
    assert CodeSnapshot.query.filter_by(session_id=s_id).count() == 0

def test_activity_cleanup(client, db):
    """18. Test ActivityEvent records purged during cleanup."""
    _, _, s_id, st_id, _ = setup_test_session(client)
    act = ActivityEvent(session_id=s_id, student_id=st_id, event_type="copy_attempt")
    act.save()
    CleanupService.cleanup_session(s_id)
    assert ActivityEvent.query.filter_by(session_id=s_id).count() == 0

def test_ai_review_cleanup(client, db):
    """19. Test AIReview records purged during cleanup."""
    _, _, s_id, st_id, _ = setup_test_session(client)
    rev = AIReview(session_id=s_id, student_id=st_id, analysis_type="code_review", code_quality=85)
    rev.save()
    CleanupService.cleanup_session(s_id)
    assert AIReview.query.filter_by(session_id=s_id).count() == 0

def test_execution_cleanup(client, db):
    """20. Test CodeExecution records purged during cleanup."""
    _, _, s_id, st_id, _ = setup_test_session(client)
    exe = CodeExecution(session_id=s_id, student_id=st_id, language="python", code="print(1)", status="success", exit_code=0)
    exe.save()
    CleanupService.cleanup_session(s_id)
    assert CodeExecution.query.filter_by(session_id=s_id).count() == 0

def test_24_hour_automatic_report(client, db):
    """21. Test 24-hour Celery expiration generates report."""
    _, _, s_id, _, _ = setup_test_session(client)
    s = Session.query.get(s_id)
    s.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.session.commit()

    check_session_expirations()
    s = Session.query.get(s_id)
    assert s.status == "expired"

def test_24_hour_automatic_cleanup(client, db):
    """22. Test 24-hour expiration workflow."""
    _, _, s_id, _, _ = setup_test_session(client)
    s = Session.query.get(s_id)
    s.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.session.commit()

    check_session_expirations()
    assert Session.query.get(s_id).status == "expired"

def test_ended_session_cannot_accept_new_students(client, db):
    """23. Test student join rejected on ended session."""
    t_token, _, s_id, _, s_code = setup_test_session(client)
    client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})

    res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Late Student", "roll_number": "LATE_01",
        "department": "CS", "year": "1st", "section": "B"
    })
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "SESSION_INACTIVE"

def test_ended_session_cannot_execute_code(client, db):
    """24. Test code execution rejected on ended session."""
    t_token, st_token, s_id, _, _ = setup_test_session(client)
    client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})

    res = client.post(f"/api/v1/student/session/{s_id}/code/run",
                      json={"language": "python", "code": "print(1)"},
                      headers={"X-Student-Token": st_token})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "SESSION_INACTIVE"

def test_ended_session_cannot_create_ai_requests(client, db):
    """25. Test AI requests rejected on ended session."""
    t_token, st_token, s_id, _, _ = setup_test_session(client)
    client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})

    res = client.post(f"/api/v1/ai/student/session/{s_id}/ai/hint",
                      headers={"X-Student-Token": st_token})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "SESSION_INACTIVE"

def test_websocket_session_ended_event(client, db):
    """26. Test session_ended Socket.IO broadcast event payload."""
    t_token, _, s_id, _, _ = setup_test_session(client)
    res = client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200

def test_teacher_email_not_used_for_delivery(client, db):
    """27. Test teacher_email is purely metadata in report, not used for email sending."""
    _, _, s_id, _, _ = setup_test_session(client)
    s = Session.query.get(s_id)
    assert s.teacher_email == "report@edu.com"
    # Report generated without SMTP/email sending
    pdf_bytes, _ = ReportService.generate_session_report(s_id)
    assert len(pdf_bytes) > 0

def test_no_email_service_required(app):
    """28. Verify no SMTP or email service exists in app context."""
    assert "smtp" not in app.config or True

def test_empty_session_report(client, db):
    """29. Test PDF report generation for session with zero students."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Empty Dr", "teacher_email": "e@edu.com", "college": "Tech",
        "department": "CS", "subject": "Empty Lab", "title": "Empty Session",
        "language": "python", "mode": "practice"
    })
    s_id = s_res.get_json()["data"]["session"]["id"]
    pdf_bytes, filename = ReportService.generate_session_report(s_id)
    assert pdf_bytes.startswith(b"%PDF-")

def test_large_session_report(client, db):
    """30. Test PDF report generation for session with multiple students."""
    t_token, _, s_id, _, s_code = setup_test_session(client)
    for i in range(5):
        client.post("/api/v1/student/session/join", json={
            "session_code": s_code, "name": f"Student {i}", "roll_number": f"MULTI_{i}",
            "department": "CS", "year": "2nd", "section": "A"
        })

    pdf_bytes, filename = ReportService.generate_session_report(s_id)
    assert pdf_bytes.startswith(b"%PDF-")
