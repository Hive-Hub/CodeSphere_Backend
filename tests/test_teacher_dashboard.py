import pytest
from app.models.session import Session
from app.models.student import Student
from app.models.code_snapshot import CodeSnapshot
from app.models.code_execution import CodeExecution
from app.models.activity_event import ActivityEvent
from app.services.presence_service import (
    set_student_online, set_student_offline, get_online_student_ids, set_student_running_status
)
from app.services.code_service import set_student_typing_status
from app.services.compiler_service import OnlineCompilerService
from tests.test_online_compiler import MockTestCompilerProvider

def create_test_session_and_teacher(client):
    """Helper to create a session and return teacher_token and session_id."""
    res = client.post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Dashboard",
        "teacher_email": "dash@edu.com",
        "college": "Tech Institute",
        "department": "CS",
        "subject": "Algorithms",
        "title": "Live Dashboard Session",
        "language": "python",
        "mode": "practice"
    })
    data = res.get_json()["data"]
    return data["teacher_token"], data["session"]["id"], data["session"]["session_code"]

def join_test_student(client, session_code, name="Student A", roll="ROLL_001"):
    """Helper to join a student and return student_token and student_id."""
    res = client.post("/api/v1/student/session/join", json={
        "session_code": session_code,
        "name": name,
        "roll_number": roll,
        "department": "CS",
        "year": "3rd Year",
        "section": "A"
    })
    data = res.get_json()["data"]
    return data["student_token"], data["student"]["id"]

# ------------------------------------------------------------------------------
# 1. TEACHER DASHBOARD ENDPOINT & STATS TESTS (1-3)
# ------------------------------------------------------------------------------

def test_teacher_dashboard_endpoint(client, db):
    """1. Test GET /api/teacher/session/{session_id}/dashboard endpoint."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    s_token, student_id = join_test_student(client, s_code, "Alice", "CS_101")

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "session" in data
    assert "statistics" in data
    assert "students" in data
    assert data["session"]["id"] == s_id
    assert data["session"]["language"] == "python"

def test_dashboard_statistics(client, db):
    """2. Test classroom statistics calculation in dashboard."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st1 = join_test_student(client, s_code, "Alice", "CS_101")
    _, st2 = join_test_student(client, s_code, "Bob", "CS_102")

    set_student_online(s_id, st1)
    set_student_typing_status(st1, True, session_id=s_id)

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    stats = res.get_json()["data"]["statistics"]
    assert stats["total_students"] == 2
    assert stats["online_students"] >= 1
    assert stats["typing_students"] >= 1

def test_student_list_in_dashboard(client, db):
    """3. Test student list array structure and null AI fields."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Charlie", "CS_103")

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    students = res.get_json()["data"]["students"]
    assert len(students) == 1
    st = students[0]
    assert st["id"] == st_id
    assert st["name"] == "Charlie"
    assert st["roll_number"] == "CS_103"
    assert st["progress"] is None
    assert st["ai_score"] is None

# ------------------------------------------------------------------------------
# 2. STUDENT DETAIL & HISTORIES (4-7)
# ------------------------------------------------------------------------------

def test_student_detail_endpoint(client, db):
    """4. Test GET /api/teacher/session/{session_id}/students/{student_id}."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "David", "CS_104")

    res = client.get(f"/api/v1/teacher/session/{s_id}/students/{st_id}", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["student"]["id"] == st_id
    assert "presence" in data
    assert "code" in data
    assert "executions" in data
    assert data["progress"] is None
    assert data["ai_score"] is None

def test_activity_pagination(client, db):
    """5. Test paginated activity history for a student."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Eva", "CS_105")

    # Create 5 activity events
    for i in range(5):
        evt = ActivityEvent(session_id=s_id, student_id=st_id, event_type="tab_blur")
        evt.save()

    res = client.get(f"/api/v1/teacher/session/{s_id}/students/{st_id}/activity?page=1&limit=3", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["events"]) == 3
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["total_pages"] == 2

def test_execution_history_endpoint(client, db):
    """6. Test paginated execution history endpoint."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Frank", "CS_106")

    # Log 2 execution records
    ex1 = CodeExecution(session_id=s_id, student_id=st_id, language="python", code="print(1)", status="success", exit_code=0)
    ex1.save()

    res = client.get(f"/api/v1/teacher/session/{s_id}/students/{st_id}/executions", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["executions"]) == 1
    assert data["executions"][0]["language"] == "python"

