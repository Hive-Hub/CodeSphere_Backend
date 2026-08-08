from datetime import datetime, timezone
from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.activity_event import ActivityEvent
from app.services.code_service import (
    set_student_live_code, get_student_live_code, set_student_typing_status,
    get_student_typing_status, save_code_snapshot, record_activity_event
)
from app.tasks.code_tasks import persist_debounced_code_snapshot

# ------------------------------------------------------------------------------
# 1. STUDENT WORKSPACE API TESTS
# ------------------------------------------------------------------------------

def test_student_workspace_practice_mode(client, db):
    """Test GET /api/student/session/{session_id}/workspace in practice mode."""
    # Create practice session and student
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Practice",
        "teacher_email": "prac@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Python",
        "title": "Practice Session",
        "language": "python",
        "mode": "practice"
    })
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Prac Student",
        "roll_number": "PRAC_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = j_res.get_json()["data"]["student_token"]

    response = client.get(
        f"/api/v1/student/session/{session_id}/workspace",
        headers={"X-Student-Token": s_token}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    assert json_data["data"]["mode"] == "practice"
    assert json_data["data"]["editor_config"]["language"] == "python"

def test_student_workspace_problem_solving_mode_reference_protection(client, db):
    """Test workspace API in problem_solving mode strictly excludes reference_solution."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Prob",
        "teacher_email": "prob@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Java",
        "title": "Problem Solving",
        "language": "java",
        "mode": "problem_solving"
    })
    t_token = s_res.get_json()["data"]["teacher_token"]
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    # Teacher adds problem with confidential solution
    client.post(
        f"/api/v1/teacher/session/{session_id}/problem",
        json={
            "title": "Factorial",
            "description": "Calculate n!",
            "reference_solution": "public class Solution { ... }"
        },
        headers={"X-Teacher-Token": t_token}
    )

    # Student joins
    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Prob Student",
        "roll_number": "PROB_001",
        "department": "CS",
        "year": "2nd Year",
        "section": "B"
    })
    s_token = j_res.get_json()["data"]["student_token"]

    response = client.get(
        f"/api/v1/student/session/{session_id}/workspace",
        headers={"X-Student-Token": s_token}
    )
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["success"] is True
    prob = json_data["data"]["problem"]
    assert prob["title"] == "Factorial"
    
    # CRITICAL SECURITY ASSERTION
    assert "reference_solution" not in prob

# ------------------------------------------------------------------------------
# 2. CODE SAVE & RETRIEVAL REST API TESTS
# ------------------------------------------------------------------------------

def test_student_code_save_and_versioning(client, db):
    """Test explicit POST /api/student/session/{session_id}/code/save and snapshot versioning."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Code",
        "teacher_email": "code@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "C",
        "title": "C Lab",
        "language": "c",
        "mode": "practice"
    })
    t_token = s_res.get_json()["data"]["teacher_token"]
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Coder",
        "roll_number": "C_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = j_res.get_json()["data"]["student_token"]
    student_id = j_res.get_json()["data"]["student"]["id"]

    # First save -> version 1
    save1 = client.post(
        f"/api/v1/student/session/{session_id}/code/save",
        json={"code": "#include <stdio.h>\nint main() { return 0; }", "language": "c"},
        headers={"X-Student-Token": s_token}
    )
    assert save1.status_code == 200
    assert save1.get_json()["data"]["version"] == 1

    # Second save -> version 2
    save2 = client.post(
        f"/api/v1/student/session/{session_id}/code/save",
        json={"code": "#include <stdio.h>\nint main() { printf(\"Hello\"); return 0; }", "language": "c"},
        headers={"X-Student-Token": s_token}
    )
    assert save2.status_code == 200
    assert save2.get_json()["data"]["version"] == 2

    # Student retrieves current code
    st_get = client.get(
        f"/api/v1/student/session/{session_id}/code",
        headers={"X-Student-Token": s_token}
    )
    assert st_get.status_code == 200
    assert "printf" in st_get.get_json()["data"]["code"]
    assert st_get.get_json()["data"]["version"] == 2

    # Teacher retrieves student code
    t_get = client.get(
        f"/api/v1/teacher/session/{session_id}/students/{student_id}/code",
        headers={"X-Teacher-Token": t_token}
    )
    assert t_get.status_code == 200
    assert t_get.get_json()["data"]["student"]["id"] == student_id
    assert "printf" in t_get.get_json()["data"]["code"]
    assert t_get.get_json()["data"]["version"] == 2

