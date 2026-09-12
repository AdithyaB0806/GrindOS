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


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    career_title = Column(String)


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id = Column(Integer, primary_key=True, index=True)

    roadmap_id = Column(Integer, ForeignKey("roadmaps.id"))

    phase_number = Column(Integer)

    phase_title = Column(String)

    title = Column(String)

    order_index = Column(Integer)

    # not_started | learning | practicing | completed
    status = Column(String, default="not_started")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    # set when this skill was seeded from a roadmap item
    roadmap_item_id = Column(
        Integer,
        ForeignKey("roadmap_items.id"),
        nullable=True
    )

    name = Column(String)

    # not_started | learning | practicing | completed
    status = Column(String, default="not_started")
class RoadmapItemGuide(Base):
    __tablename__ = "roadmap_item_guides"
    id = Column(Integer, primary_key=True, index=True)
    roadmap_item_id = Column(Integer, ForeignKey("roadmap_items.id"), unique=True)
    content = Column(JSON)
class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    company = Column(String)
    role = Column(String)
    location = Column(String, nullable=True)
    source = Column(String, nullable=True)
    url = Column(String, nullable=True)
    # wishlist | applied | oa | interview | offer | rejected
    status = Column(String, default="wishlist")
    notes = Column(String, nullable=True)
class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    career_title = Column(String)
    # dsa | system_design | behavioral | domain | hr
    category = Column(String)
    prompt = Column(String)
    hint = Column(String, nullable=True)
    talking_points = Column(JSON)
    # not_started | practicing | nailed
    # not_started | practicing | nailed
    status = Column(String, default="not_started")