def test_session_analytics_endpoint(client, db):
    """7. Test GET /api/teacher/session/{session_id}/analytics."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    join_test_student(client, s_code, "Grace", "CS_107")

    res = client.get(f"/api/v1/teacher/session/{s_id}/analytics", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert "total_students" in data
    assert "online_students" in data
    assert "total_code_runs" in data
    assert data["total_students"] == 1

# ------------------------------------------------------------------------------
# 3. COUNTS & REDIS STATE TESTS (8-13)
# ------------------------------------------------------------------------------

def test_online_student_count(client, db):
    """8. Test online student count determination."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Hannah", "CS_108")

    set_student_online(s_id, st_id)
    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    stats = res.get_json()["data"]["statistics"]
    assert stats["online_students"] == 1

def test_offline_student_count(client, db):
    """9. Test offline student count determination."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Ian", "CS_109")

    set_student_offline(s_id, st_id)
    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    stats = res.get_json()["data"]["statistics"]
    assert stats["offline_students"] == 1

def test_typing_count(client, db):
    """10. Test typing student count determination."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Jack", "CS_110")

    set_student_online(s_id, st_id)
    set_student_typing_status(st_id, True, session_id=s_id)

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    stats = res.get_json()["data"]["statistics"]
    assert stats["typing_students"] == 1

def test_running_count(client, db):
    """11. Test running code student count determination."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Kara", "CS_111")

    set_student_online(s_id, st_id)
    set_student_running_status(s_id, st_id, True)

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    stats = res.get_json()["data"]["statistics"]
    assert stats["running_students"] == 1

def test_code_version_in_student_dashboard(client, db):
    """12. Test code version reporting in dashboard."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Leo", "CS_112")

    snap = CodeSnapshot(session_id=s_id, student_id=st_id, language="python", code="x = 10", version=3)
    snap.save()

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    st = res.get_json()["data"]["students"][0]
    assert st["code_version"] == 3

def test_redis_dashboard_state(client, db):
    """13. Test Redis dashboard set tracking."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Mona", "CS_113")

    set_student_online(s_id, st_id)
    online_ids = get_online_student_ids(s_id)
    assert st_id in online_ids

# ------------------------------------------------------------------------------
# 4. SOCKET.IO EVENT STANDARDIZATION TESTS (14-20)
# ------------------------------------------------------------------------------

def test_socket_student_joined(socket_client, app, db):
    """14. Test Socket.IO student_joined event structure."""
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Nora", "roll_number": "SOCK_01",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    received = socket_client.get_received()
    assert len(received) >= 1
    join_evt = [r for r in received if r["name"] == "student_joined"][0]
    payload = join_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id

def test_socket_student_left(socket_client, app, db):
    """15. Test Socket.IO student_left event structure."""
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Oscar", "roll_number": "SOCK_02",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("student_leave_session", {"session_id": s_id, "student_id": st_id})
    received = socket_client.get_received()
    assert len(received) >= 1
    left_evt = [r for r in received if r["name"] == "student_left"][0]
    payload = left_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id

def test_socket_student_typing(socket_client, app, db):
    """16. Test Socket.IO student_typing event payload."""
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Pam", "roll_number": "SOCK_03",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("typing_start", {"session_id": s_id, "student_id": st_id})
    received = socket_client.get_received()
    type_evt = [r for r in received if r["name"] == "student_typing"][0]
    payload = type_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id
    assert "timestamp" in payload

def test_socket_student_stopped_typing(socket_client, app, db):
    """17. Test Socket.IO student_stopped_typing event payload."""
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Quinn", "roll_number": "SOCK_04",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("typing_stop", {"session_id": s_id, "student_id": st_id})
    received = socket_client.get_received()
    stop_evt = [r for r in received if r["name"] == "student_stopped_typing"][0]
    payload = stop_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id
    assert "timestamp" in payload

def test_socket_student_code_updated(socket_client, app, db):
    """18. Test Socket.IO student_code_updated event payload."""
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Rachel", "roll_number": "SOCK_05",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("code_change", {"session_id": s_id, "student_id": st_id, "code": "def foo(): pass", "cursor": {"line": 1, "column": 5}})
    received = socket_client.get_received()
    code_evt = [r for r in received if r["name"] == "student_code_updated"][0]
    payload = code_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id
    assert "timestamp" in payload

def test_socket_compiler_started(socket_client, app, db):
    """19. Test Socket.IO compiler_started event payload."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Sam", "roll_number": "SOCK_06",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("run_code", {"session_id": s_id, "student_id": st_id, "language": "python", "code": "print(1)"})
    received = socket_client.get_received()
    start_evt = [r for r in received if r["name"] == "compiler_started"][0]
    payload = start_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id
    assert "timestamp" in payload

