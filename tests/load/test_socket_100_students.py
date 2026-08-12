import time
import pytest
from app.extensions import socketio

def test_socket_100_concurrent_clients_simulation(app):
    """Simulate 100 concurrent Socket.IO clients joining rooms and sending typing/code events."""
    client_count = 100
    session_id = 888

    latencies = []
    start_total = time.time()

    with app.app_context():
        # Create 100 socket test clients
        clients = []
        for i in range(1, client_count + 1):
            t0 = time.time()
            client = socketio.test_client(app)
            clients.append(client)
            latencies.append((time.time() - t0) * 1000)

        # 1. Join room
        for i, client in enumerate(clients, start=1):
            t0 = time.time()
            client.emit("student_join_session", {"session_id": session_id, "student_id": i, "name": f"Student {i}"})
            latencies.append((time.time() - t0) * 1000)

        # 2. Emit typing events
        for i, client in enumerate(clients, start=1):
            t0 = time.time()
            client.emit("typing_start", {"session_id": session_id, "student_id": i})
            client.emit("code_change", {"session_id": session_id, "student_id": i, "code": f"print({i})"})
            client.emit("typing_stop", {"session_id": session_id, "student_id": i})
            latencies.append((time.time() - t0) * 1000)

        # 3. Disconnect clients
        for client in clients:
            client.disconnect()

        total_elapsed = time.time() - start_total
        total_ops = len(latencies)
        ops_per_sec = total_ops / total_elapsed if total_elapsed > 0 else 0

        latencies.sort()
        avg_latency = sum(latencies) / len(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]

        print(f"\n--- SOCKET.IO 100 CLIENTS LOAD TEST RESULTS ---")
        print(f"Total Clients Simulated: {client_count}")
        print(f"Total Operations: {total_ops}")
        print(f"Total Time: {total_elapsed:.4f} sec")
        print(f"Throughput: {ops_per_sec:.2f} ops/sec")
        print(f"Average Latency: {avg_latency:.2f} ms")
        print(f"P95 Latency: {p95:.2f} ms")
        print(f"P99 Latency: {p99:.2f} ms")

        assert avg_latency < 100.0
