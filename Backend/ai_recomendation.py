import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import Assessment, Recommendation, User
from Backend.auth import get_current_user

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

RECOMMENDATION_PROMPT = """
You are a career advisor for computer science / tech students in India.

Given this user's interest assessment answers (JSON below), return:
1. Top 3 career paths that fit them
2. For each path: why it fits, matching skills, skill gaps, and 3-5 example job roles to search for
3. One suggested next skill to learn first

User answers:
{answers}

Respond ONLY with valid JSON in this exact schema, no markdown, no extra text:
{{
  "career_paths": [
    {{
      "title": "string",
      "fit_reason": "string",
      "matching_skills": ["string"],
      "skill_gaps": ["string"],
      "example_roles": ["string"]
    }}
  ],
  "next_skill_to_learn": "string"
}}
"""

def generate_recommendation(answers: dict) -> dict:
    prompt = RECOMMENDATION_PROMPT.format(answers=json.dumps(answers))

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    return json.loads(response.text)


@router.post("/generate")
def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == current_user.id)
        .order_by(Assessment.id.desc())
        .first()
    )

    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found for this user")

    existing = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == current_user.id)
        .first()
    )
    if existing:
        return existing.result

    try:
        result = generate_recommendation(assessment.answers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    new_rec = Recommendation(
        user_id=current_user.id,
        result=result
    )
    db.add(new_rec)
    db.commit()
    db.refresh(new_rec)

    return new_rec.result