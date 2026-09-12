from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import Skill, User
from Backend.schemas import SkillCreate, SkillStatusUpdate
from Backend.auth import get_current_user

router = APIRouter(prefix="/skills", tags=["Skills"])

# not_started | learning | practicing | completed -> dashboard progress bar %
STATUS_PERCENT = {"not_started": 0, "learning": 33, "practicing": 66, "completed": 100}
ALLOWED_STATUSES = set(STATUS_PERCENT)


def _serialize(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "status": skill.status,
        "progress_percent": STATUS_PERCENT.get(skill.status, 0),
    }


@router.get("/")
def list_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    skills = db.query(Skill).filter(Skill.user_id == current_user.id).all()
    return [_serialize(s) for s in skills]


@router.get("/dashboard")
def skills_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single aggregate block for the GrindOS dashboard's SKILLS progress bar."""
    skills = db.query(Skill).filter(Skill.user_id == current_user.id).all()
    if not skills:
        return {"average_percent": 0.0, "total_skills": 0, "completed_skills": 0}

    percents = [STATUS_PERCENT.get(s.status, 0) for s in skills]
    return {
        "average_percent": round(sum(percents) / len(percents), 1),
        "total_skills": len(skills),
        "completed_skills": sum(1 for s in skills if s.status == "completed"),
    }


@router.post("/")
def add_skill(
    data: SkillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually add a skill outside the roadmap (e.g. something learned on
    their own). Roadmap-linked skills are seeded automatically by
    /roadmap/generate - this is just for the extras.
    """
    existing = (
        db.query(Skill)
        .filter(Skill.user_id == current_user.id, Skill.name == data.name)
        .first()
    )
    if existing:
        return _serialize(existing)

    skill = Skill(user_id=current_user.id, name=data.name, status="not_started")
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return _serialize(skill)


@router.patch("/{skill_id}/status")
def update_skill_status(
    skill_id: int,
    data: SkillStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )

    skill = (
        db.query(Skill)
        .filter(Skill.id == skill_id, Skill.user_id == current_user.id)
        .first()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.status = data.status
    db.commit()
    db.refresh(skill)
    return _serialize(skill)