from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.services.presence_service import (
    set_student_online, set_student_offline, get_online_count, update_student_heartbeat
)
from app.tasks.session_tasks import check_session_expirations

# ------------------------------------------------------------------------------
# 1. TEACHER SESSION CREATION TESTS
# ------------------------------------------------------------------------------

def test_teacher_session_creation_success(client):
    """Test successful teacher session creation."""
    payload = {
        "teacher_name": "Dr. Alan Turing",
        "teacher_email": "turing@cambridge.edu",
        "college": "Trinity College",
        "department": "Computer Science",
        "subject": "Algorithms",
        "title": "Sorting Algorithms Practice",
        "language": "python",
        "mode": "practice"
    }
    response = client.post("/api/v1/teacher/session/create", json=payload)
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "teacher_token" in json_data["data"]
    
    session_data = json_data["data"]["session"]
    assert len(session_data["session_code"]) == 6
    assert session_data["session_code"].isdigit()
    assert session_data["status"] == "active"
    assert session_data["language"] == "python"
    assert session_data["mode"] == "practice"

def test_session_creation_invalid_language(client):
    """Test session creation rejection for unsupported language."""
    payload = {
        "teacher_name": "Prof. Smith",
        "teacher_email": "smith@edu.com",
        "college": "Tech Uni",
        "department": "CS",
        "subject": "Web Dev",
        "title": "JS Lab",
        "language": "javascript",  # Unsupported in Phase 1
        "mode": "practice"
    }
    response = client.post("/api/v1/teacher/session/create", json=payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "VALIDATION_ERROR"

def test_session_creation_invalid_mode(client):
    """Test session creation rejection for invalid mode."""
    payload = {
        "teacher_name": "Prof. Smith",
        "teacher_email": "smith@edu.com",
        "college": "Tech Uni",
        "department": "CS",
        "subject": "Web Dev",
        "title": "Lab 1",
        "language": "python",
        "mode": "invalid_mode"
    }
    response = client.post("/api/v1/teacher/session/create", json=payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["success"] is False

def test_session_creation_missing_fields(client):
    """Test session creation rejection when mandatory fields are missing."""
    payload = {
        "teacher_name": "Prof. Smith",
        "language": "python",
        "mode": "practice"
    }
    response = client.post("/api/v1/teacher/session/create", json=payload)
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["success"] is False

# ------------------------------------------------------------------------------
# 2. SESSION VALIDATION & STATUS TESTS
# ------------------------------------------------------------------------------

def test_public_session_status_endpoint(client, db):
    """Test public session status check endpoint GET /api/session/{session_code}/status."""
    # Create active session
    session = Session(
        session_code="123456",
        teacher_name="Prof. X",
        teacher_email="x@mutants.edu",
        college="Xavier Institute",
        department="Mutation Science",
        subject="Telepathy 101",
        title="Intro Class",
        language="c",
        mode="practice",
        status="active"
    )
    session.save()

    # Query status
    response = client.get("/api/v1/session/123456/status")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["exists"] is True
    assert json_data["data"]["is_active"] is True
    assert json_data["data"]["language"] == "c"
    # Ensure teacher email is NOT exposed
    assert "teacher_email" not in json_data["data"]

def test_nonexistent_session_status(client):
    """Test public session status check for non-existent session code."""
    response = client.get("/api/v1/session/999999/status")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["data"]["exists"] is False
    assert json_data["data"]["is_active"] is False

# ------------------------------------------------------------------------------
# 3. STUDENT JOIN TESTS
# ------------------------------------------------------------------------------

def test_student_join_success(client, db):
    """Test successful student join with valid session code."""
    session = Session(
        session_code="654321",
        teacher_name="Dr. Hopper",
        teacher_email="grace@navy.mil",
        college="Navy Academy",
        department="CS",
        subject="Compilers",
        title="COBOL Lab",
        language="java",
        mode="practice",
        status="active"
    )
    session.save()

    join_payload = {
        "session_code": "654321",
        "name": "Alice Johnson",
        "roll_number": "CS_2026_001",
        "department": "Computer Science",
        "year": "3rd Year",
        "section": "A"
    }

    response = client.post("/api/v1/student/session/join", json=join_payload)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert "student_token" in json_data["data"]
    assert json_data["data"]["student"]["name"] == "Alice Johnson"
    assert json_data["data"]["session"]["session_id"] == session.id

def test_student_join_duplicate_roll_number(client, db):
    """Test rejection of duplicate roll number within the same active session."""
    session = Session(
        session_code="111222",
        teacher_name="Prof. Knuth",
        teacher_email="knuth@stanford.edu",
        college="Stanford",
        department="CS",
        subject="Algorithms",
        title="TAOCP Lab",
        language="python",
        mode="practice",
        status="active"
    )
    session.save()

    payload = {
        "session_code": "111222",
        "name": "Bob Smith",
        "roll_number": "ROLL_DUP_001",
        "department": "CS",
        "year": "2nd Year",
        "section": "B"
    }

    # First join -> success
    res1 = client.post("/api/v1/student/session/join", json=payload)
    assert res1.status_code == 200

    # Second join with same roll_number -> HTTP 400 DUPLICATE_ROLL_NUMBER
    res2 = client.post("/api/v1/student/session/join", json=payload)
    assert res2.status_code == 400
    json_data = res2.get_json()
    assert json_data["success"] is False
    assert json_data["error"]["code"] == "DUPLICATE_ROLL_NUMBER"

# ------------------------------------------------------------------------------
# 4. PROBLEM CREATION & REFERENCE SOLUTION PROTECTION TESTS
# ------------------------------------------------------------------------------

def test_problem_creation_in_problem_solving_mode(client, db):
    """Test teacher creating a problem in problem_solving mode."""
    # Create session & teacher token
    create_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Dijkstra",
        "teacher_email": "edsger@utexas.edu",
        "college": "UT Austin",
        "department": "CS",
        "subject": "Graph Theory",
        "title": "Shortest Path Lab",
        "language": "python",
        "mode": "problem_solving"
    })
    token = create_res.get_json()["data"]["teacher_token"]
    session_id = create_res.get_json()["data"]["session"]["id"]

    # Create problem
    prob_payload = {
        "title": "Dijkstra Algorithm Implementation",
        "description": "Find single source shortest paths.",
        "constraints": "V <= 1000, E <= 5000",
        "input_format": "Adjacency list",
        "output_format": "Distances array",
        "sample_input": "4 5\n0 1 10...",
        "sample_output": "0 10 15 20",
        "reference_solution": "def dijkstra(g, src): pass"
    }

    response = client.post(
        f"/api/v1/teacher/session/{session_id}/problem",
        json=prob_payload,
        headers={"X-Teacher-Token": token}
    )
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data["success"] is True
    # Teacher receives reference_solution
    assert "reference_solution" in json_data["data"]["problem"]

