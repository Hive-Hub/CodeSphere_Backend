import json
import pytest
from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.session_student import SessionStudent
from app.models.report_job import ReportJob
from app.services.report_v2_service import ReportV2Service

def test_teacher_profile_and_token(client):
    """Test persistent teacher profile creation, login, and token authentication."""
    # 1. Initialize teacher profile
    resp = client.post("/api/v1/teacher/profile", json={
        "name": "Prof. Sekhar",
        "email": "sekhar@university.edu",
        "college": "Tech Institute",
        "department": "Computer Science",
        "subject": "Python Data Structures"
    })
    assert resp.status_code in (200, 201)
    data = resp.get_json()["data"]
    teacher_token = data["teacher_token"]
    assert teacher_token is not None

    # 2. Get profile with token
    headers = {"X-Teacher-Token": teacher_token}
    get_resp = client.get("/api/v1/teacher/profile", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.get_json()["data"]["teacher"]["email"] == "sekhar@university.edu"

    # 3. Duplicate profile init reuses existing record
    resp2 = client.post("/api/v1/teacher/profile", json={
        "name": "Prof. Sekhar Updated",
        "email": "sekhar@university.edu"
    })
    assert resp2.status_code == 200
    assert Teacher.query.filter_by(email="sekhar@university.edu").count() == 1

def test_student_persistence_and_multiple_sessions(client):
    """Test student persistence model (reusing student identity across sessions)."""
    # Create Session 1
    s1_resp = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Sekhar",
        "teacher_email": "sekhar@uni.edu",
        "college": "College",
        "department": "CS",
        "subject": "Python",
        "title": "Session 1",
        "language": "python",
        "mode": "practice"
    })
    code1 = s1_resp.get_json()["data"]["session"]["session_code"]

    # Student joins Session 1
    j1_resp = client.post("/api/v1/student/session/join", json={
        "session_code": code1,
        "name": "Rahul Kumar",
        "roll_number": "21CS042",
        "department": "CS",
        "year": "3rd",
        "section": "A"
    })
    assert j1_resp.status_code == 200

    # Create Session 2
    s2_resp = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Sekhar",
        "teacher_email": "sekhar@uni.edu",
        "college": "College",
        "department": "CS",
        "subject": "Python",
        "title": "Session 2",
        "language": "python",
        "mode": "practice"
    })
    code2 = s2_resp.get_json()["data"]["session"]["session_code"]

    # Same Student joins Session 2
    j2_resp = client.post("/api/v1/student/session/join", json={
        "session_code": code2,
        "name": "Rahul Kumar",
        "roll_number": "21CS042",
        "department": "CS",
        "year": "3rd",
        "section": "A"
    })
    assert j2_resp.status_code == 200

    # Verify single Student record exists with 2 SessionStudent participations
    st_count = Student.query.filter_by(roll_number="21CS042").count()
    assert st_count == 1

    student = Student.query.filter_by(roll_number="21CS042").first()
    parts = SessionStudent.query.filter_by(student_id=student.id).all()
    assert len(parts) == 2

def test_compiler_input_and_socket_events(client):
    """Test compiler endpoint with stdin input."""
    # Create session & join student
    s_resp = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Teacher", "teacher_email": "t@u.edu", "college": "C", "department": "D", "subject": "S",
        "title": "Compiler Test", "language": "python", "mode": "practice"
    })
    session = s_resp.get_json()["data"]["session"]

    j_resp = client.post("/api/v1/student/session/join", json={
        "session_code": session["session_code"], "name": "Student A", "roll_number": "ROLL001",
        "department": "CS", "year": "1", "section": "A"
    })
    st_token = j_resp.get_json()["data"]["student_token"]

    run_resp = client.post(
        f"/api/v1/student/session/{session['id']}/code/run",
        json={"language": "python", "code": "import sys\nprint(sys.stdin.read())", "stdin": "10\n20\n"},
        headers={"X-Student-Token": st_token}
    )
    assert run_resp.status_code == 200
    res_data = run_resp.get_json()["data"]
    assert res_data["success"] is True

def test_v2_report_jobs(client):
    """Test V2 any-time report job generation and status querying."""
    # Init teacher profile
    p_resp = client.post("/api/v1/teacher/profile", json={"name": "Dr. Report", "email": "report@uni.edu"})
    t_token = p_resp.get_json()["data"]["teacher_token"]

    # Generate Today report
    gen_resp = client.post(
        "/api/v1/teacher/reports/generate",
        json={"filter_type": "today", "format": "both"},
        headers={"X-Teacher-Token": t_token}
    )
    assert gen_resp.status_code in (200, 202)
    job_data = gen_resp.get_json()["data"]
    job_id = job_data["job_id"]

    # Check status
    stat_resp = client.get(f"/api/v1/teacher/reports/job/{job_id}/status", headers={"X-Teacher-Token": t_token})
    assert stat_resp.status_code == 200
    assert stat_resp.get_json()["data"]["job_id"] == job_id
