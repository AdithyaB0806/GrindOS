from fastapi import FastAPI

from Backend.database import Base, engine
from Backend.routes import router
from Backend.assessment import router as assessment_router
from Backend.ai_recomendation import router as recommendation_router
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()
app.include_router(recommendation_router)

app.include_router(assessment_router)
app.include_router(router)

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