def test_problem_creation_rejected_in_practice_mode(client, db):
    """Test rejection of problem creation when session is in practice mode."""
    create_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Practice",
        "teacher_email": "practice@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Basics",
        "title": "Free Coding Practice",
        "language": "python",
        "mode": "practice" # Practice mode!
    })
    token = create_res.get_json()["data"]["teacher_token"]
    session_id = create_res.get_json()["data"]["session"]["id"]

    response = client.post(
        f"/api/v1/teacher/session/{session_id}/problem",
        json={"title": "Test", "description": "Desc"},
        headers={"X-Teacher-Token": token}
    )
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["error"]["code"] == "INVALID_MODE"

def test_student_dashboard_never_exposes_reference_solution(client, db):
    """Verify GET /student/session/{session_id} never returns reference_solution or teacher email."""
    create_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Secret Teacher",
        "teacher_email": "secret_email@private.com",
        "college": "Secret College",
        "department": "CS",
        "subject": "Security",
        "title": "Secret Session",
        "language": "python",
        "mode": "problem_solving"
    })
    t_token = create_res.get_json()["data"]["teacher_token"]
    session_id = create_res.get_json()["data"]["session"]["id"]
    s_code = create_res.get_json()["data"]["session"]["session_code"]

    # Teacher creates problem with confidential reference_solution
    client.post(
        f"/api/v1/teacher/session/{session_id}/problem",
        json={
            "title": "Secret Problem",
            "description": "Solve it",
            "reference_solution": "SUPER_SECRET_TEACHER_SOLUTION_CODE"
        },
        headers={"X-Teacher-Token": t_token}
    )

    # Student joins session
    join_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Eve Student",
        "roll_number": "EVE_007",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = join_res.get_json()["data"]["student_token"]

    # Student requests session info
    response = client.get(
        f"/api/v1/student/session/{session_id}",
        headers={"X-Student-Token": s_token}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True

    prob_data = json_data["data"]["problem"]
    assert prob_data["title"] == "Secret Problem"
    
    # CRITICAL SECURITY CHECK
    assert "reference_solution" not in prob_data
    assert "teacher_email" not in json_data["data"]["session"]

# ------------------------------------------------------------------------------
# 5. TEACHER DASHBOARD & END SESSION TESTS
# ------------------------------------------------------------------------------

def test_teacher_dashboard_and_end_session(client, db):
    """Test GET teacher dashboard and POST end session."""
    create_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. EndTest",
        "teacher_email": "end@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Subject",
        "title": "Session to End",
        "language": "python",
        "mode": "practice"
    })
    token = create_res.get_json()["data"]["teacher_token"]
    session_id = create_res.get_json()["data"]["session"]["id"]
    s_code = create_res.get_json()["data"]["session"]["session_code"]

    # Get teacher dashboard
    dash_res = client.get(
        f"/api/v1/teacher/session/{session_id}",
        headers={"X-Teacher-Token": token}
    )
    assert dash_res.status_code == 200
    assert dash_res.get_json()["data"]["status"] == "active"

    # End session
    end_res = client.post(
        f"/api/v1/teacher/session/{session_id}/end",
        headers={"X-Teacher-Token": token}
    )
    assert end_res.status_code == 200
    assert end_res.get_json()["data"]["session"]["status"] == "ended"

    # Attempt student join after session ended -> rejected
    join_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Late Student",
        "roll_number": "LATE_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    assert join_res.status_code == 400
    assert join_res.get_json()["error"]["code"] == "SESSION_INACTIVE"

