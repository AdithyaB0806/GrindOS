from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import (
    Assessment,
    AssessmentQuestion,
    JobApplication,
    MockInterviewSession,
    Recommendation,
    Resume,
    User,
)
from Backend.auth import require_admin
from Backend.assessment import ensure_seeded, serialize_question
from Backend.schemas import QuestionCreate, QuestionUpdate, QuestionReorder, RoleUpdate

# every route in this router requires an admin
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

ALLOWED_ROLES = {"user", "admin"}


# ---------- overview ----------

@router.get("/stats")
def admin_stats(db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "admins": db.query(User).filter(User.role == "admin").count(),
        "assessments_taken": db.query(Assessment).count(),
        "recommendations": db.query(Recommendation).count(),
        "resumes": db.query(Resume).count(),
        "job_applications": db.query(JobApplication).count(),
        "mock_interview_sessions": db.query(MockInterviewSession).count(),
        "questions_active": db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.is_active.is_(True))
        .count(),
    }


# ---------- users ----------

@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    assessed = {a.user_id for a in db.query(Assessment.user_id).all()}
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role or "user",
            "has_assessment": u.id in assessed,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/role")
def set_user_role(
    user_id: int,
    data: RoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ALLOWED_ROLES)}")
    if user_id == admin.id:
        # stops you from accidentally locking yourself (and maybe everyone) out
        raise HTTPException(status_code=400, detail="You can't change your own role")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = data.role
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


# ---------- assessment questions ----------

@router.get("/questions")
def list_all_questions(db: Session = Depends(get_db)):
    """Includes inactive questions, unlike the public /assessment/questions."""
    ensure_seeded(db)
    rows = db.query(AssessmentQuestion).order_by(AssessmentQuestion.order_index).all()
    return [serialize_question(q, include_admin_fields=True) for q in rows]


@router.post("/questions")
def create_question(data: QuestionCreate, db: Session = Depends(get_db)):
    key = data.key.strip()
    if not key or not data.question.strip():
        raise HTTPException(status_code=400, detail="key and question are required")
    options = [o.strip() for o in data.options if o.strip()]
    if len(options) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 options")
    if db.query(AssessmentQuestion).filter(AssessmentQuestion.key == key).first():
        raise HTTPException(status_code=400, detail="A question with this key already exists")

    last = db.query(AssessmentQuestion).order_by(AssessmentQuestion.order_index.desc()).first()
    q = AssessmentQuestion(
        key=key,
        question=data.question.strip(),
        type=data.type,
        options=options,
        allow_other=data.allow_other,
        is_active=data.is_active,
        order_index=(last.order_index + 1) if last else 0,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return serialize_question(q, include_admin_fields=True)


@router.patch("/questions/{question_id}")
def update_question(question_id: int, data: QuestionUpdate, db: Session = Depends(get_db)):
    q = db.query(AssessmentQuestion).filter(AssessmentQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # `key` is deliberately not editable: saved student answers and the AI
    # recommendation prompt are keyed by it.
    if data.question is not None:
        if not data.question.strip():
            raise HTTPException(status_code=400, detail="question can't be empty")
        q.question = data.question.strip()
    if data.options is not None:
        options = [o.strip() for o in data.options if o.strip()]
        if len(options) < 2:
            raise HTTPException(status_code=400, detail="Provide at least 2 options")
        q.options = options
    if data.allow_other is not None:
        q.allow_other = data.allow_other
    if data.is_active is not None:
        q.is_active = data.is_active

    db.commit()
    db.refresh(q)
    return serialize_question(q, include_admin_fields=True)


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db)):
    q = db.query(AssessmentQuestion).filter(AssessmentQuestion.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
    return {"message": "Question deleted"}


@router.put("/questions/reorder")
def reorder_questions(data: QuestionReorder, db: Session = Depends(get_db)):
    rows = {
        q.id: q
        for q in db.query(AssessmentQuestion).filter(AssessmentQuestion.id.in_(data.ids)).all()
    }
    for index, qid in enumerate(data.ids):
        if qid in rows:
            rows[qid].order_index = index
    db.commit()
    return {"message": "Order updated"}