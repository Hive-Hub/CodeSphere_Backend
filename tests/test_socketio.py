def test_socketio_connection_and_ping(socket_client):
    """Test Socket.IO connection handshake and ping event."""
    assert socket_client.is_connected()
    
    # Check initial connection response
    received = socket_client.get_received()
    assert len(received) > 0
    assert received[0]["name"] == "connection_response"
    assert received[0]["args"][0]["status"] == "connected"
    
    # Emit ping event
    socket_client.emit("ping", {"timestamp": 123456789})
    received_ping = socket_client.get_received()
    assert len(received_ping) > 0
    assert received_ping[0]["name"] == "pong"
    assert received_ping[0]["args"][0]["message"] == "pong"

def test_socketio_execute_code_event(socket_client):
    """Test Socket.IO real-time execute_code event for Python code."""
    socket_client.emit("execute_code", {
        "language": "python",
        "code": "print('SocketIO Test')",
        "stdin": ""
    })
    
    received = socket_client.get_received()
    # Filter out connection response if present
    exec_events = [r for r in received if r["name"] == "execution_result"]
    assert len(exec_events) > 0
    payload = exec_events[0]["args"][0]
    assert payload["success"] is True
    assert "output" in payload
