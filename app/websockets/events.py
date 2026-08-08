from datetime import datetime, timezone
from flask import request
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from app.models.student import Student
from app.models.session import Session
from app.models.activity_event import SUPPORTED_EVENT_TYPES
from app.services.online_compiler import OnlineCompilerService
from app.services.presence_service import (
    set_student_online, set_student_offline, update_student_heartbeat
)
from app.services.code_service import (
    set_student_live_code, set_student_typing_status, save_code_snapshot, record_activity_event, MAX_CODE_SIZE_BYTES
)
from app.tasks.code_tasks import persist_debounced_code_snapshot
from app.logger import socketio_logger

# ------------------------------------------------------------------------------
# PHASE 0 SOCKET.IO CORE EVENTS
# ------------------------------------------------------------------------------

@socketio.on("connect")
def handle_connect():
    """Client WebSocket connection handler."""
    socketio_logger.info(f"Socket.IO client connected: {request.sid}")
    emit("connection_response", {
        "status": "connected",
        "sid": request.sid,
        "message": "Connected to CodeSphere Socket.IO server"
    })

@socketio.on("disconnect")
def handle_disconnect():
    """Client WebSocket disconnection handler."""
    socketio_logger.info(f"Socket.IO client disconnected: {request.sid}")

@socketio.on("ping")
def handle_ping(data=None):
    """Ping event handler returning pong payload."""
    socketio_logger.info(f"Received Socket.IO ping from {request.sid}")
    emit("pong", {"status": "success", "message": "pong", "data": data or {}})

@socketio.on("execute_code")
def handle_code_execution(data):
    """Legacy test execution handler."""
    language = data.get("language")
    code = data.get("code")
    stdin = data.get("stdin", "")
    if not language or not code:
        emit("execution_result", {"success": False, "error": "Missing language or code"})
        return
    result = OnlineCompilerService.execute_code(language, code, stdin)
    emit("execution_result", result)

# ------------------------------------------------------------------------------
# PHASE 1 & 2 SESSION WEBSOCKET EVENTS
# ------------------------------------------------------------------------------

@socketio.on("student_join_session")
def handle_student_join_session(data):
    """Event triggered when a student connects to a session room."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    
    if not session_id or not student_id:
        emit("error", {"message": "session_id and student_id are required"})
        return

    room_name = f"session:{session_id}"
    join_room(room_name)
    socketio_logger.info(f"Student {student_id} joined room {room_name}")

    student = Student.query.get(student_id)
    if student:
        student.status = "online"
        student.last_active = datetime.now(timezone.utc)
        db.session.commit()

    set_student_online(session_id, student_id, request.sid)

    payload = {
        "event": "student_joined",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student.name if student else "Student",
        "roll_number": student.roll_number if student else ""
    }
    emit("student_joined", payload, to=room_name)
    emit("student_online", payload, to=room_name)

@socketio.on("student_leave_session")
def handle_student_leave_session(data):
    """Event triggered when a student leaves a session room."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    if not session_id or not student_id:
        return

    room_name = f"session:{session_id}"
    socketio_logger.info(f"Student {student_id} left room {room_name}")
    student = Student.query.get(student_id)

    payload = {
        "event": "student_left",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student.name if student else "Student"
    }
    emit("student_left", payload, to=room_name)
    emit("student_offline", payload, to=room_name)

    leave_room(room_name)

    if student:
        student.status = "offline"
        student.last_active = datetime.now(timezone.utc)
        db.session.commit()

    set_student_offline(session_id, student_id)

