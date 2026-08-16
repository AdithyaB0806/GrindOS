from sqlalchemy import Column,Integer,String,JSON, ForeignKey
from Backend.database import Base

class User(Base):

    __tablename__="users"

    id=Column(Integer,primary_key=True,index=True)

    name=Column(String)

    email=Column(String,unique=True,index=True)

    password=Column(String)

class Assessment(Base):
    __tablename__="assessments"

    id=Column(Integer,primary_key=True,index=True)

    user_id=Column(Integer,ForeignKey("users.id"))

    answers=Column(JSON)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    result = Column(JSON)