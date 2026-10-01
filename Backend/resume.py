#resume.py
import os
import io
import json

import re

from dotenv import load_dotenv
from openai import OpenAI

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import Resume, CoverLetter, Recommendation, User
from Backend.schemas import (
    ResumeBuilderData,
    ResumeTailorRequest,
    AtsCheckRequest,
    SectionOrderUpdate,
    CoverLetterRequest,
)
from Backend.auth import get_current_user
from Backend.resumerender import (
    render_text as render_resume_text,
    render_docx as render_resume_docx,
    render_html as render_resume_html,
    resolve_order,
)


# ============================================================
# Environment / AI Client
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set in the environment.")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


router = APIRouter(prefix="/resume", tags=["Resume"])


# ============================================================
# Constants
# ============================================================

ALLOWED_UPLOAD_TYPES = {"pdf", "docx"}

GROQ_MODEL = "openai/gpt-oss-20b"


# ============================================================
# Prompts
# ============================================================

ATS_PROMPT = """
You are an ATS (Applicant Tracking System) simulator and a strict resume reviewer for the
Indian tech job market. Evaluate the resume text below exactly as an ATS parser AND a
no-nonsense human recruiter would.

Resume:
{resume_text}

Job description to match against (this will say "None provided." if the student didn't
give one - in that case skip keyword matching and just review general ATS-friendliness):
{jd_text}

Return ONLY valid JSON in this exact schema, no markdown, no extra text:
{{
  "ats_score": <integer 0-100>,
  "verdict": "<one short sentence overall verdict>",
  "formatting_issues": ["string"],
  "content_issues": ["string"],
  "missing_keywords": ["string"],
  "strengths": ["string"],
  "quick_fixes": ["string"]
}}

Rules:
- formatting_issues should only flag things that actually appear to break ATS parsing
  (evidence of tables/columns, missing contact info, non-standard section headers, no
  clear section structure, walls of text with no bullets). Don't invent issues that
  aren't supported by the text.
- missing_keywords must be an empty list if no job description was provided.
- content_issues covers weak bullets, missing metrics/impact, vague language, no clear
  outcomes.
- Keep every string under 20 words. Max 6 items per list.
"""


TAILOR_PROMPT = """
You are a resume writer helping a student tailor their resume to a specific job description,
for the Indian tech job market. Keep the output strictly ATS-friendly: plain text only,
standard section headers in ALL CAPS on their own line (SUMMARY, EXPERIENCE, PROJECTS,
EDUCATION, SKILLS, CERTIFICATIONS - only include sections that have content), bullet points
starting with "-", no tables, no special characters, no multi-column layout.

Rewrite the resume below so it's tailored to the job description: mirror its important
keywords and skills naturally wherever the candidate's real experience actually supports it,
reorder or re-emphasize bullets toward what this JD cares about most, and tighten weak
bullets into impact-driven ones (action verb + what they did + measurable outcome where
possible). Never invent experience, companies, titles, metrics, or skills the candidate
doesn't already have in the original.

Original resume:
{resume_text}

Job description:
{jd_text}

Return ONLY the tailored resume as plain text, ready to be pasted into a document - no
commentary, no markdown formatting, no explanations before or after.
"""


COVER_LETTER_PROMPT = """
You are helping a student write a concise, honest, non-generic cover letter for a job in the
Indian tech job market. Base every claim strictly on their actual resume below - never invent
experience, projects, companies, or skills that aren't in it.

Resume:
{resume_text}

Job description:
{jd_text}

Target company: {company}
Target role: {role}

Write a cover letter (3-4 short paragraphs, under 350 words) that:
- Opens with genuine, specific interest in this role/company (not generic flattery)
- Connects 2-3 concrete things from their resume to what the JD actually asks for
- Sounds like a real early-career candidate, not corporate boilerplate
- Ends with a simple, confident closing line

Return ONLY the cover letter text - no markdown, no subject line, no placeholder brackets
like "[Your Name]". Use the candidate's actual name from the resume if present in the
greeting/sign-off, otherwise omit the name rather than using a placeholder.
"""


# ============================================================
# File parsing helpers
# ============================================================

def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber

    parts = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()

            if text:
                parts.append(text)

    return "\n".join(parts).strip()


def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(file_bytes))

    return "\n".join(
        p.text for p in document.paragraphs if p.text.strip()
    )


# ============================================================
# Rendering helpers
# ============================================================

# NOTE: render_resume_text / render_resume_docx / render_resume_html now live in
# Backend/resume_render.py (imported above) so the preview, the download and the
# text sent to the AI all come from the same code.


def text_to_docx(text: str) -> bytes:
    """
    Generic plain-text -> docx renderer, used for the AI-tailored resume text.
    """

    from docx import Document
    from docx.shared import Pt

    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    for raw_line in text.split("\n"):

        line = raw_line.strip()

        if not line:
            doc.add_paragraph("")

        elif line.isupper() and len(line) < 40:
            doc.add_heading(
                line.title(),
                level=2
            )

        elif line.startswith(
            ("-", "•", "*")
        ):
            doc.add_paragraph(
                line.lstrip("-•* ").strip(),
                style="List Bullet"
            )

        else:
            doc.add_paragraph(line)

    buf = io.BytesIO()

    doc.save(buf)

    return buf.getvalue()


