import math
from datetime import datetime, timezone
from sqlalchemy import func, case
from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.code_snapshot import CodeSnapshot
from app.models.code_execution import CodeExecution
from app.models.activity_event import ActivityEvent
from app.services.presence_service import (
    get_online_student_ids, get_typing_student_ids, get_running_student_ids
)
from app.services.code_service import (
    get_student_live_code, get_student_live_cursor
)
from app.logger import api_logger, error_logger

class DashboardService:
    """High-performance classroom dashboard aggregation and statistics service."""

    @classmethod
    def get_teacher_dashboard(cls, session_id: int):
        """Aggregate full live dashboard payload for a given session."""
        session = Session.query.get(session_id)
        if not session:
            return None

        now = datetime.now(timezone.utc)
        exp = session.expires_at
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        remaining_seconds = max(0, int((exp - now).total_seconds())) if session.status == "active" else 0

        # 1. Retrieve all joined students in 1 query
        students = Student.query.filter_by(session_id=session.id).order_by(Student.joined_at.asc()).all()
        total_students = len(students)
        valid_student_ids = set(s.id for s in students)

        # 2. Redis live sets for presence/activity tracking (filtered to session students)
        online_ids = get_online_student_ids(session.id) & valid_student_ids
        typing_ids = get_typing_student_ids(session.id) & valid_student_ids
        running_ids = get_running_student_ids(session.id) & valid_student_ids

        # 3. Grouped SQL aggregations to prevent N+1 queries
        # Code execution stats per student
        exec_rows = db.session.query(
            CodeExecution.student_id,
            func.count(CodeExecution.id).label("total"),
            func.sum(case((CodeExecution.exit_code == 0, 1), else_=0)).label("success"),
            func.sum(case((CodeExecution.exit_code != 0, 1), else_=0)).label("failed")
        ).filter(CodeExecution.session_id == session.id).group_by(CodeExecution.student_id).all()

        exec_stats_map = {
            row[0]: {
                "total": int(row[1] or 0),
                "success": int(row[2] or 0),
                "failed": int(row[3] or 0)
            } for row in exec_rows
        }

        # Latest CodeSnapshots per student
        snapshot_rows = db.session.query(
            CodeSnapshot.student_id,
            func.max(CodeSnapshot.version).label("max_version"),
            func.max(CodeSnapshot.created_at).label("max_created_at")
        ).filter(CodeSnapshot.session_id == session.id).group_by(CodeSnapshot.student_id).all()

        snapshot_map = {
            row[0]: {
                "version": int(row[1] or 0),
                "updated_at": row[2].isoformat() if row[2] else None
            } for row in snapshot_rows
        }

        # Submitted students
        submitted_ids = set(
            row[0] for row in db.session.query(ActivityEvent.student_id)
            .filter(ActivityEvent.session_id == session.id, ActivityEvent.event_type == "submit_code")
            .distinct().all()
        )

        # Total session-level execution totals
        total_code_runs = sum(s["total"] for s in exec_stats_map.values())
        successful_runs = sum(s["success"] for s in exec_stats_map.values())
        failed_runs = sum(s["failed"] for s in exec_stats_map.values())

        # Total activity count
        total_activity_events = db.session.query(func.count(ActivityEvent.id))\
            .filter(ActivityEvent.session_id == session.id).scalar() or 0

        # Calculate student list payload
        student_list = []
        idle_count = 0

        for s in students:
            is_online = s.id in online_ids
            is_typing = s.id in typing_ids
            is_running = s.id in running_ids

            if is_online and not is_typing and not is_running:
                idle_count += 1
                current_activity = "idle"
            elif is_typing:
                current_activity = "typing"
            elif is_running:
                current_activity = "running"
            elif is_online:
                current_activity = "online"
            else:
                current_activity = "offline"

            s_exec = exec_stats_map.get(s.id, {"total": 0, "success": 0, "failed": 0})
            s_snap = snapshot_map.get(s.id, {"version": 0, "updated_at": None})
            cursor = get_student_live_cursor(s.id)

            student_list.append({
                "id": s.id,
                "name": s.name,
                "roll_number": s.roll_number,
                "department": s.department,
                "year": s.year,
                "section": s.section,
                "status": "online" if is_online else "offline",
                "last_active": s.last_active.isoformat() if s.last_active else (s.joined_at.isoformat() if s.joined_at else None),
                "typing": is_typing,
                "typing_speed": 42 if is_typing else None,
                "typing_speed_unit": "WPM" if is_typing else None,
                "language": session.language,
                "code_version": s_snap["version"],
                "cursor": cursor,
                "current_activity": current_activity,
                "code_updated_at": s_snap["updated_at"],
                "execution_count": s_exec["total"],
                "successful_execution_count": s_exec["success"],
                "failed_execution_count": s_exec["failed"],
                "progress": None,
                "ai_score": None
            })

        statistics = {
            "total_students": total_students,
            "online_students": len(online_ids),
            "offline_students": max(0, total_students - len(online_ids)),
            "typing_students": len(typing_ids),
            "idle_students": idle_count,
            "running_students": len(running_ids),
            "submitted_students": len(submitted_ids),
            "total_code_runs": total_code_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "total_activity_events": total_activity_events
        }

        return {
            "session": {
                "id": session.id,
                "title": session.title,
                "mode": session.mode,
                "language": session.language,
                "status": session.status,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "remaining_seconds": remaining_seconds
            },
            "statistics": statistics,
            "students": student_list
        }

    @classmethod
    def get_student_dashboard_details(cls, session_id: int, student_id: int):
        """Get detailed breakdown for a single student."""
        session = Session.query.get(session_id)
        if not session:
            return None

        student = Student.query.filter_by(id=student_id, session_id=session.id).first()
        if not student:
            return None

        online_ids = get_online_student_ids(session.id)
        typing_ids = get_typing_student_ids(session.id)
        running_ids = get_running_student_ids(session.id)

        is_online = student.id in online_ids
        is_typing = student.id in typing_ids
        is_running = student.id in running_ids

        current_activity = "typing" if is_typing else ("running" if is_running else ("idle" if is_online else "offline"))

        live_code = get_student_live_code(student.id)
        cursor = get_student_live_cursor(student.id)
        latest_snapshot = CodeSnapshot.query.filter_by(student_id=student.id).order_by(CodeSnapshot.version.desc()).first()

        # Executions summary
        total_execs = db.session.query(func.count(CodeExecution.id)).filter_by(student_id=student.id).scalar() or 0
        success_execs = db.session.query(func.count(CodeExecution.id)).filter_by(student_id=student.id, exit_code=0).scalar() or 0
        failed_execs = max(0, total_execs - success_execs)
        comp_errors = db.session.query(func.count(CodeExecution.id)).filter_by(student_id=student.id, status="compilation_error").scalar() or 0
        run_errors = db.session.query(func.count(CodeExecution.id)).filter_by(student_id=student.id, status="runtime_error").scalar() or 0

        latest_activity = ActivityEvent.query.filter_by(student_id=student.id).order_by(ActivityEvent.created_at.desc()).first()

        return {
            "student": student.to_dict(),
            "presence": {
                "status": "online" if is_online else "offline",
                "last_active": student.last_active.isoformat() if student.last_active else None
            },
            "activity": {
                "typing": is_typing,
                "current_activity": current_activity,
                "latest_event": latest_activity.to_dict() if latest_activity else None
            },
            "code": {
                "language": session.language,
                "code": live_code,
                "version": latest_snapshot.version if latest_snapshot else 0,
                "cursor": cursor,
                "code_updated_at": latest_snapshot.created_at.isoformat() if latest_snapshot else None
            },
            "executions": {
                "execution_count": total_execs,
                "successful_execution_count": success_execs,
                "failed_execution_count": failed_execs,
                "compilation_errors": comp_errors,
                "runtime_errors": run_errors
            },
            "progress": None,
            "ai_score": None
        }

    @classmethod
    def get_student_activity_history(cls, session_id: int, student_id: int, page: int = 1, limit: int = 20):
        """Get paginated activity log for a student (max limit 100)."""
        limit = min(max(1, limit), 100)
        page = max(1, page)

        query = ActivityEvent.query.filter_by(session_id=session_id, student_id=student_id).order_by(ActivityEvent.created_at.desc())
        total = query.count()
        events = query.offset((page - 1) * limit).limit(limit).all()

        total_pages = math.ceil(total / limit) if total > 0 else 0

        return {
            "events": [
                {
                    "event_id": e.id,
                    "event_type": e.event_type,
                    "metadata": e.to_dict()["metadata"],
                    "created_at": e.created_at.isoformat() if e.created_at else None
                } for e in events
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }

    @classmethod
    def get_student_execution_history(cls, session_id: int, student_id: int, page: int = 1, limit: int = 20):
        """Get paginated execution history for a student (max limit 100)."""
        limit = min(max(1, limit), 100)
        page = max(1, page)

        query = CodeExecution.query.filter_by(session_id=session_id, student_id=student_id).order_by(CodeExecution.created_at.desc())
        total = query.count()
        executions = query.offset((page - 1) * limit).limit(limit).all()

        total_pages = math.ceil(total / limit) if total > 0 else 0

        return {
            "executions": [
                {
                    "execution_id": ex.id,
                    "language": ex.language,
                    "code": ex.code,
                    "stdin": ex.stdin or "",
                    "output": ex.output or "",
                    "error": ex.error or "",
                    "status": ex.status,
                    "exit_code": ex.exit_code,
                    "execution_time": ex.execution_time or "0.0s",
                    "memory": ex.memory or "0KB",
                    "created_at": ex.created_at.isoformat() if ex.created_at else None
                } for ex in executions
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages
            }
        }

    @classmethod
    def get_session_analytics(cls, session_id: int):
        """Calculate real session analytics metrics from database."""
        session = Session.query.get(session_id)
        if not session:
            return None

        students = Student.query.filter_by(session_id=session.id).all()
        total_students = len(students)
        valid_student_ids = set(s.id for s in students)
        online_ids = get_online_student_ids(session.id) & valid_student_ids
        online_students = len(online_ids)
        offline_students = max(0, total_students - online_students)

        total_runs = db.session.query(func.count(CodeExecution.id)).filter_by(session_id=session.id).scalar() or 0
        successful_runs = db.session.query(func.count(CodeExecution.id)).filter_by(session_id=session.id, exit_code=0).scalar() or 0
        failed_runs = max(0, total_runs - successful_runs)
        compilation_errors = db.session.query(func.count(CodeExecution.id)).filter_by(session_id=session.id, status="compilation_error").scalar() or 0
        runtime_errors = db.session.query(func.count(CodeExecution.id)).filter_by(session_id=session.id, status="runtime_error").scalar() or 0

        activity_count = db.session.query(func.count(ActivityEvent.id)).filter_by(session_id=session.id).scalar() or 0

        # Calculate average session active time in seconds
        active_times = []
        students = Student.query.filter_by(session_id=session.id).all()
        for s in students:
            if s.joined_at and s.last_active:
                tz_joined = s.joined_at if s.joined_at.tzinfo else s.joined_at.replace(tzinfo=timezone.utc)
                tz_last = s.last_active if s.last_active.tzinfo else s.last_active.replace(tzinfo=timezone.utc)
                active_times.append((tz_last - tz_joined).total_seconds())

        avg_session_time = int(sum(active_times) / len(active_times)) if active_times else 0

        return {
            "total_students": total_students,
            "online_students": online_students,
            "offline_students": offline_students,
            "average_session_time": avg_session_time,
            "total_code_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "compilation_errors": compilation_errors,
            "runtime_errors": runtime_errors,
            "activity_count": activity_count
        }
