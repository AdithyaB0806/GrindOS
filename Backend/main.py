from fastapi import FastAPI

from Backend.database import Base, engine
from Backend.routes import router
from Backend.assessment import router as assessment_router

app = FastAPI()

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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)