def test_code_save_payload_size_limit(client, db):
    """Test rejection of code payloads exceeding 100KB size limit."""
    s_res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Size",
        "teacher_email": "size@edu.com",
        "college": "College",
        "department": "CS",
        "subject": "Limits",
        "title": "Size Test",
        "language": "python",
        "mode": "practice"
    })
    session_id = s_res.get_json()["data"]["session"]["id"]
    s_code = s_res.get_json()["data"]["session"]["session_code"]

    j_res = client.post("/api/v1/student/session/join", json={
        "session_code": s_code,
        "name": "Huge Code Student",
        "roll_number": "HUGE_001",
        "department": "CS",
        "year": "1st Year",
        "section": "A"
    })
    s_token = j_res.get_json()["data"]["student_token"]

    # Payload larger than 100KB (150KB string)
    huge_code = "a = 1\n" * 25000
    save_res = client.post(
        f"/api/v1/student/session/{session_id}/code/save",
        json={"code": huge_code, "language": "python"},
        headers={"X-Student-Token": s_token}
    )
    assert save_res.status_code == 400
    assert save_res.get_json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

# ------------------------------------------------------------------------------
# 3. REDIS LIVE STATE & SERVICE LAYER TESTS
# ------------------------------------------------------------------------------

def test_redis_live_code_state(app, mocker):
    """Test Redis fast live code and typing state tracking."""
    mock_redis = mocker.patch("redis.Redis.from_url")
    mock_instance = mock_redis.return_value
    mock_instance.set.return_value = True
    mock_instance.get.side_effect = lambda key: "print('Live Redis Code')" if "code" in key else "1"
    mock_instance.sadd.return_value = 1

    with app.app_context():
        assert set_student_live_code(student_id=1, session_id=1, code="print('Live Redis Code')", cursor={"line": 2, "column": 5}) is True
        assert get_student_live_code(student_id=1) == "print('Live Redis Code')"
        assert set_student_typing_status(student_id=1, is_typing=True) is True
        assert get_student_typing_status(student_id=1) is True

def test_record_activity_event(app, db):
    """Test recording activity events in database."""
    with app.app_context():
        session = Session(
            session_code="888999",
            teacher_name="Event Prof",
            teacher_email="event@edu.com",
            college="College",
            department="CS",
            subject="Security",
            title="Event Session",
            language="python",
            mode="practice",
            status="active"
        )
        session.save()

        student = Student(
            session_id=session.id,
            name="Event Student",
            roll_number="EVENT_001",
            department="CS",
            year="1st Year",
            section="A"
        )
        student.save()

        event = record_activity_event(session.id, student.id, "copy_attempt", {"chars": 50})
        assert event is not None
        assert event.id is not None
        assert event.event_type == "copy_attempt"

        # Verify in DB
        saved_event = ActivityEvent.query.get(event.id)
        assert saved_event.event_type == "copy_attempt"

def test_debounced_code_snapshot_celery_task(app, db):
    """Test debounced code snapshot Celery task."""
    with app.app_context():
        session = Session(
            session_code="333444",
            teacher_name="Debounce Teacher",
            teacher_email="deb@edu.com",
            college="College",
            department="CS",
            subject="Tasks",
            title="Debounce Session",
            language="python",
            mode="practice",
            status="active"
        )
        session.save()

        student = Student(
            session_id=session.id,
            name="Debounce Student",
            roll_number="DEB_001",
            department="CS",
            year="1st Year",
            section="A"
        )
        student.save()

        # Run debounced snapshot task
        res = persist_debounced_code_snapshot.apply(args=[session.id, student.id, "python", "x = 42"]).get()
        assert res["status"] == "SUCCESS"
        assert res["version"] == 1

        # Verify CodeSnapshot in DB
        snap = CodeSnapshot.query.filter_by(student_id=student.id).first()
        assert snap is not None
        assert snap.code == "x = 42"

