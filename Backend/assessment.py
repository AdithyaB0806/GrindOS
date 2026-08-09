from unittest import result

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Backend.assessment_questions import QUESTIONS
from Backend.database import get_db
from Backend.models import Assessment
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
    result = Assessment(
        user_id=user_id,
        answers=data.answers
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "message": "Assessment submitted successfully",
        "answers": result.answers
    }

    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "message": "Assessment submitted successfully",
        "answers": result.answers
    }