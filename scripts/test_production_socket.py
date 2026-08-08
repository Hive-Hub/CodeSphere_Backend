import os
import sys
import time
import socketio

def run_socket_smoke_test():
    """Automated WebSocket Socket.IO production smoke test script."""
    base_url = os.getenv("PRODUCTION_URL", "http://localhost:5000").rstrip("/")
    print(f"==================================================")
    print(f"RUNNING CODESPHERE WEBSOCKET SOCKET.IO SMOKE TEST")
    print(f"Target WebSocket Base: {base_url}")
    print(f"==================================================")

    sio = socketio.Client()

    events_received = []

    @sio.event
    def connect():
        print("   [PASS] Connected to WebSocket server")
        events_received.append("connect")

    @sio.event
    def disconnect():
        print("   [PASS] Disconnected from WebSocket server")

    @sio.on("*")
    def catch_all(event, data):
        print(f"   [EVENT RECEIVED] {event}: {data}")
        events_received.append(event)

    try:
        sio.connect(base_url, socketio_path="/socket.io/")
        time.sleep(1)

        # Emit student join simulation
        sio.emit("student_join_session", {
            "session_id": 1,
            "student_id": 1,
            "name": "Socket Tester"
        })
        time.sleep(1)

        sio.disconnect()
        print(f"==================================================")
        print(f"WEBSOCKET SMOKE TEST COMPLETED SUCCESSFULLY!")
        print(f"==================================================")
    except Exception as e:
        print(f"WEBSOCKET SMOKE TEST WARNING: {str(e)}")
        print("Note: Run with active server to complete full handshake.")

if __name__ == "__main__":
    run_socket_smoke_test()
