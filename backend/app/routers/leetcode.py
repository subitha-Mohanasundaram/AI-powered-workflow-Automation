"""
LeetCode Tracker Router — includes HTML dashboard at /leetcode
"""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..logging_config import get_logger
from ..models import LeetCodeReport, LeetCodeStudent
from ..security import require_api_key
from ..services.leetcode import fetch_student_stats, generate_class_report
from ..services.ai import AIInterpreterService, _get_client

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/leetcode",
    tags=["leetcode"],
    dependencies=[Depends(require_api_key)],
)

templates = Jinja2Templates(directory="backend/app/templates")


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def leetcode_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("leetcode.html", {"request": request})


# ── Request / Response models ─────────────────────────────────────────────────

class AddStudentRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, description="LeetCode username")
    real_name: str = Field(default="", max_length=128, description="Student's real name (optional)")
    batch: str = Field(default="default", max_length=64, description="Batch/class name")


class AskRequest(BaseModel):
    question: str = Field(
        ..., min_length=5, max_length=500,
        description="Plain English question about your students",
        examples=["Who solved the most problems today?", "Show me the topic breakdown for the class"]
    )
    batch: str = Field(default="default", description="Which batch to query")


# ── Student management ────────────────────────────────────────────────────────

@router.post("/students", summary="Add a student to the tracker")
def add_student(body: AddStudentRequest, db: Session = Depends(get_db)) -> dict:
    existing = db.query(LeetCodeStudent).filter(LeetCodeStudent.username == body.username).first()
    if existing:
        if not existing.is_active:
            existing.is_active = 1
            db.commit()
            return {"message": f"{body.username} re-activated", "username": body.username}
        raise HTTPException(status_code=409, detail=f"Student '{body.username}' already exists")

    # Verify the username exists on LeetCode
    stats = fetch_student_stats(body.username)
    if not stats.get("found"):
        raise HTTPException(
            status_code=404,
            detail=f"LeetCode username '{body.username}' not found. Check the spelling."
        )

    student = LeetCodeStudent(
        username=body.username,
        real_name=body.real_name or stats.get("real_name", body.username),
        batch=body.batch,
    )
    db.add(student)
    db.commit()
    logger.info("Student added | username=%s | batch=%s", body.username, body.batch)
    return {
        "message": f"Student '{body.username}' added successfully",
        "username": body.username,
        "real_name": student.real_name,
        "total_solved": stats["solved"]["total"],
    }


@router.delete("/students/{username}", summary="Remove a student")
def remove_student(username: str, db: Session = Depends(get_db)) -> dict:
    student = db.query(LeetCodeStudent).filter(LeetCodeStudent.username == username).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student '{username}' not found")
    student.is_active = 0
    db.commit()
    return {"message": f"Student '{username}' removed"}


@router.get("/students", summary="List all tracked students")
def list_students(batch: str = "default", db: Session = Depends(get_db)) -> dict:
    students = (
        db.query(LeetCodeStudent)
        .filter(LeetCodeStudent.batch == batch, LeetCodeStudent.is_active == 1)
        .all()
    )
    return {
        "batch": batch,
        "count": len(students),
        "students": [
            {"username": s.username, "real_name": s.real_name, "added_at": s.added_at.isoformat()}
            for s in students
        ],
    }


# ── Individual student stats ──────────────────────────────────────────────────

@router.get("/student/{username}", summary="Get live stats for one student")
def get_student_stats(username: str) -> dict:
    stats = fetch_student_stats(username)
    if not stats.get("found"):
        raise HTTPException(status_code=404, detail=stats.get("error", "User not found"))
    return stats


# ── Class report ──────────────────────────────────────────────────────────────

@router.get("/report", summary="Generate live class report")
def get_class_report(batch: str = "default", save: bool = True, db: Session = Depends(get_db)) -> dict:
    students = (
        db.query(LeetCodeStudent)
        .filter(LeetCodeStudent.batch == batch, LeetCodeStudent.is_active == 1)
        .all()
    )
    if not students:
        raise HTTPException(
            status_code=404,
            detail=f"No students in batch '{batch}'. Add students first via POST /api/leetcode/students"
        )

    usernames = [s.username for s in students]
    logger.info("Generating report | batch=%s | students=%d", batch, len(usernames))
    report = generate_class_report(usernames)

    # Save report to DB for history
    if save and "error" not in report:
        record = LeetCodeReport(
            batch=batch,
            report_json=json.dumps(report),
        )
        db.add(record)
        db.commit()
        logger.info("Report saved | batch=%s | id=%d", batch, record.id)

    return report


