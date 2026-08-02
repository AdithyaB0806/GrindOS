from fastapi import APIRouter, Depends
from Backend.auth import get_current_user
from Backend.models import User

router = APIRouter()

@router.get("/users/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email
    }