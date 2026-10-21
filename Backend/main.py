import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Backend.admin import router as admin_router
from Backend.ai_recomendation import router as recommendation_router
from Backend.assessment import router as assessment_router
from Backend.dashboard import router as dashboard_router
from Backend.database import Base, engine
from Backend.interview import router as interview_router
from Backend.jd_match import router as jd_match_router  # also registers the JDMatch table
from Backend.jobs import router as jobs_router
from Backend.mock_interview import router as mock_interview_router
from Backend.resume import router as resume_router
from Backend.roadmap import router as roadmap_router
from Backend.routes import router
from Backend.skills import router as skills_router

app = FastAPI(title="GrindOS API")

# Where the frontend is served from. Set CORS_ORIGINS on the host, e.g.
#   CORS_ORIGINS=https://grindos.vercel.app,https://www.grindos.app
# localhost is always allowed so local development keeps working.
_origins = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendation_router)
app.include_router(assessment_router)
app.include_router(router)
app.include_router(roadmap_router)
app.include_router(skills_router)
app.include_router(jobs_router)
app.include_router(interview_router)
app.include_router(dashboard_router)
app.include_router(resume_router)
app.include_router(jd_match_router)
app.include_router(mock_interview_router)
app.include_router(admin_router)

# Creates missing tables only; it never alters existing ones. Once the schema
# starts changing in production, move to Alembic migrations.
# Every module that defines a model (including jd_match.py) must be imported
# above this line, or its table won't be created.
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "GrindOS API Running"}


@app.get("/health")
def health():
    return {"status": "ok"}