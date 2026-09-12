from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from Backend.database import get_db
from Backend.models import (
    JobApplication,
    InterviewQuestion,
    Recommendation,
    Roadmap,
    RoadmapItem,
    Skill,
    User,
)
from Backend.auth import get_current_user
from Backend.skills import STATUS_PERCENT
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
@router.get("/summary")
def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    skills = db.query(Skill).filter(Skill.user_id == user_id).all()
    skill_percents = [STATUS_PERCENT.get(s.status, 0) for s in skills]
    skills_block = {
        "average_percent": round(sum(skill_percents) / len(skill_percents), 1) if skills else 0.0,
        "total_skills": len(skills),
        "completed_skills": sum(1 for s in skills if s.status == "completed"),
        "next_skill": next(
            (s.name for s in skills if s.status != "completed"),
            None,
        ),
    }
    roadmap = db.query(Roadmap).filter(Roadmap.user_id == user_id).first()
    roadmap_block = None
    if roadmap:
        items = (
            db.query(RoadmapItem)
            .filter(RoadmapItem.roadmap_id == roadmap.id)
            .order_by(RoadmapItem.order_index)
            .all()
        )
        total = len(items)
        completed = sum(1 for i in items if i.status == "completed")
        next_item = next((i for i in items if i.status != "completed"), None)
        roadmap_block = {
            "id": roadmap.id,
            "career_title": roadmap.career_title,
            "progress_percent": round((completed / total) * 100, 1) if total else 0.0,
            "total_items": total,
            "completed_items": completed,
            "next_item": (
                {
                    "id": next_item.id,
                    "title": next_item.title,
                    "status": next_item.status,
                    "phase_title": next_item.phase_title,
                }
                if next_item
                else None
            ),
        }
    jobs = db.query(JobApplication).filter(JobApplication.user_id == user_id).all()
    job_counts = {
        "wishlist": 0,
        "applied": 0,
        "oa": 0,
        "interview": 0,
        "offer": 0,
        "rejected": 0,
    }
    for job in jobs:
        if job.status in job_counts:
            job_counts[job.status] += 1
    jobs_block = {
        "total": len(jobs),
        "pipeline": job_counts["applied"] + job_counts["oa"] + job_counts["interview"],
        "counts": job_counts,
        "recent": [
            {
                "id": j.id,
                "company": j.company,
                "role": j.role,
                "status": j.status,
            }
            for j in sorted(jobs, key=lambda x: x.id, reverse=True)[:4]
        ],
    }
    questions = db.query(InterviewQuestion).filter(InterviewQuestion.user_id == user_id).all()
    interview_total = len(questions)
    interview_block = {
        "total": interview_total,
        "nailed": sum(1 for q in questions if q.status == "nailed"),
        "practicing": sum(1 for q in questions if q.status == "practicing"),
        "progress_percent": round(
            (sum(1 for q in questions if q.status == "nailed") / interview_total) * 100, 1
        )
        if interview_total
        else 0.0,
        "career_title": questions[0].career_title if questions else None,
    }
    recommendation = db.query(Recommendation).filter(Recommendation.user_id == user_id).first()
    rec_result = recommendation.result if recommendation else None
    return {
        "skills": skills_block,
        "roadmap": roadmap_block,
        "jobs": jobs_block,
        "interview": interview_block,
        "recommendation": rec_result,
        "next_skill_to_learn": (rec_result or {}).get("next_skill_to_learn"),
    }