# ============================================================
# Shared helpers
# ============================================================

def _get_resume(
    db: Session,
    user_id: int
) -> Resume | None:

    return (
        db.query(Resume)
        .filter(
            Resume.user_id == user_id
        )
        .first()
    )


def _serialize(r: Resume) -> dict:

    return {
        "id": r.id,
        "source": r.source,
        "title": r.title,
        "file_name": r.file_name,
        "file_type": r.file_type,
        "raw_text": r.raw_text,
        "builder_data": r.builder_data,
        "tailored_text": r.tailored_text,
        "tailored_for_jd": r.tailored_for_jd,
        "ats": r.ats,
    }


# ============================================================
# Groq AI helpers
# ============================================================

def _call_groq_text(prompt: str) -> str:

    response = client.responses.create(
        model=GROQ_MODEL,
        input=prompt,
    )

    return response.output_text.strip()


def _call_groq_json(prompt: str) -> dict:

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        response_format={
            "type": "json_object"
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty response."
        )

    return json.loads(content)


# ============================================================
# Build
# ============================================================

@router.post("/build")
def build_resume(
    data: ResumeBuilderData,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    builder_data = data.model_dump()
    builder_data["section_order"] = resolve_order(builder_data)

    text = render_resume_text(
        builder_data
    )

    resume = _get_resume(
        db,
        current_user.id
    )

    if resume:

        resume.source = "built"

        resume.title = (
            builder_data.get("full_name")
            or resume.title
            or "My Resume"
        )

        resume.file_name = None
        resume.file_type = None

        resume.raw_text = text

        resume.builder_data = builder_data

        resume.tailored_text = None
        resume.tailored_for_jd = None
        resume.ats = None

    else:

        resume = Resume(
            user_id=current_user.id,
            source="built",
            title=(
                builder_data.get("full_name")
                or "My Resume"
            ),
            raw_text=text,
            builder_data=builder_data,
        )

        db.add(resume)

    db.commit()
    db.refresh(resume)

    return _serialize(resume)


# ============================================================
# Download built resume
# ============================================================


def _safe_filename(title, suffix=""):
    stem = re.sub(r"\.(pdf|docx)$", "", title or "resume", flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "resume"
    return f"{stem}{suffix}.docx"

DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument."
    "wordprocessingml.document"
)


def _docx_response(docx_bytes: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/build/download")
def download_built_resume(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = _get_resume(db, current_user.id)
    if not resume:
        raise HTTPException(404, "Build or upload a resume first")
    if resume.builder_data:
        docx_bytes = render_resume_docx(resume.builder_data)
    elif resume.raw_text:
        docx_bytes = text_to_docx(resume.raw_text)
    else:
        raise HTTPException(404, "Build or upload a resume first")
    return _docx_response(docx_bytes, _safe_filename(resume.title))


# ============================================================
# Preview + section ordering
# ============================================================

@router.post("/build/preview")
def preview_resume(
    data: ResumeBuilderData,
    current_user: User = Depends(get_current_user),
):
    """
    Render the form as it currently stands, without saving. Call this on
    every (debounced) edit to drive a live preview.
    """
    d = data.model_dump()
    return {
        "html": render_resume_html(d),
        "section_order": resolve_order(d),
    }


@router.get("/build/preview")
def preview_saved_resume(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_resume(db, current_user.id)
    if not resume or not resume.builder_data:
        raise HTTPException(404, "Build a resume first")
    return {
        "html": render_resume_html(resume.builder_data),
        "section_order": resolve_order(resume.builder_data),
    }


@router.put("/build/order")
def update_section_order(
    payload: SectionOrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Move sections around (e.g. Projects above Experience) without resending
    the whole form. Unlike /build this keeps the tailored text and ATS result,
    since only the layout changed.
    """
    resume = _get_resume(db, current_user.id)
    if not resume or not resume.builder_data:
        raise HTTPException(404, "Build a resume first")

    # assign a NEW dict - SQLAlchemy doesn't see in-place edits to JSON columns
    new_data = dict(resume.builder_data)
    new_data["section_order"] = resolve_order({"section_order": payload.section_order})
    resume.builder_data = new_data
    resume.raw_text = render_resume_text(new_data)
    db.commit()
    db.refresh(resume)
    return {
        "section_order": new_data["section_order"],
        "html": render_resume_html(new_data),
    }


# ============================================================
# Upload
# ============================================================

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    ext = (
        (file.filename or "")
        .rsplit(".", 1)[-1]
        .lower()
    )

    if ext not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported"
        )

    content = await file.read()

    try:

        if ext == "pdf":
            text = extract_text_from_pdf(
                content
            )

        else:
            text = extract_text_from_docx(
                content
            )

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Couldn't read that file: {str(e)}"
        )

    if not text.strip():

        raise HTTPException(
            status_code=400,
            detail=(
                "Couldn't extract any text from that file - "
                "is it a scanned/image resume?"
            ),
        )

    resume = _get_resume(
        db,
        current_user.id
    )

    if resume:

        resume.source = "uploaded"

        resume.title = file.filename

        resume.file_name = file.filename
        resume.file_type = ext

        resume.raw_text = text

        resume.builder_data = None

        resume.tailored_text = None
        resume.tailored_for_jd = None
        resume.ats = None

    else:

        resume = Resume(
            user_id=current_user.id,
            source="uploaded",
            title=file.filename,
            file_name=file.filename,
            file_type=ext,
            raw_text=text,
        )

        db.add(resume)

    db.commit()
    db.refresh(resume)

    return _serialize(resume)


# ============================================================
# Current resume
# ============================================================

@router.get("/")
def get_resume(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    resume = _get_resume(
        db,
        current_user.id
    )

    if not resume:
        return {
            "message": "No resume yet"
        }

    return _serialize(resume)


# ============================================================
# Tailor resume
# ============================================================

@router.post("/tailor")
def tailor_resume(
    payload: ResumeTailorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    resume = _get_resume(
        db,
        current_user.id
    )

    if not resume or not resume.raw_text:

        raise HTTPException(
            status_code=404,
            detail="Build or upload a resume first"
        )

    prompt = TAILOR_PROMPT.format(
        resume_text=resume.raw_text,
        jd_text=payload.jd_text.strip(),
    )

    try:

        tailored = _call_groq_text(
            prompt
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"AI tailoring failed: {str(e)}"
        )

    resume.tailored_text = tailored

    resume.tailored_for_jd = (
        payload.jd_text
    )

    db.commit()
    db.refresh(resume)

    return _serialize(resume)


# ============================================================
# Download tailored resume
# ============================================================

@router.get("/tailor/download")
def download_tailored_resume(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    resume = _get_resume(
        db,
        current_user.id
    )

    if not resume or not resume.tailored_text:

        raise HTTPException(
            status_code=404,
            detail=(
                "Tailor a resume to a job "
                "description first"
            ),
        )

    docx_bytes = text_to_docx(resume.tailored_text)
    return _docx_response(docx_bytes, _safe_filename(resume.title, "_tailored"))


# ============================================================
# ATS check
# ============================================================

@router.post("/ats-check")
def ats_check(
    payload: AtsCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    resume = _get_resume(
        db,
        current_user.id
    )

    if not resume or not resume.raw_text:

        raise HTTPException(
            status_code=404,
            detail="Build or upload a resume first"
        )

    if (
        payload.jd_text
        and payload.jd_text.strip()
    ):
        jd_text = payload.jd_text.strip()

    else:
        jd_text = "None provided."

    prompt = ATS_PROMPT.format(
        resume_text=resume.raw_text,
        jd_text=jd_text,
    )

    try:

        result = _call_groq_json(
            prompt
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"ATS check failed: {str(e)}"
        )

    resume.ats = result

    db.commit()
    db.refresh(resume)

    return result


# ============================================================
# Cover letter
# ============================================================

@router.post("/cover-letter")
def generate_cover_letter(
    payload: CoverLetterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    resume = _get_resume(
        db,
        current_user.id
    )

    if not resume or not resume.raw_text:

        raise HTTPException(
            status_code=404,
            detail="Build or upload a resume first"
        )

    prompt = COVER_LETTER_PROMPT.format(
        resume_text=resume.raw_text,
        jd_text=payload.jd_text.strip(),
        company=(
            payload.company
            or "the company"
        ),
        role=(
            payload.role
            or "the role"
        ),
    )

    try:

        content = _call_groq_text(
            prompt
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "Cover letter generation failed: "
                f"{str(e)}"
            ),
        )

    existing = (
        db.query(CoverLetter)
        .filter(
            CoverLetter.user_id
            == current_user.id
        )
        .first()
    )

    if existing:

        existing.company = payload.company
        existing.role = payload.role
        existing.jd_text = payload.jd_text
        existing.content = content

        letter = existing

    else:

        letter = CoverLetter(
            user_id=current_user.id,
            company=payload.company,
            role=payload.role,
            jd_text=payload.jd_text,
            content=content,
        )

        db.add(letter)

    db.commit()
    db.refresh(letter)

    return {
        "id": letter.id,
        "company": letter.company,
        "role": letter.role,
        "content": letter.content,
    }


# ============================================================
# Get cover letter
# ============================================================

@router.get("/cover-letter")
def get_cover_letter(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    letter = (
        db.query(CoverLetter)
        .filter(
            CoverLetter.user_id
            == current_user.id
        )
        .first()
    )

    if not letter:

        return {
            "message": "No cover letter yet"
        }

    return {
        "id": letter.id,
        "company": letter.company,
        "role": letter.role,
        "content": letter.content,
    }