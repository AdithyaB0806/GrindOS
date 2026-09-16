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
class RoadmapItemChat(Base):
    __tablename__ = "roadmap_item_chats"
    id = Column(Integer, primary_key=True, index=True)
    roadmap_item_id = Column(Integer, ForeignKey("roadmap_items.id"), unique=True)
    # [{"role": "user" | "assistant", "content": "..."}]
    messages = Column(JSON)
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


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    # "built" | "uploaded"
    source = Column(String)
    title = Column(String, nullable=True)

    # set when source == "uploaded"
    file_name = Column(String, nullable=True)
    file_type = Column(String, nullable=True)  # pdf | docx

    # plain-text version of the resume — either extracted from the
    # uploaded file, or rendered from builder_data. This is what gets
    # fed to the AI for tailoring / ATS checks / cover letters.
    raw_text = Column(String, nullable=True)

    # structured form data, only present when source == "built"
    builder_data = Column(JSON, nullable=True)

    # latest JD-tailored version (plain text) and the JD it was tailored for
    tailored_text = Column(String, nullable=True)
    tailored_for_jd = Column(String, nullable=True)

    # latest ATS check result
    # {"ats_score":.., "verdict":.., "formatting_issues":[...], ...}
    ats = Column(JSON, nullable=True)


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    company = Column(String, nullable=True)
    role = Column(String, nullable=True)
    jd_text = Column(String, nullable=True)
    content = Column(String)


class MockInterviewSession(Base):
    __tablename__ = "mock_interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    career_title = Column(String, nullable=True)


class MockInterviewQuestion(Base):
    __tablename__ = "mock_interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("mock_interview_sessions.id"))

    # dsa | system_design | behavioral | domain | hr
    category = Column(String)
    prompt = Column(String)

    user_answer = Column(String, nullable=True)
    # {"score":.., "strengths":[...], "improvements":[...], "model_answer_tip":..}
    feedback = Column(JSON, nullable=True)

    # unanswered | answered
    status = Column(String, default="unanswered")