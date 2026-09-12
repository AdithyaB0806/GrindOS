from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from Backend.database import get_db
from Backend.models import JobApplication, User
from Backend.schemas import JobCreate, JobUpdate
from Backend.auth import get_current_user
router = APIRouter(prefix="/jobs", tags=["Jobs"])
ALLOWED_STATUSES = {"wishlist", "applied", "oa", "interview", "offer", "rejected"}
def _serialize(job: JobApplication) -> dict:
    return {
        "id": job.id,
        "company": job.company,
        "role": job.role,
        "location": job.location,
        "source": job.source,
        "url": job.url,
        "status": job.status,
        "notes": job.notes,
    }
@router.get("/")
def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(JobApplication)
        .filter(JobApplication.user_id == current_user.id)
        .order_by(JobApplication.id.desc())
        .all()
    )
    return [_serialize(j) for j in jobs]
@router.get("/dashboard")
def jobs_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.query(JobApplication).filter(JobApplication.user_id == current_user.id).all()
    counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    for job in jobs:
        if job.status in counts:
            counts[job.status] += 1
    pipeline = counts["applied"] + counts["oa"] + counts["interview"]
    return {
        "total": len(jobs),
        "pipeline": pipeline,
        "counts": counts,
    }
@router.post("/")
def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = data.status if data.status in ALLOWED_STATUSES else "wishlist"
    job = JobApplication(
        user_id=current_user.id,
        company=data.company.strip(),
        role=data.role.strip(),
        location=(data.location or "").strip() or None,
        source=(data.source or "").strip() or None,
        url=(data.url or "").strip() or None,
        status=status,
        notes=(data.notes or "").strip() or None,
    )
    if not job.company or not job.role:
        raise HTTPException(status_code=400, detail="company and role are required")
    db.add(job)
    db.commit()
    db.refresh(job)
    return _serialize(job)
@router.patch("/{job_id}")
def update_job(
    job_id: int,
    data: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
    if "status" in payload and payload["status"] not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )
    for key, value in payload.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return _serialize(job)
@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}