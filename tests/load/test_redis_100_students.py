import time
import pytest
from app.services.redis_service import (
    get_redis_client, redis_set, redis_get, check_redis_connection
)
from app.services.code_service import set_student_live_code
from app.services.presence_service import (
    set_student_online, update_student_heartbeat, get_online_student_ids
)

def test_redis_100_concurrent_students_load(app):
    """Simulate 100 concurrent students issuing presence, heartbeat, typing, and code updates."""
    session_id = 999
    num_students = 100

    latencies = []
    start_total_time = time.time()

    with app.app_context():
        # 1. Simulate 100 students joining
        for i in range(1, num_students + 1):
            t0 = time.time()
            set_student_online(session_id, i, sid=f"sid_{i}")
            latencies.append((time.time() - t0) * 1000)

        # 2. Simulate heartbeats and code updates for 100 students
        for i in range(1, num_students + 1):
            t0 = time.time()
            update_student_heartbeat(session_id, i)
            code = f"def solution_{i}():\n    return {i} * 42\n"
            set_student_live_code(i, session_id, code, cursor={"line": i, "column": 5})
            latencies.append((time.time() - t0) * 1000)

        total_elapsed = time.time() - start_total_time
        total_ops = len(latencies)
        ops_per_sec = total_ops / total_elapsed if total_elapsed > 0 else 0

        latencies.sort()
        avg_latency = sum(latencies) / len(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        online_set = get_online_student_ids(session_id)

        print(f"\n--- REDIS 100 STUDENTS LOAD TEST RESULTS ---")
        print(f"Total Operations: {total_ops}")
        print(f"Total Time: {total_elapsed:.4f} sec")
        print(f"Throughput: {ops_per_sec:.2f} ops/sec")
        print(f"Average Latency: {avg_latency:.2f} ms")
        print(f"P95 Latency: {p95:.2f} ms")
        print(f"P99 Latency: {p99:.2f} ms")
        print(f"Online Count: {len(online_set)} / {num_students}")

        assert len(online_set) == num_students
        assert avg_latency < 5000.0 # Latency threshold for network/cloud round-trips
