from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Backend.assessment_questions import QUESTIONS  # now just the seed data
from Backend.database import get_db
from Backend.models import Assessment, AssessmentQuestion, Recommendation, User
from Backend.schemas import AssessmentSubmission
from Backend.auth import get_current_user

router = APIRouter(prefix="/assessment", tags=["Assessment"])


def ensure_seeded(db: Session) -> None:
    """First run: copy the hardcoded questions into the DB so admins can edit them."""
    if db.query(AssessmentQuestion).count() > 0:
        return
    for index, q in enumerate(QUESTIONS):
        db.add(
            AssessmentQuestion(
                key=q["key"],
                question=q["question"],
                type=q.get("type", "single_choice"),
                options=q["options"],
                allow_other=q.get("allow_other", True),
                order_index=index,
                is_active=True,
            )
        )
    db.commit()


def serialize_question(q: AssessmentQuestion, include_admin_fields: bool = False) -> dict:
    data = {
        "id": q.id,
        "key": q.key,
        "question": q.question,
        "type": q.type,
        "options": q.options or [],
        "allow_other": q.allow_other,
    }
    if include_admin_fields:
        data["is_active"] = q.is_active
        data["order_index"] = q.order_index
    return data


@router.get("/questions")
def get_assessment_questions(db: Session = Depends(get_db)):
    ensure_seeded(db)
    rows = (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.is_active.is_(True))
        .order_by(AssessmentQuestion.order_index)
        .all()
    )
    return [serialize_question(q) for q in rows]


@router.post("/submit")
def submit_assessment(
    data: AssessmentSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(Assessment).filter(Assessment.user_id == current_user.id).first()

    if existing:
        existing.answers = data.answers
        db.commit()
        db.refresh(existing)
        saved = existing
    else:
        saved = Assessment(user_id=current_user.id, answers=data.answers)
        db.add(saved)
        db.commit()
        db.refresh(saved)

    # answers changed -> any old recommendation is stale, clear it so the
    # next call to /recommendations/generate produces a fresh one
    db.query(Recommendation).filter(Recommendation.user_id == current_user.id).delete()
    db.commit()

    return {
        "message": "Assessment submitted successfully",
        "answers": saved.answers
    }

@router.get("/recommendations")
def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recommendation = db.query(Recommendation).filter(Recommendation.user_id == current_user.id).first()
    if not recommendation:
        return {"message": "No recommendations available"}
    return recommendation