import os
import sys
import requests

def run_smoke_tests():
    """Automated REST API production smoke test script."""
    base_url = os.getenv("PRODUCTION_URL", "http://localhost:5000").rstrip("/")
    print(f"==================================================")
    print(f"RUNNING CODESPHERE PRODUCTION REST SMOKE TEST")
    print(f"Target Base URL: {base_url}")
    print(f"==================================================")

    # 1. GET /health
    health_url = f"{base_url}/api/v1/health"
    print(f"1. Testing GET {health_url}...")
    r = requests.get(health_url)
    assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
    print("   [PASS] Health check returned 200 OK")

    # 2. Teacher Creates Session
    create_url = f"{base_url}/api/v1/teacher/session/create"
    print(f"2. Testing POST {create_url}...")
    s_payload = {
        "teacher_name": "Smoke Teacher",
        "teacher_email": "smoke@codesphere.ai",
        "college": "Render Tech",
        "department": "CS",
        "subject": "Prod Lab",
        "title": "Smoke Test Session",
        "language": "python",
        "mode": "practice"
    }
    r = requests.post(create_url, json=s_payload)
    assert r.status_code == 201, f"Session create failed: {r.status_code} {r.text}"
    s_data = r.json()["data"]
    teacher_token = s_data["teacher_token"]
    session_id = s_data["session"]["id"]
    session_code = s_data["session"]["session_code"]
    print(f"   [PASS] Created Session ID {session_id} with Code {session_code}")

    # 3. Public Session Status
    status_url = f"{base_url}/api/v1/session/{session_code}/status"
    print(f"3. Testing GET {status_url}...")
    r = requests.get(status_url)
    assert r.status_code == 200, f"Status check failed: {r.status_code}"
    print("   [PASS] Public status validated")

    # 4. Student Joins Session
    join_url = f"{base_url}/api/v1/student/session/join"
    print(f"4. Testing POST {join_url}...")
    j_payload = {
        "session_code": session_code,
        "name": "Smoke Student",
        "roll_number": "SMK_001",
        "department": "CS",
        "year": "4th",
        "section": "A"
    }
    r = requests.post(join_url, json=j_payload)
    assert r.status_code == 200, f"Student join failed: {r.status_code} {r.text}"
    j_data = r.json()["data"]
    student_token = j_data["student_token"]
    student_id = j_data["student"]["id"]
    print(f"   [PASS] Student ID {student_id} joined session")

    # 5. Teacher Dashboard
    dash_url = f"{base_url}/api/v1/teacher/session/{session_id}/dashboard"
    print(f"5. Testing GET {dash_url}...")
    r = requests.get(dash_url, headers={"X-Teacher-Token": teacher_token})
    assert r.status_code == 200, f"Dashboard failed: {r.status_code}"
    print("   [PASS] Teacher Dashboard accessible")

    # 6. Student Saves Code
    save_url = f"{base_url}/api/v1/student/session/{session_id}/code/save"
    print(f"6. Testing POST {save_url}...")
    r = requests.post(save_url, json={"code": "print('Smoke Test OK')"}, headers={"X-Student-Token": student_token})
    assert r.status_code == 200, f"Code save failed: {r.status_code}"
    print("   [PASS] Student Code Saved")

    # 7. Student Executes Code
    run_url = f"{base_url}/api/v1/student/session/{session_id}/code/run"
    print(f"7. Testing POST {run_url}...")
    r = requests.post(run_url, json={"language": "python", "code": "print('Smoke Execution')"}, headers={"X-Student-Token": student_token})
    assert r.status_code in [200, 202], f"Code run failed: {r.status_code}"
    print("   [PASS] Code Execution dispatched")

    # 8. Teacher Ends Session & Report Check
    end_url = f"{base_url}/api/v1/teacher/session/{session_id}/end"
    print(f"8. Testing POST {end_url}...")
    r = requests.post(end_url, headers={"X-Teacher-Token": teacher_token})
    assert r.status_code == 200, f"End session failed: {r.status_code}"
    print("   [PASS] Session Ended & Reports Generated")

    print(f"==================================================")
    print(f"ALL PRODUCTION REST SMOKE TESTS PASSED!")
    print(f"==================================================")

if __name__ == "__main__":
    try:
        run_smoke_tests()
    except Exception as e:
        print(f"SMOKE TEST FAILED: {str(e)}")
        sys.exit(1)