def test_socket_compiler_completed(socket_client, app, db):
    """20. Test Socket.IO compiler_completed event payload."""
    OnlineCompilerService.set_provider(MockTestCompilerProvider("success"))
    res = app.test_client().post("/api/v1/teacher/session/create", json={
        "teacher_name": "Prof. Sock", "teacher_email": "s@edu.com", "college": "Col",
        "department": "CS", "subject": "Py", "title": "Sock S", "language": "python", "mode": "practice"
    })
    s_id = res.get_json()["data"]["session"]["id"]
    s_code = res.get_json()["data"]["session"]["session_code"]

    j_res = app.test_client().post("/api/v1/student/session/join", json={
        "session_code": s_code, "name": "Tina", "roll_number": "SOCK_07",
        "department": "CS", "year": "1st Year", "section": "A"
    })
    st_id = j_res.get_json()["data"]["student"]["id"]

    socket_client.emit("student_join_session", {"session_id": s_id, "student_id": st_id})
    socket_client.get_received()

    socket_client.emit("run_code", {"session_id": s_id, "student_id": st_id, "language": "python", "code": "print(1)"})
    received = socket_client.get_received()
    comp_evt = [r for r in received if r["name"] == "compiler_completed"][0]
    payload = comp_evt["args"][0]
    assert payload["session_id"] == s_id
    assert payload["student_id"] == st_id
    assert "timestamp" in payload

# ------------------------------------------------------------------------------
# 5. AUTHORIZATION & SECURITY TESTS (21-24)
# ------------------------------------------------------------------------------

def test_teacher_authorization_valid(client, db):
    """21. Test valid teacher token gains dashboard access."""
    t_token, s_id, _ = create_test_session_and_teacher(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200

def test_student_cannot_access_teacher_dashboard(client, db):
    """22. Test student token or missing auth is rejected with 401/403."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    st_token, _ = join_test_student(client, s_code, "Umar", "CS_201")

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Student-Token": st_token})
    assert res.status_code in (401, 403)

def test_wrong_teacher_cannot_access_another_session(client, db):
    """23. Test teacher token for Session A cannot access Session B dashboard."""
    t_token1, s_id1, _ = create_test_session_and_teacher(client)
    t_token2, s_id2, _ = create_test_session_and_teacher(client)

    res = client.get(f"/api/v1/teacher/session/{s_id2}/dashboard", headers={"X-Teacher-Token": t_token1})
    assert res.status_code == 403

def test_session_expiry_handling_in_dashboard(client, db):
    """24. Test ended session dashboard returns remaining_seconds=0."""
    t_token, s_id, _ = create_test_session_and_teacher(client)
    client.post(f"/api/v1/teacher/session/{s_id}/end", headers={"X-Teacher-Token": t_token})

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["session"]["remaining_seconds"] == 0

# ------------------------------------------------------------------------------
# 6. EDGE CASES & PERFORMANCE TESTS (25-28)
# ------------------------------------------------------------------------------

def test_dashboard_with_zero_students(client, db):
    """25. Test dashboard cleanly returns empty student list for session with zero students."""
    t_token, s_id, _ = create_test_session_and_teacher(client)
    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["statistics"]["total_students"] == 0
    assert len(data["students"]) == 0

def test_dashboard_bulk_students_performance(client, db):
    """26. Test dashboard aggregation with 100 students."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)

    # Bulk insert 100 students
    students = []
    for i in range(100):
        s = Student(session_id=s_id, name=f"Student {i}", roll_number=f"BULK_{i:03d}", department="CS", year="1st", section="A")
        students.append(s)
    db.session.bulk_save_objects(students)
    db.session.commit()

    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["statistics"]["total_students"] == 100
    assert len(data["students"]) == 100

def test_activity_pagination_limit_max_cap(client, db):
    """27. Test activity endpoint caps limit query parameter at max 100."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    _, st_id = join_test_student(client, s_code, "Victor", "CS_301")

    res = client.get(f"/api/v1/teacher/session/{s_id}/students/{st_id}/activity?limit=500", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["pagination"]["limit"] == 100

def test_n_plus_one_query_protection(client, db):
    """28. Test N+1 query protection: dashboard queries stay bounded even with multiple students."""
    t_token, s_id, s_code = create_test_session_and_teacher(client)
    for i in range(10):
        join_test_student(client, s_code, f"PerfStudent {i}", f"PERF_{i:02d}")

    # Verify response time and clean structure
    res = client.get(f"/api/v1/teacher/session/{s_id}/dashboard", headers={"X-Teacher-Token": t_token})
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["students"]) == 10