# ------------------------------------------------------------------------------
# 4. REAL-TIME SOCKET.IO EVENT BROADCAST TESTS
# ------------------------------------------------------------------------------

def test_socketio_code_change_and_typing_events(socket_client, app, db):
    """Test Socket.IO code_change, typing_start, typing_stop, and cursor_move events."""
    session = Session(
        session_code="444555",
        teacher_name="Prof. RealTime",
        teacher_email="rt@edu.com",
        college="College",
        department="CS",
        subject="Networks",
        title="RealTime Session",
        language="python",
        mode="practice",
        status="active"
    )
    session.save()

    student = Student(
        session_id=session.id,
        name="RT Student",
        roll_number="RT_001",
        department="CS",
        year="1st Year",
        section="A"
    )
    student.save()

    # Join room first
    socket_client.emit("student_join_session", {"session_id": session.id, "student_id": student.id})
    socket_client.get_received() # Clear join events

    # 1. code_change
    socket_client.emit("code_change", {
        "session_id": session.id,
        "student_id": student.id,
        "code": "def hello(): print('world')",
        "cursor": {"line": 1, "column": 12}
    })
    rec_code = socket_client.get_received()
    assert len(rec_code) > 0
    assert rec_code[0]["name"] == "student_code_updated"
    assert "hello" in rec_code[0]["args"][0]["code"]

    # 2. typing_start
    socket_client.emit("typing_start", {"session_id": session.id, "student_id": student.id})
    rec_type1 = socket_client.get_received()
    assert len(rec_type1) > 0
    assert rec_type1[0]["name"] == "student_typing"

    # 3. typing_stop
    socket_client.emit("typing_stop", {"session_id": session.id, "student_id": student.id})
    rec_type2 = socket_client.get_received()
    assert len(rec_type2) > 0
    assert rec_type2[0]["name"] == "student_stopped_typing"

    # 4. cursor_move
    socket_client.emit("cursor_move", {"session_id": session.id, "student_id": student.id, "line": 5, "column": 10})
    rec_cursor = socket_client.get_received()
    assert len(rec_cursor) > 0
    assert rec_cursor[0]["name"] == "student_cursor_updated"
    assert rec_cursor[0]["args"][0]["cursor"]["line"] == 5

def test_socketio_activity_and_run_code_events(socket_client, app, db):
    """Test Socket.IO activity_event and run_code event with compiler status broadcasts."""
    session = Session(
        session_code="999000",
        teacher_name="Prof. Compiler",
        teacher_email="comp@edu.com",
        college="College",
        department="CS",
        subject="Compilers",
        title="Compiler Session",
        language="python",
        mode="practice",
        status="active"
    )
    session.save()

    student = Student(
        session_id=session.id,
        name="Comp Student",
        roll_number="COMP_001",
        department="CS",
        year="1st Year",
        section="A"
    )
    student.save()

    socket_client.emit("student_join_session", {"session_id": session.id, "student_id": student.id})
    socket_client.get_received()

    # 1. activity_event (copy_attempt)
    socket_client.emit("activity_event", {
        "session_id": session.id,
        "student_id": student.id,
        "event_type": "copy_attempt",
        "metadata": {"chars": 25}
    })
    rec_act = socket_client.get_received()
    assert len(rec_act) > 0
    assert rec_act[0]["name"] == "student_activity"
    assert rec_act[0]["args"][0]["event_type"] == "copy_attempt"

    # 2. run_code event
    socket_client.emit("run_code", {
        "session_id": session.id,
        "student_id": student.id,
        "language": "python",
        "code": "print('Compiler Broadcast Test')",
        "stdin": ""
    })
    rec_run = socket_client.get_received()
    assert len(rec_run) >= 2
    event_names = [r["name"] for r in rec_run]
    assert "compiler_started" in event_names
    assert "execution_result" in event_names or "compiler_completed" in event_names