@router.get("/report/history", summary="List previously saved reports")
def report_history(batch: str = "default", limit: int = 10, db: Session = Depends(get_db)) -> dict:
    reports = (
        db.query(LeetCodeReport)
        .filter(LeetCodeReport.batch == batch)
        .order_by(LeetCodeReport.generated_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "batch": batch,
        "count": len(reports),
        "reports": [
            {
                "id": r.id,
                "generated_at": r.generated_at.isoformat(),
                "summary": json.loads(r.report_json).get("summary", {}),
            }
            for r in reports
        ],
    }


# ── Natural language Q&A ──────────────────────────────────────────────────────

@router.post("/ask", summary="Ask anything about your students in plain English")
def ask_about_students(body: AskRequest, db: Session = Depends(get_db)) -> dict:
    """
    Ask questions like:
    - "Who solved the most problems today?"
    - "Which topics is the class weakest in?"
    - "How many students are active this week?"
    - "Who has the highest contest rating?"
    - "Show me students who haven't solved anything today"
    """
    students = (
        db.query(LeetCodeStudent)
        .filter(LeetCodeStudent.batch == body.batch, LeetCodeStudent.is_active == 1)
        .all()
    )
    if not students:
        raise HTTPException(status_code=404, detail=f"No students in batch '{body.batch}'")

    usernames = [s.username for s in students]
    report = generate_class_report(usernames)

    if "error" in report:
        raise HTTPException(status_code=503, detail=report["error"])

    # Use OpenAI to answer the question with the real data as context
    if settings.ai_api_key and settings.ai_api_key not in ("replace_me", ""):
        answer = _answer_with_ai(body.question, report)
    else:
        answer = _answer_with_rules(body.question, report)

    return {
        "question": body.question,
        "answer": answer,
        "data_freshness": report.get("generated_at"),
        "students_analysed": report["summary"]["total_students"],
    }


def _answer_with_ai(question: str, report: dict) -> str:
    """Use GPT to answer the question with the report data as context."""
    try:
        client = _get_client()

        # Build a concise data summary to feed into the prompt
        summary = report["summary"]
        leaderboard = report["leaderboard"][:10]
        today = report["today_activity"]
        topics = list(report["top_topics"].items())[:8]

        context = f"""
You are a coding mentor assistant. Answer questions about student LeetCode progress.

CLASS REPORT — {report['date']}
Total students: {summary['total_students']}
Active today: {summary['active_today']}
Total problems solved (all time): {summary['total_problems_solved_alltime']}
Problems solved today: {summary['problems_solved_today']}
Average per student: {summary['average_solved']}
Difficulty: Easy={summary['difficulty']['easy']}, Medium={summary['difficulty']['medium']}, Hard={summary['difficulty']['hard']}

LEADERBOARD (top 10):
{json.dumps(leaderboard, indent=2)}

TODAY'S ACTIVITY:
{json.dumps(today, indent=2)}

TOP TOPICS:
{json.dumps(dict(topics), indent=2)}
"""

        response = client.chat.completions.create(
            model=settings.ai_model,
            temperature=0.3,
            max_tokens=400,
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": question},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        logger.error("AI answer failed | error=%s", exc)
        return _answer_with_rules(question, report)


def _answer_with_rules(question: str, report: dict) -> str:
    """Rule-based answer when AI is not available."""
    q = question.lower()
    summary = report["summary"]
    leaderboard = report["leaderboard"]
    today = report["today_activity"]
    topics = report["top_topics"]

    if any(w in q for w in ["most", "top", "best", "leader", "rank"]):
        if leaderboard:
            top = leaderboard[0]
            return (
                f"{top['real_name']} (@{top['username']}) leads the class with "
                f"{top['total_solved']} problems solved "
                f"({top['easy']} Easy, {top['medium']} Medium, {top['hard']} Hard)."
            )

    if any(w in q for w in ["today", "active", "recent"]):
        if not today:
            return f"No students have solved problems today yet. {summary['total_students']} students tracked."
        names = ", ".join(f"{s['real_name']} ({s['problems_today']} problems)" for s in today[:5])
        return f"{len(today)} student(s) active today: {names}."

    if any(w in q for w in ["topic", "subject", "weak", "strong", "category"]):
        if topics:
            top = list(topics.items())[:3]
            lines = ", ".join(f"{t[0]} ({t[1]} solved)" for t in top)
            return f"Top topics across the class: {lines}."

    if any(w in q for w in ["inactive", "not solved", "haven't", "zero"]):
        inactive = [s for s in leaderboard if s["solved_today"] == 0]
        if inactive:
            names = ", ".join(s["real_name"] for s in inactive[:5])
            return f"{len(inactive)} student(s) have not solved anything today: {names}."
        return "All students have solved at least one problem today!"

    if any(w in q for w in ["total", "count", "how many", "number"]):
        return (
            f"Class summary: {summary['total_students']} students, "
            f"{summary['total_problems_solved_alltime']} total problems solved, "
            f"{summary['active_today']} active today, "
            f"average {summary['average_solved']} problems per student."
        )

    # Default — return summary
    return (
        f"Class has {summary['total_students']} students. "
        f"Total solved: {summary['total_problems_solved_alltime']}. "
        f"Active today: {summary['active_today']}. "
        f"Top student: {leaderboard[0]['real_name']} with {leaderboard[0]['total_solved']} solved."
        if leaderboard else "No data available."
    )
