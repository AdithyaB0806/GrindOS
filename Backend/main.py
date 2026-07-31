from fastapi import FastAPI

from Backend.database import Base, engine
from Backend.routes import router


Base.metadata.create_all(bind=engine)

app=FastAPI()

app.include_router(router)

@app.get("/")
def root():
    return {
        "message":"GrindOS API Running"
    }