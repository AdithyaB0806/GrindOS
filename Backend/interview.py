import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.ai import AIError, ai_unavailable, generate_json
from Backend.auth import get_current_user
from Backend.database import get_db
from Backend.models import InterviewQuestion, Recommendation, Roadmap, User
from Backend.ratelimit import spend_ai_budget
from Backend.schemas import InterviewQuestionStatusUpdate

log = logging.getLogger("grindos.interview")

router = APIRouter(prefix="/interview", tags=["Interview"])

ALLOWED_STATUSES = {"not_started", "practicing", "nailed"}
ALLOWED_CATEGORIES = {"dsa", "system_design", "behavioral", "domain", "hr"}

INTERVIEW_PROMPT = """
You are an interview coach for computer science / tech students targeting jobs in India
(product companies, startups, and service-to-product jumps). Build a focused interview
prep set for this career path:

Career: {career_title}
Matching skills: {matching_skills}
Skill gaps: {skill_gaps}

Return ONLY valid JSON in this schema, no markdown:
{{
  "questions": [
    {{
      "category": "dsa",
      "prompt": "the question the candidate should practice",
      "hint": "a short hint, not the full answer",
      "talking_points": ["bullet they should cover", "bullet"]
    }}
  ]
}}

Rules:
- Exactly 16 questions.
- Mix: 5 dsa, 3 system_design, 4 domain (role-specific), 2 behavioral, 2 hr.
- category must be one of: dsa, system_design, behavioral, domain, hr
- DSA questions should name the pattern (arrays, graphs, DP, etc.) and be realistic for
  45-minute rounds, not trivia.
- Domain questions must actually match {career_title}.
- Keep prompts concise. talking_points: 3-5 short bullets.
"""


def _text(value, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _clean_questions(data) -> dict:
    """Keep usable questions only, with safe categories and lengths."""
    raw = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError("no questions in AI reply")

    questions = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        prompt = _text(item.get("prompt"), 600)
        if not prompt:
            continue
        category = item.get("category")
        if category not in ALLOWED_CATEGORIES:
            category = "domain"
        points = item.get("talking_points")
        points = (
            [_text(p, 200) for p in points if isinstance(p, (str, int, float)) and str(p).strip()][:6]
            if isinstance(points, list)
            else []
        )
        questions.append(
            {
                "category": category,
                "prompt": prompt,
                "hint": _text(item.get("hint"), 300) or None,
                "talking_points": points,
            }
        )
    if not questions:
        raise ValueError("AI reply had no usable questions")
    return {"questions": questions[:20]}


def _serialize(q: InterviewQuestion) -> dict:
    return {
        "id": q.id,
        "career_title": q.career_title,
        "category": q.category,
        "prompt": q.prompt,
        "hint": q.hint,
        "talking_points": q.talking_points or [],
        "status": q.status,
    }


def _group(questions: list[InterviewQuestion]) -> dict:
    grouped = {}
    for q in questions:
        grouped.setdefault(q.category, []).append(_serialize(q))
    career = questions[0].career_title if questions else None
    total = len(questions)
    nailed = sum(1 for q in questions if q.status == "nailed")
    practicing = sum(1 for q in questions if q.status == "practicing")
    return {
        "career_title": career,
        "total": total,
        "nailed": nailed,
        "practicing": practicing,
        "progress_percent": round((nailed / total) * 100, 1) if total else 0.0,
        "categories": grouped,
        "questions": [_serialize(q) for q in questions],
    }


@router.get("/")
def get_interview_prep(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.user_id == current_user.id)
        .order_by(InterviewQuestion.id)
        .all()
    )
    if not questions:
        return {"message": "No interview prep available"}
    return _group(questions)


@router.get("/dashboard")
def interview_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.user_id == current_user.id)
        .all()
    )
    total = len(questions)
    nailed = sum(1 for q in questions if q.status == "nailed")
    return {
        "total": total,
        "nailed": nailed,
        "practicing": sum(1 for q in questions if q.status == "practicing"),
        "progress_percent": round((nailed / total) * 100, 1) if total else 0.0,
        "career_title": questions[0].career_title if questions else None,
    }


@router.post("/generate")
def generate_interview_prep(
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.user_id == current_user.id)
        .order_by(InterviewQuestion.id)
        .all()
    )
    if existing and not regenerate:
        return _group(existing)

    recommendation = (
        db.query(Recommendation).filter(Recommendation.user_id == current_user.id).first()
    )
    if not recommendation:
        raise HTTPException(
            status_code=404,
            detail="No recommendation found. Complete the assessment first.",
        )

    roadmap = db.query(Roadmap).filter(Roadmap.user_id == current_user.id).first()
    career_paths = recommendation.result.get("career_paths", [])
    career_title = roadmap.career_title if roadmap else (
        career_paths[0]["title"] if career_paths else "Software Engineer"
    )
    chosen = next(
        (c for c in career_paths if c.get("title", "").lower() == career_title.lower()),
        career_paths[0] if career_paths else {},
    )

    prompt = INTERVIEW_PROMPT.format(
        career_title=career_title,
        matching_skills=json.dumps(chosen.get("matching_skills", [])),
        skill_gaps=json.dumps(chosen.get("skill_gaps", [])),
    )

    spend_ai_budget(current_user)
    try:
        items = generate_json(prompt, validate=_clean_questions, provider="openai")["questions"]
    except AIError:
        raise ai_unavailable("Building your interview prep")

    db.query(InterviewQuestion).filter(InterviewQuestion.user_id == current_user.id).delete()

    saved = []
    for item in items:
        q = InterviewQuestion(
            user_id=current_user.id,
            career_title=career_title,
            category=item["category"],
            prompt=item["prompt"],
            hint=item["hint"],
            talking_points=item["talking_points"],
            status="not_started",
        )
        db.add(q)
        saved.append(q)

    db.commit()
    for q in saved:
        db.refresh(q)

    return _group(saved)


@router.patch("/questions/{question_id}/status")
def update_question_status(
    question_id: int,
    payload: InterviewQuestionStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )
    q = (
        db.query(InterviewQuestion)
        .filter(
            InterviewQuestion.id == question_id,
            InterviewQuestion.user_id == current_user.id,
        )
        .first()
    )
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    q.status = payload.status
    db.commit()
    db.refresh(q)
    return _serialize(q)