from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Backend.auth import create_access_token, get_current_user
from Backend.database import get_db
from Backend.models import User
from Backend.ratelimit import (
    clear_login_failures,
    login_rate_limit,
    record_login_failure,
    register_rate_limit,
)
from Backend.schemas import Login, Register
from Backend.security import hash_password, verify_password

router = APIRouter()


def _find_user(db: Session, email: str) -> User | None:
    # func.lower so accounts created before emails were lowercased still match
    return db.query(User).filter(func.lower(User.email) == email).first()


@router.post("/register")
def register(user: Register, request: Request, db: Session = Depends(get_db)):
    register_rate_limit(request)

    if _find_user(db, user.email):
        raise HTTPException(status_code=400, detail="Email already exists")

    new_user = User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password),
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # two sign-ups with the same email at the same moment
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already exists")
    return {"message": "User Registered Successfully"}


@router.post("/login")
def login(user: Login, request: Request, db: Session = Depends(get_db)):
    login_rate_limit(request, user.email)

    db_user = _find_user(db, user.email)
    if not db_user or not verify_password(user.password, db_user.password):
        record_login_failure(request, user.email)
        raise HTTPException(status_code=401, detail="Invalid Credentials")

    clear_login_failures(user.email)
    token = create_access_token({"sub": db_user.email, "id": db_user.id})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role or "user",
    }