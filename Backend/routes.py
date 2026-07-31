from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import User
from Backend.schemas import Register, Login
from Backend.security import hash_password, verify_password
from Backend.auth import create_access_token

router=APIRouter()

@router.post("/register")

def register(user:Register,db:Session=Depends(get_db)):

    existing=db.query(User).filter(
        User.email==user.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    new_user=User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password)
    )

    db.add(new_user)

    db.commit()

    return {
        "message":"User Registered Successfully"
    }


@router.post("/login")

def login(user:Login,db:Session=Depends(get_db)):

    db_user=db.query(User).filter(
        User.email==user.email
    ).first()

    if not db_user:

        raise HTTPException(
            status_code=401,
            detail="Invalid Credentials"
        )

    if not verify_password(
        user.password,
        db_user.password
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid Credentials"
        )

    token=create_access_token(
        {
            "sub":db_user.email,
            "id":db_user.id
        }
    )

    return {
        "access_token":token,
        "token_type":"bearer"
    }