# ------------------------------------------------------------------------------
# 6. CELERY EXPIRATION TASK & REDIS PRESENCE TESTS
# ------------------------------------------------------------------------------

def test_celery_session_expiration_task(app, db):
    """Test check_session_expirations Celery task auto-expiring 24-hour sessions."""
    with app.app_context():
        # Create an expired session (expires_at in past)
        past_time = datetime.now(timezone.utc) - timedelta(hours=25)
        session = Session(
            session_code="555666",
            teacher_name="Old Teacher",
            teacher_email="old@edu.com",
            college="Old College",
            department="CS",
            subject="History",
            title="Old Session",
            language="c",
            mode="practice",
            status="active",
            expires_at=past_time
        )
        session.save()

        # Run Celery expiration task
        res = check_session_expirations.apply().get()
        assert res["status"] == "SUCCESS"
        assert res["expired_count"] >= 1

        # Check DB status updated to 'expired'
        updated = Session.query.get(session.id)
        assert updated.status == "expired"

def test_redis_presence_tracking(app, mocker):
    """Test Redis online student presence helpers."""
    mock_redis = mocker.patch("redis.Redis.from_url")
    mock_instance = mock_redis.return_value
    mock_instance.sadd.return_value = 1
    mock_instance.srem.return_value = 1
    mock_instance.scard.return_value = 1
    mock_instance.hset.return_value = 1

    with app.app_context():
        assert set_student_online(session_id=1, student_id=10, sid="sid_123") is True
        assert get_online_count(session_id=1) == 1
        assert update_student_heartbeat(session_id=1, student_id=10) is True
        assert set_student_offline(session_id=1, student_id=10) is True

# ------------------------------------------------------------------------------
# 7. SOCKET.IO SESSION ROOM EVENT TESTS
# ------------------------------------------------------------------------------

def test_socketio_student_presence_events(socket_client, app, db):
    """Test Socket.IO student_join_session, heartbeat, and leave events."""
    session = Session(
        session_code="777888",
        teacher_name="Socket Prof",
        teacher_email="socket@edu.com",
        college="College",
        department="CS",
        subject="Networks",
        title="Socket Lab",
        language="python",
        mode="practice",
        status="active"
    )
    session.save()

    student = Student(
        session_id=session.id,
        name="Socket Student",
        roll_number="SOCK_001",
        department="CS",
        year="1st Year",
        section="A",
        status="offline"
    )
    student.save()

    # 1. Join room event
    socket_client.emit("student_join_session", {
        "session_id": session.id,
        "student_id": student.id
    })
    received = socket_client.get_received()
    event_names = [r["name"] for r in received]
    assert "student_joined" in event_names or "student_online" in event_names

    # 2. Heartbeat event
    socket_client.emit("student_heartbeat", {
        "session_id": session.id,
        "student_id": student.id
    })
    received_hb = socket_client.get_received()
    assert len(received_hb) > 0
    assert received_hb[0]["name"] == "heartbeat_ack"

    # 3. Leave room event
    socket_client.emit("student_leave_session", {
        "session_id": session.id,
        "student_id": student.id
    })
    received_leave = socket_client.get_received()
    event_names_leave = [r["name"] for r in received_leave]
    assert "student_left" in event_names_leave or "student_offline" in event_names_leave