@socketio.on("student_heartbeat")
def handle_student_heartbeat(data):
    """Event triggered periodically by student client."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    if not session_id or not student_id:
        return

    student = Student.query.get(student_id)
    if student:
        student.last_active = datetime.now(timezone.utc)
        db.session.commit()

    update_student_heartbeat(session_id, student_id)
    emit("heartbeat_ack", {"status": "received", "timestamp": datetime.now(timezone.utc).isoformat()})

# ------------------------------------------------------------------------------
# PHASE 2 REAL-TIME CODING & ACTIVITY BROADCAST EVENTS
# ------------------------------------------------------------------------------

@socketio.on("code_change")
def handle_code_change(data):
    """Real-time code change event emitted by student."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    code = data.get("code", "")
    cursor = data.get("cursor", {"line": 1, "column": 1})

    if not session_id or not student_id:
        emit("error", {"message": "session_id and student_id are required"})
        return

    if len(code.encode("utf-8")) > MAX_CODE_SIZE_BYTES:
        emit("error", {"message": "Code payload exceeds size limit"})
        return

    # Update Redis live state
    set_student_live_code(student_id, session_id, code, cursor)

    # Schedule debounced Celery snapshot save (3s delay)
    session = Session.query.get(session_id)
    language = session.language if session else "python"
    try:
        persist_debounced_code_snapshot.apply_async(
            args=[session_id, student_id, language, code],
            countdown=3
        )
    except Exception as e:
        socketio_logger.warning(f"Could not queue Celery debounced snapshot: {str(e)}")

    student = Student.query.get(student_id)
    room_name = f"session:{session_id}"

    # Broadcast student_code_updated to teacher room
    emit("student_code_updated", {
        "event": "student_code_updated",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student.name if student else "Student",
        "roll_number": student.roll_number if student else "",
        "code": code,
        "cursor": cursor,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

@socketio.on("typing_start")
def handle_typing_start(data):
    """Student typing start event."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    if not session_id or not student_id:
        return

    set_student_typing_status(student_id, True, session_id=session_id)
    student = Student.query.get(student_id)
    room_name = f"session:{session_id}"

    emit("student_typing", {
        "event": "student_typing",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student.name if student else "Student",
        "roll_number": student.roll_number if student else "",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

@socketio.on("typing_stop")
def handle_typing_stop(data):
    """Student typing stop event."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    if not session_id or not student_id:
        return

    set_student_typing_status(student_id, False, session_id=session_id)
    student = Student.query.get(student_id)
    room_name = f"session:{session_id}"

    emit("student_stopped_typing", {
        "event": "student_stopped_typing",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student.name if student else "Student",
        "roll_number": student.roll_number if student else "",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

@socketio.on("cursor_move")
def handle_cursor_move(data):
    """Student cursor movement event."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    line = data.get("line", 1)
    column = data.get("column", 1)
    if not session_id or not student_id:
        return

    cursor_dict = {"line": line, "column": column}
    room_name = f"session:{session_id}"

    emit("student_cursor_updated", {
        "event": "student_cursor_updated",
        "session_id": session_id,
        "student_id": student_id,
        "cursor": cursor_dict,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

@socketio.on("code_save")
def handle_code_save(data):
    """Student explicit code save event via Socket.IO."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    code = data.get("code", "")
    language = data.get("language")

    if not session_id or not student_id:
        return

    session = Session.query.get(session_id)
    lang = language or (session.language if session else "python")

    set_student_live_code(student_id, session_id, code)
    snapshot = save_code_snapshot(session_id, student_id, lang, code)

    room_name = f"session:{session_id}"
    emit("student_code_saved", {
        "event": "student_code_saved",
        "session_id": session_id,
        "student_id": student_id,
        "version": snapshot.version,
        "saved_at": snapshot.created_at.isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

@socketio.on("activity_event")
def handle_activity_event(data):
    """Activity tracking event (copy, paste, tab blur, tab focus, etc.)."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    event_type = data.get("event_type")
    meta = data.get("metadata", {})

    if not session_id or not student_id or not event_type:
        return

    if event_type in SUPPORTED_EVENT_TYPES:
        record_activity_event(session_id, student_id, event_type, meta)
        room_name = f"session:{session_id}"
        emit("student_activity", {
            "event": "student_activity",
            "session_id": session_id,
            "student_id": student_id,
            "event_type": event_type,
            "metadata": meta,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, to=room_name)

@socketio.on("run_code")
def handle_run_code(data):
    """Real-time code execution with compiler status broadcasts."""
    session_id = data.get("session_id")
    student_id = data.get("student_id")
    language = data.get("language", "python")
    code = data.get("code", "")
    stdin = data.get("stdin", "")

    if not session_id or not student_id or not code:
        emit("execution_result", {"success": False, "error": "session_id, student_id, and code are required"})
        return

    room_name = f"session:{session_id}"

    student = Student.query.get(student_id)
    student_name = student.name if student else "Student"
    roll_number = student.roll_number if student else ""

    # Mark running status in Redis
    from app.services.presence_service import set_student_running_status
    set_student_running_status(session_id, student_id, True)

    # 1. Notify teacher room compiler started
    emit("compiler_started", {
        "event": "compiler_started",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student_name,
        "roll_number": roll_number,
        "language": language,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)

    # Record run_code activity event
    record_activity_event(session_id, student_id, "run_code", {"language": language})

    # 2. Execute via OnlineCompilerService
    start_time = datetime.now(timezone.utc)
    try:
        result = OnlineCompilerService.execute_code(language, code, stdin)
    finally:
        set_student_running_status(session_id, student_id, False)

    end_time = datetime.now(timezone.utc)
    exec_duration = round((end_time - start_time).total_seconds(), 3)

    # 3. Emit result to requesting student
    emit("execution_result", result)

    # 4. Broadcast compiler_completed to teacher room
    emit("compiler_completed", {
        "event": "compiler_completed",
        "session_id": session_id,
        "student_id": student_id,
        "student_name": student_name,
        "roll_number": roll_number,
        "status": result.get("status", "success" if result.get("success") else "failed"),
        "output": result.get("output", ""),
        "error": result.get("error", ""),
        "execution_time": result.get("execution_time", f"{exec_duration}s"),
        "memory": result.get("memory", "0KB"),
        "error_present": bool(result.get("error") or not result.get("success")),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }, to=room_name)
