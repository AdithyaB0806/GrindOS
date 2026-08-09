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