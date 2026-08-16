from pydantic import BaseModel, EmailStr
from typing import Dict


class Register(BaseModel):
    name: str
    email: EmailStr
    password: str


class Login(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class AssessmentSubmission(BaseModel):
    answers: Dict[str, str]

from typing import List

class CareerPath(BaseModel):
    title: str
    fit_reason: str
    matching_skills: List[str]
    skill_gaps: List[str]
    example_roles: List[str]

class RecommendationResponse(BaseModel):
    career_paths: List[CareerPath]
    next_skill_to_learn: str