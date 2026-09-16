import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import MockInterviewSession, MockInterviewQuestion, Recommendation, Roadmap, User
from Backend.schemas import MockInterviewAnswer
from Backend.auth import get_current_user

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter(prefix="/mock-interview", tags=["Mock Interview"])

ALLOWED_CATEGORIES = {"dsa", "system_design", "behavioral", "domain", "hr"}
GEMINI_MODEL = "gemini-3.6-flash"

GENERATE_PROMPT = """
You are an interview coach building a mock-interview question set for a tech student
targeting jobs in India, for this career path:

Career: {career_title}
Matching skills: {matching_skills}
Skill gaps: {skill_gaps}

Return ONLY valid JSON in this schema, no markdown:
{{
  "questions": [
    {{"category": "dsa", "prompt": "the question to ask out loud"}}
  ]
}}

Rules:
- Exactly 8 questions.
- Mix: 2 dsa, 1 system_design, 3 domain (role-specific), 1 behavioral, 1 hr.
- category must be one of: dsa, system_design, behavioral, domain, hr.
- Phrase each question the way an interviewer would actually ask it out loud, realistic for
  an early-career/fresher round - not trivia.
"""

FEEDBACK_PROMPT = """
You are an interviewer giving direct, honest feedback on a candidate's answer in a mock
interview, for jobs in India. Do not be flattering - if the answer is weak, say so and
explain why.

Career target: {career_title}
Question category: {category}
Question asked: {question}

Candidate's answer:
{answer}

Return ONLY valid JSON in this exact schema, no markdown:
{{
  "score": <integer 1-10>,
  "strengths": ["string"],
  "improvements": ["string"],
  "model_answer_tip": "<one short paragraph on what a strong answer would cover>"
}}

Rules:
- strengths and improvements: 2-4 short, concrete bullets each (not generic advice).
- If the answer is empty, off-topic, or extremely thin, score it low (1-3) and say so
  plainly in improvements.
"""


def _serialize(q: MockInterviewQuestion) -> dict:
    return {
        "id": q.id,
        "category": q.category,
        "prompt": q.prompt,
        "user_answer": q.user_answer,
        "feedback": q.feedback,
        "status": q.status,
    }


def _group(session: MockInterviewSession, questions: list[MockInterviewQuestion]) -> dict:
    return {
        "career_title": session.career_title if session else None,
        "total": len(questions),
        "answered": sum(1 for q in questions if q.status == "answered"),
        "questions": [_serialize(q) for q in questions],
    }


@router.get("/")
def get_mock_interview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(MockInterviewSession).filter(MockInterviewSession.user_id == current_user.id).first()
    if not session:
        return {"message": "No mock interview set yet"}
    questions = (
        db.query(MockInterviewQuestion)
        .filter(MockInterviewQuestion.session_id == session.id)
        .order_by(MockInterviewQuestion.id)
        .all()
    )
    return _group(session, questions)


@router.post("/generate")
def generate_mock_interview(
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(MockInterviewSession).filter(MockInterviewSession.user_id == current_user.id).first()
    if session and not regenerate:
        questions = (
            db.query(MockInterviewQuestion)
            .filter(MockInterviewQuestion.session_id == session.id)
            .order_by(MockInterviewQuestion.id)
            .all()
        )
        return _group(session, questions)

    recommendation = db.query(Recommendation).filter(Recommendation.user_id == current_user.id).first()
    if not recommendation:
        raise HTTPException(status_code=404, detail="Complete the assessment first")

    roadmap = db.query(Roadmap).filter(Roadmap.user_id == current_user.id).first()
    career_paths = recommendation.result.get("career_paths", [])
    career_title = roadmap.career_title if roadmap else (
        career_paths[0]["title"] if career_paths else "Software Engineer"
    )
    chosen = next(
        (c for c in career_paths if c.get("title", "").lower() == career_title.lower()),
        career_paths[0] if career_paths else {},
    )

    prompt = GENERATE_PROMPT.format(
        career_title=career_title,
        matching_skills=json.dumps(chosen.get("matching_skills", [])),
        skill_gaps=json.dumps(chosen.get("skill_gaps", [])),
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        data = json.loads(response.text)
        items = data.get("questions", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    if not items:
        raise HTTPException(status_code=500, detail="AI returned no questions")

    if session:
        db.query(MockInterviewQuestion).filter(MockInterviewQuestion.session_id == session.id).delete()
        session.career_title = career_title
        db.commit()
    else:
        session = MockInterviewSession(user_id=current_user.id, career_title=career_title)
        db.add(session)
        db.commit()
        db.refresh(session)

    saved = []
    for item in items:
        category = item.get("category", "domain")
        if category not in ALLOWED_CATEGORIES:
            category = "domain"
        prompt_text = (item.get("prompt") or "").strip()
        if not prompt_text:
            continue
        q = MockInterviewQuestion(
            session_id=session.id,
            category=category,
            prompt=prompt_text,
            status="unanswered",
        )
        db.add(q)
        saved.append(q)

    db.commit()
    for q in saved:
        db.refresh(q)

    return _group(session, saved)


@router.post("/questions/{question_id}/answer")
def answer_mock_question(
    question_id: int,
    payload: MockInterviewAnswer,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(MockInterviewQuestion)
        .join(MockInterviewSession, MockInterviewQuestion.session_id == MockInterviewSession.id)
        .filter(MockInterviewQuestion.id == question_id, MockInterviewSession.user_id == current_user.id)
        .first()
    )
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    answer = payload.answer.strip()
    if not answer:
        raise HTTPException(status_code=400, detail="Answer can't be empty")

    session = db.query(MockInterviewSession).filter(MockInterviewSession.id == q.session_id).first()

    prompt = FEEDBACK_PROMPT.format(
        career_title=session.career_title if session else "Software Engineer",
        category=q.category,
        question=q.prompt,
        answer=answer,
    )
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        feedback = json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI feedback failed: {str(e)}")

    q.user_answer = answer
    q.feedback = feedback
    q.status = "answered"
    db.commit()
    db.refresh(q)
    return _serialize(q)