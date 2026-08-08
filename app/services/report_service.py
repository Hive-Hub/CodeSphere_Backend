import os
import io
import json
import tempfile
from datetime import datetime, timezone
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.extensions import db
from app.models.session import Session
from app.models.student import Student
from app.models.problem import Problem
from app.models.code_snapshot import CodeSnapshot
from app.models.code_execution import CodeExecution
from app.models.activity_event import ActivityEvent
from app.models.ai_review import AIReview
from app.services.redis_service import get_redis_client
from app.logger import api_logger, error_logger

class ReportService:
    """Session PDF Report Generation & Temporary Storage Service."""

    @classmethod
    def generate_session_report(cls, session_id: int) -> tuple[bytes, str]:
        """Collect all session data and compile professional PDF report."""
        session = Session.query.get(session_id)
        if not session:
            raise ValueError(f"Session ID {session_id} not found")

        # 1. Collect Session Metadata
        students = Student.query.filter_by(session_id=session_id).order_by(Student.joined_at.asc()).all()
        problem = Problem.query.filter_by(session_id=session_id).order_by(Problem.created_at.desc()).first()
        executions = CodeExecution.query.filter_by(session_id=session_id).all()
        activities = ActivityEvent.query.filter_by(session_id=session_id).all()
        ai_reviews = AIReview.query.filter_by(session_id=session_id).all()

        total_students = len(students)
        total_runs = len(executions)
        successful_runs = sum(1 for e in executions if e.exit_code == 0)
        failed_runs = total_runs - successful_runs
        compilation_errors = sum(1 for e in executions if e.status == "compilation_error")
        runtime_errors = sum(1 for e in executions if e.status == "runtime_error")

        created_t = session.created_at
        if created_t and created_t.tzinfo is None:
            created_t = created_t.replace(tzinfo=timezone.utc)

        ended_t = session.ended_at or datetime.now(timezone.utc)
        if ended_t and ended_t.tzinfo is None:
            ended_t = ended_t.replace(tzinfo=timezone.utc)

        created_str = created_t.strftime("%Y-%m-%d %H:%M:%S UTC") if created_t else "N/A"
        ended_str = ended_t.strftime("%Y-%m-%d %H:%M:%S UTC") if ended_t else "N/A"
        
        duration_str = "N/A"
        if created_t:
            duration_secs = int((ended_t - created_t).total_seconds())
            mins, secs = divmod(duration_secs, 60)
            hrs, mins = divmod(mins, 60)
            duration_str = f"{hrs}h {mins}m {secs}s" if hrs > 0 else f"{mins}m {secs}s"

        # 2. Build ReportLab Document
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#1E293B'),
            alignment=1,
            spaceAfter=12
        )
        heading_style = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#2563EB'),
            spaceBefore=12,
            spaceAfter=6
        )
        cell_style = ParagraphStyle(
            'CellText',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#334155')
        )
        cell_bold = ParagraphStyle(
            'CellBold',
            parent=styles['Normal'],
            fontSize=9,
            leading=11,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#0F172A')
        )

        story = []

        # Header Title
        story.append(Paragraph("CodeSphere AI - Session Analytics Report", title_style))
        story.append(Spacer(1, 10))

        # Section 1: Session Overview
        story.append(Paragraph("1. Session Overview", heading_style))
        overview_raw = [
            [Paragraph("Session Code:", cell_bold), Paragraph(str(session.session_code), cell_style), Paragraph("Title:", cell_bold), Paragraph(str(session.title), cell_style)],
            [Paragraph("Teacher Name:", cell_bold), Paragraph(str(session.teacher_name), cell_style), Paragraph("Teacher Email:", cell_bold), Paragraph(str(session.teacher_email), cell_style)],
            [Paragraph("College:", cell_bold), Paragraph(str(session.college), cell_style), Paragraph("Department:", cell_bold), Paragraph(str(session.department), cell_style)],
            [Paragraph("Subject:", cell_bold), Paragraph(str(session.subject), cell_style), Paragraph("Language/Mode:", cell_bold), Paragraph(f"{session.language.upper()} ({session.mode})", cell_style)],
            [Paragraph("Created At:", cell_bold), Paragraph(created_str, cell_style), Paragraph("Ended At:", cell_bold), Paragraph(ended_str, cell_style)],
            [Paragraph("Duration:", cell_bold), Paragraph(duration_str, cell_style), Paragraph("Status:", cell_bold), Paragraph(session.status.upper(), cell_style)]
        ]
        t_overview = Table(overview_raw, colWidths=[90, 180, 90, 180])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        story.append(t_overview)
        story.append(Spacer(1, 12))

        # Section 2: Class Analytics Summary
        story.append(Paragraph("2. Classroom Summary Statistics", heading_style))
        stats_raw = [
            [Paragraph("Metric", cell_bold), Paragraph("Value", cell_bold), Paragraph("Metric", cell_bold), Paragraph("Value", cell_bold)],
            [Paragraph("Total Joined Students", cell_style), Paragraph(str(total_students), cell_style), Paragraph("Total Activity Events", cell_style), Paragraph(str(len(activities)), cell_style)],
            [Paragraph("Total Code Executions", cell_style), Paragraph(str(total_runs), cell_style), Paragraph("Successful Runs", cell_style), Paragraph(str(successful_runs), cell_style)],
            [Paragraph("Failed Executions", cell_style), Paragraph(str(failed_runs), cell_style), Paragraph("Compilation Errors", cell_style), Paragraph(str(compilation_errors), cell_style)],
            [Paragraph("Runtime Errors", cell_style), Paragraph(str(runtime_errors), cell_style), Paragraph("AI Reviews Logged", cell_style), Paragraph(str(len(ai_reviews)), cell_style)]
        ]
        t_stats = Table(stats_raw, colWidths=[130, 140, 130, 140])
        t_stats.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F1F5F9')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_stats)
        story.append(Spacer(1, 12))

        # Section 3: Student Performance Detail
        story.append(Paragraph("3. Student Performance Breakdown", heading_style))
        student_rows = [
            [Paragraph("Name", cell_bold), Paragraph("Roll No", cell_bold), Paragraph("Dept", cell_bold), Paragraph("Year", cell_bold), Paragraph("Runs", cell_bold), Paragraph("AI Prog", cell_bold), Paragraph("Quality", cell_bold)]
        ]

        for s in students:
            s_prog = "N/A"
            s_qual = "N/A"
            s_reviews = [r for r in ai_reviews if r.student_id == s.id]
            for r in s_reviews:
                if r.progress is not None:
                    s_prog = f"{r.progress}%"
                if r.code_quality is not None:
                    s_qual = f"{r.code_quality}/100"

            s_runs = sum(1 for e in executions if e.student_id == s.id)
            student_rows.append([
                Paragraph(s.name[:15], cell_style),
                Paragraph(s.roll_number[:12], cell_style),
                Paragraph(s.department[:8], cell_style),
                Paragraph(s.year[:6], cell_style),
                Paragraph(str(s_runs), cell_style),
                Paragraph(s_prog, cell_style),
                Paragraph(s_qual, cell_style)
            ])

        if len(student_rows) == 1:
            student_rows.append([Paragraph("No students joined", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("0", cell_style), Paragraph("N/A", cell_style), Paragraph("N/A", cell_style)])

        t_students = Table(student_rows, colWidths=[100, 80, 70, 50, 45, 60, 60])
        t_students.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_students)
        story.append(Spacer(1, 12))

        # Section 4: Problem Statement & Reference Solution (Teacher-Only)
        if problem:
            story.append(Paragraph("4. Problem Statement & Reference Solution (Teacher Confidential)", heading_style))
            desc_text = (problem.description[:200] + "...") if len(problem.description or "") > 200 else (problem.description or "None")
            ref_text = (problem.reference_solution[:250] + "...") if len(problem.reference_solution or "") > 250 else (problem.reference_solution or "None")

            prob_raw = [
                [Paragraph("Problem Title:", cell_bold), Paragraph(str(problem.title), cell_style)],
                [Paragraph("Description:", cell_bold), Paragraph(desc_text, cell_style)],
                [Paragraph("Constraints:", cell_bold), Paragraph(str(problem.constraints or "None"), cell_style)],
                [Paragraph("Teacher Reference Solution:", cell_bold), Paragraph(ref_text, cell_style)]
            ]
            t_prob = Table(prob_raw, colWidths=[130, 410])
            t_prob.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FEF3C7')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FDE68A')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t_prob)

        doc.build(story)

        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()

        filename = f"codesphere_session_{session.session_code}_report.pdf"

        # Cache PDF bytes in Redis for temporary direct download
        try:
            r = get_redis_client()
            r.set(f"session:{session_id}:pdf_report", pdf_bytes, ex=86400) # 24 hr TTL
            r.set(f"session:{session_id}:report_status", "ready", ex=86400)
            r.set(f"session:{session_id}:report_filename", filename, ex=86400)
        except Exception as e:
            error_logger.warning(f"Failed to cache PDF report in Redis: {str(e)}")

        return pdf_bytes, filename

    @classmethod
    def get_cached_report(cls, session_id: int) -> tuple[bytes, str]:
        """Retrieve temporarily cached PDF report bytes from Redis."""
        try:
            r = get_redis_client()
            pdf_bytes = r.get(f"session:{session_id}:pdf_report")
            filename = r.get(f"session:{session_id}:report_filename")
            if pdf_bytes:
                fn_str = filename.decode("utf-8") if isinstance(filename, bytes) else (filename or f"codesphere_session_{session_id}_report.pdf")
                return pdf_bytes, fn_str
        except Exception:
            pass

        # Fallback: regenerate if data still exists
        return cls.generate_session_report(session_id)

    @classmethod
    def get_report_status(cls, session_id: int) -> dict:
        """Get report generation status for a session for both PDF and Excel."""
        session = Session.query.get(session_id)
        if not session:
            return {
                "pdf": {"status": "not_found", "download_url": None},
                "excel": {"status": "not_found", "download_url": None}
            }

        st = "ready" if session.status in ["ended", "expired", "cleanup_pending"] else "pending"
        return {
            "pdf": {
                "status": st,
                "download_url": f"/api/v1/teacher/session/{session_id}/report/pdf" if st == "ready" else None
            },
            "excel": {
                "status": st,
                "download_url": f"/api/v1/teacher/session/{session_id}/report/excel" if st == "ready" else None
            }
        }

    @classmethod
    def generate_report_summary(cls, session_id: int) -> dict:
        """Provide report summary payload contract for frontend report page UI."""
        session = Session.query.get(session_id)
        if not session:
            return None

        students = Student.query.filter_by(session_id=session_id).all()
        executions = CodeExecution.query.filter_by(session_id=session_id).all()
        activities = ActivityEvent.query.filter_by(session_id=session_id).all()
        ai_reviews = AIReview.query.filter_by(session_id=session_id).all()

        total_runs = len(executions)
        successful_runs = sum(1 for e in executions if e.exit_code == 0)

        return {
            "session": session.to_dict(include_private=True),
            "summary": {
                "total_students": len(students),
                "total_code_runs": total_runs,
                "successful_runs": successful_runs,
                "failed_runs": total_runs - successful_runs,
                "total_activity_events": len(activities),
                "ai_reviews_count": len(ai_reviews)
            },
            "downloads": {
                "pdf": f"/api/v1/teacher/session/{session_id}/report/pdf",
                "excel": f"/api/v1/teacher/session/{session_id}/report/excel"
            }
        }
