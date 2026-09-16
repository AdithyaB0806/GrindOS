from fastapi import FastAPI
from Backend.database import Base, engine
from Backend.routes import router
from Backend.assessment import router as assessment_router
from Backend.ai_recomendation import router as recommendation_router
from Backend.roadmap import router as roadmap_router
from Backend.skills import router as skills_router
from Backend.jobs import router as jobs_router
from Backend.interview import router as interview_router
from Backend.dashboard import router as dashboard_router
from Backend.resume import router as resume_router
from Backend.mock_interview import router as mock_interview_router
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()
app.include_router(recommendation_router)
app.include_router(assessment_router)
app.include_router(router)
app.include_router(roadmap_router)
app.include_router(skills_router)
app.include_router(jobs_router)
app.include_router(interview_router)
app.include_router(dashboard_router)
app.include_router(resume_router)
app.include_router(mock_interview_router)

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {
        "message":"GrindOS API Running"
    }
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)