from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import RoadmapItem, Skill, User
from Backend.schemas import SkillCreate, SkillStatusUpdate
from Backend.auth import get_current_user

router = APIRouter(prefix="/skills", tags=["Skills"])

# not_started | learning | practicing | completed -> dashboard progress bar %
STATUS_PERCENT = {"not_started": 0, "learning": 33, "practicing": 66, "completed": 100}
ALLOWED_STATUSES = set(STATUS_PERCENT)


def _serialize(skill: Skill, phase_title: str | None = None) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "status": skill.status,
        "progress_percent": STATUS_PERCENT.get(skill.status, 0),
        # "roadmap" skills were seeded from a roadmap item and grouped by
        # phase in the UI; "manual" ones were added by the student directly
        # and can be deleted.
        "source": "roadmap" if skill.roadmap_item_id else "manual",
        "phase_title": phase_title,
    }


def _serialize_all(skills: list[Skill], db: Session) -> list[dict]:
    item_ids = [s.roadmap_item_id for s in skills if s.roadmap_item_id]
    phase_by_item_id = {}
    if item_ids:
        items = db.query(RoadmapItem).filter(RoadmapItem.id.in_(item_ids)).all()
        phase_by_item_id = {i.id: i.phase_title for i in items}
    return [
        _serialize(s, phase_by_item_id.get(s.roadmap_item_id))
        for s in skills
    ]


@router.get("/")
def list_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    skills = db.query(Skill).filter(Skill.user_id == current_user.id).all()
    return _serialize_all(skills, db)


@router.get("/dashboard")
def skills_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Single aggregate block for the GrindOS dashboard's SKILLS progress bar."""
    skills = db.query(Skill).filter(Skill.user_id == current_user.id).all()
    if not skills:
        return {
            "average_percent": 0.0,
            "total_skills": 0,
            "completed_skills": 0,
            "by_status": {s: 0 for s in ALLOWED_STATUSES},
        }

    percents = [STATUS_PERCENT.get(s.status, 0) for s in skills]
    by_status = {status: 0 for status in ALLOWED_STATUSES}
    for s in skills:
        if s.status in by_status:
            by_status[s.status] += 1

    return {
        "average_percent": round(sum(percents) / len(percents), 1),
        "total_skills": len(skills),
        "completed_skills": by_status["completed"],
        "by_status": by_status,
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
    return _serialize_all([skill], db)[0]


@router.delete("/{skill_id}")
def delete_skill(
    skill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    skill = (
        db.query(Skill)
        .filter(Skill.id == skill_id, Skill.user_id == current_user.id)
        .first()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill.roadmap_item_id:
        raise HTTPException(
            status_code=400,
            detail="Can't delete a skill that's linked to a roadmap item - change its status instead",
        )
    db.delete(skill)
    db.commit()
    return {"message": "Skill deleted"}