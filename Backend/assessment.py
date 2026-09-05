from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Backend.assessment_questions import QUESTIONS
from Backend.database import get_db
from Backend.models import Assessment, Recommendation
from Backend.schemas import AssessmentSubmission

router = APIRouter(prefix="/assessment", tags=["Assessment"])

@router.get("/questions")
def get_assessment_questions():
    return QUESTIONS

@router.post("/submit")
def submit_assessment(
    data: AssessmentSubmission,
    user_id: int,
    db: Session = Depends(get_db)
):
    existing = db.query(Assessment).filter(Assessment.user_id == user_id).first()

    if existing:
        existing.answers = data.answers
        db.commit()
        db.refresh(existing)
        saved = existing
    else:
        saved = Assessment(user_id=user_id, answers=data.answers)
        db.add(saved)
        db.commit()
        db.refresh(saved)

    # answers changed -> any old recommendation is stale, clear it so the
    # next call to /recommendations/generate produces a fresh one
    db.query(Recommendation).filter(Recommendation.user_id == user_id).delete()
    db.commit()

    return {
        "message": "Assessment submitted successfully",
        "answers": saved.answers
    }
@router.get("/recommendations")
def get_recommendations(
    user_id: int,
    db: Session = Depends(get_db)
):
    recommendation = db.query(Recommendation).filter(Recommendation.user_id == user_id).first()
    if not recommendation:
        return {"message": "No recommendations available"}
    return recommendation