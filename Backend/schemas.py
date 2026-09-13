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


class RoadmapItemOut(BaseModel):
    id: int
    title: str
    status: str

    class Config:
        from_attributes = True


class RoadmapPhaseOut(BaseModel):
    phase_number: int
    phase_title: str
    items: List[RoadmapItemOut]


class RoadmapOut(BaseModel):
    id: int
    career_title: str
    progress_percent: float
    phases: List[RoadmapPhaseOut]


class RoadmapItemStatusUpdate(BaseModel):
    status: str  # not_started | learning | practicing | completed


class SkillOut(BaseModel):
    id: int
    name: str
    status: str
    progress_percent: int

    class Config:
        from_attributes = True


class SkillCreate(BaseModel):
    name: str


class SkillStatusUpdate(BaseModel):
    status: str  # not_started | learning | practicing | completed


class JobCreate(BaseModel):
    company: str
    role: str
    location: str | None = None
    source: str | None = None
    url: str | None = None
    status: str = "wishlist"
    notes: str | None = None


class JobUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    source: str | None = None
    url: str | None = None
    status: str | None = None
    notes: str | None = None


class InterviewQuestionStatusUpdate(BaseModel):
    status: str  # not_started | practicing | nailed


class ChatAskRequest(BaseModel):
    question: str


class ChatMessageOut(BaseModel):
    role: str
    content: str