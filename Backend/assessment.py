from fastapi import APIRouter
from Backend.assessment_questions import QUESTIONS

router = APIRouter(prefix="/assessment", tags=["Assessment"])

@router.get("/questions")
def get_assessment_questions():
    return QUESTIONS

@router.post("/submit")
def submit_assessment(answers: dict):
    # Here you can process the answers, save them to a database, or perform any other logic
    # For now, we'll just return the submitted answers
    return {"message": "Assessment submitted successfully", "answers": answers} 