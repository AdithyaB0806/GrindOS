import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from google import genai
from google.genai import types

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from Backend.database import get_db
from Backend.models import (
    User,
    Assessment,
    Recommendation,
    Roadmap,
    RoadmapItem,
    RoadmapItemGuide,
    RoadmapItemChat,
    Skill,
)
from Backend.schemas import RoadmapItemStatusUpdate, ChatAskRequest
from Backend.auth import get_current_user

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter(prefix="/roadmap", tags=["Roadmap"])

ALLOWED_STATUSES = {"not_started", "learning", "practicing", "completed"}

ROADMAP_PROMPT = """
You are a career mentor for computer science / tech students in India, building a step-by-step
learning roadmap. Be aware of the current Indian tech job market and today's most relevant,
in-demand tools and skills - don't default to outdated technology choices.

The student is aiming for this career path:
{career_title}

Their current matching skills:
{matching_skills}

Their skill gaps:
{skill_gaps}

Their primary career goal:
{career_goal}

Time they can dedicate to learning each week:
{study_time}

Generate a structured, ordered, phase-based roadmap that takes them from where they are now to
being job-ready for this career path. Each phase should build on the previous one. Keep each
phase focused (roughly 3-6 items) and keep the whole roadmap realistic given their weekly study
time. Order phases from foundational to advanced, ending with a project/portfolio phase.

Respond ONLY with valid JSON in this exact schema, no markdown, no extra text:
{{
  "phases": [
    {{
      "phase_number": 1,
      "phase_title": "string",
      "items": ["string", "string"]
    }}
  ]
}}
"""


def generate_roadmap_phases(
    career_title: str,
    matching_skills: list,
    skill_gaps: list,
    career_goal: str,
    study_time: str,
) -> list:
    prompt = ROADMAP_PROMPT.format(
        career_title=career_title,
        matching_skills=json.dumps(matching_skills),
        skill_gaps=json.dumps(skill_gaps),
        career_goal=career_goal,
        study_time=study_time,
    )

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    data = json.loads(response.text)
    return data.get("phases", [])


def _serialize_roadmap(roadmap: Roadmap, db: Session) -> dict:
    items = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.roadmap_id == roadmap.id)
        .order_by(RoadmapItem.order_index)
        .all()
    )

    phases_by_number = {}
    for item in items:
        phase = phases_by_number.setdefault(
            item.phase_number,
            {
                "phase_number": item.phase_number,
                "phase_title": item.phase_title,
                "items": [],
            },
        )
        phase["items"].append(
            {"id": item.id, "title": item.title, "status": item.status}
        )

    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")
    progress_percent = round((completed / total) * 100, 1) if total else 0.0

    return {
        "id": roadmap.id,
        "career_title": roadmap.career_title,
        "progress_percent": progress_percent,
        "phases": sorted(phases_by_number.values(), key=lambda p: p["phase_number"]),
    }


GUIDE_PROMPT = """
You are a practical mentor for computer science / tech students in India.
The student is aiming for: {career_title}
They clicked this roadmap item: {item_title}
It sits in phase: {phase_title}

Tell them exactly how to learn it this week. Prefer currently relevant tools and
resources used in the Indian job market. Do not recommend outdated stacks.

Respond ONLY with valid JSON, no markdown:
{{
  "summary": "2-3 sentences: what this is and why it matters for the career",
  "learn_this": ["concrete subtopic 1", "subtopic 2", "subtopic 3", "subtopic 4"],
  "practice": "one paragraph on how to practice this week",
  "youtube": [
    {{
      "channel": "channel name",
      "focus": "why this channel fits this topic",
      "search_query": "exact YouTube search including the channel name and topic"
    }}
  ],
  "resources": [
    {{
      "name": "resource name",
      "url": "https://real-well-known-url",
      "why": "why open this"
    }}
  ],
  "project_idea": "a small weekend project that proves they learned it"
}}

Rules:
- 3-5 youtube entries. Use real, well-known channels that actually teach this topic
  (examples when they fit: freeCodeCamp, NeetCode, Kunal Kushwaha, CodeWithHarry,
  Traversy Media, Fireship, ThePrimeagen, Bro Code, Chai aur Code, Take U Forward,
  System Design Interview / ByteByteGo, Maria Santos). Do not invent channels.
- search_query must be specific enough to land on the right playlist or video.
- resources: 2-4 items, only real well-known docs/sites (MDN, official docs,
  LeetCode, NeetCode, roadmap.sh, AWS docs, etc.). Never fabricate URLs.
"""


def generate_item_guide(career_title: str, item_title: str, phase_title: str) -> dict:
    prompt = GUIDE_PROMPT.format(
        career_title=career_title,
        item_title=item_title,
        phase_title=phase_title,
    )
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def _build_guides_for_items(career_title: str, items: list[RoadmapItem]) -> dict[int, dict]:
    """
    Generate a guide for every item in one shot (called right after a roadmap
    is created/regenerated) so item detail pages never have to hit the AI on
    click - they just read what's already stored. Runs the calls concurrently
    since doing 15-30 of these sequentially would make roadmap generation feel
    like it hung. A guide that fails to generate here is simply skipped; the
    /items/{id}/guide endpoint still generates-and-caches on demand as a
    fallback, so one bad call never blocks the whole roadmap.
    """
    guides_by_item_id: dict[int, dict] = {}
    if not items:
        return guides_by_item_id

    def _one(item: RoadmapItem):
        content = generate_item_guide(
            career_title=career_title,
            item_title=item.title,
            phase_title=item.phase_title or "",
        )
        return item.id, content

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_one, item) for item in items]
        for future in as_completed(futures):
            try:
                item_id, content = future.result()
                guides_by_item_id[item_id] = content
            except Exception:
                # one item's guide failing shouldn't fail roadmap creation -
                # it'll just be generated on-demand the first time it's opened
                continue

    return guides_by_item_id


CHAT_PROMPT = """
You are a friendly, sharp mentor helping a computer science / tech student in India
who is working through a learning roadmap. Answer their doubt about the specific
roadmap item below. Be concise, practical, and specific to the Indian job market
where relevant. Plain text only - short paragraphs or bullet points, no markdown
headers, no JSON, no code fences unless the student is asking about actual code.

Career path: {career_title}
Current roadmap item: {item_title} (phase: {phase_title})
Reference brief for this item: {guide_summary}

Conversation so far:
{history}

Student's new question: {question}

Answer directly and helpfully in under 180 words unless the question genuinely
needs more room.
"""


def _format_chat_history(messages: list) -> str:
    if not messages:
        return "(no earlier messages)"
    lines = []
    for m in messages[-10:]:
        speaker = "Student" if m.get("role") == "user" else "Mentor"
        lines.append(f"{speaker}: {m.get('content', '')}")
    return "\n".join(lines)


def generate_chat_reply(
    career_title: str,
    item_title: str,
    phase_title: str,
    guide_summary: str | None,
    messages: list,
    question: str,
) -> str:
    prompt = CHAT_PROMPT.format(
        career_title=career_title,
        item_title=item_title,
        phase_title=phase_title or "",
        guide_summary=guide_summary or "Not generated yet.",
        history=_format_chat_history(messages),
        question=question,
    )
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
    )
    return (response.text or "").strip()


def _authorize_item(item_id: int, current_user: User, db: Session) -> tuple[RoadmapItem, Roadmap]:
    """
    Shared ownership check for anything scoped to a single roadmap item
    (guide, chat, status updates): item must exist and its roadmap must
    belong to the requesting user.
    """
    item = db.query(RoadmapItem).filter(RoadmapItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")
    roadmap = db.query(Roadmap).filter(Roadmap.id == item.roadmap_id).first()
    if not roadmap or roadmap.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this item")
    return item, roadmap


def _sync_skill_for_item(db: Session, user_id: int, item: RoadmapItem):
    """
    Create-or-link a Skill row for a roadmap item so the skill dashboard
    stays in step with the roadmap without the caller having to manage it.
    Matched by (user_id, name) so re-generating a roadmap re-links to the
    same skill instead of duplicating it and losing prior progress.
    """
    skill = (
        db.query(Skill)
        .filter(Skill.user_id == user_id, Skill.name == item.title)
        .first()
    )
    if skill:
        skill.roadmap_item_id = item.id
    else:
        skill = Skill(
            user_id=user_id,
            roadmap_item_id=item.id,
            name=item.title,
            status="not_started",
        )
        db.add(skill)


@router.post("/generate")
def generate_roadmap(
    career_title: str | None = None,
    regenerate: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    existing = db.query(Roadmap).filter(Roadmap.user_id == user_id).first()
    if existing and not regenerate:
        return _serialize_roadmap(existing, db)

    recommendation = (
        db.query(Recommendation).filter(Recommendation.user_id == user_id).first()
    )
    if not recommendation:
        raise HTTPException(
            status_code=404,
            detail="No recommendation found. Generate a recommendation first.",
        )

    career_paths = recommendation.result.get("career_paths", [])
    if not career_paths:
        raise HTTPException(status_code=500, detail="Recommendation has no career paths")

    if career_title:
        chosen = next(
            (c for c in career_paths if c["title"].lower() == career_title.lower()),
            None,
        )
        if not chosen:
            raise HTTPException(
                status_code=404,
                detail=f"Career path '{career_title}' not found in user's recommendations",
            )
    else:
        chosen = career_paths[0]

    assessment = (
        db.query(Assessment)
        .filter(Assessment.user_id == user_id)
        .order_by(Assessment.id.desc())
        .first()
    )
    study_time = assessment.answers.get("study_time", "Not specified") if assessment else "Not specified"
    career_goal = assessment.answers.get("career_goal", "Not specified") if assessment else "Not specified"

    try:
        phases = generate_roadmap_phases(
            career_title=chosen["title"],
            matching_skills=chosen.get("matching_skills", []),
            skill_gaps=chosen.get("skill_gaps", []),
            career_goal=career_goal,
            study_time=study_time,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI roadmap generation failed: {str(e)}")

    if not phases:
        raise HTTPException(status_code=500, detail="AI returned an empty roadmap")

    if existing and regenerate:
        old_ids = [
            item.id
            for item in db.query(RoadmapItem)
            .filter(RoadmapItem.roadmap_id == existing.id)
            .all()
        ]
        if old_ids:
            db.query(RoadmapItemGuide).filter(
                RoadmapItemGuide.roadmap_item_id.in_(old_ids)
            ).delete(synchronize_session=False)
            # chat history is tied to the specific (now-replaced) item content,
            # so it doesn't make sense to carry it over - drop it along with
            # the guide rather than leaving it orphaned/blocking the delete.
            db.query(RoadmapItemChat).filter(
                RoadmapItemChat.roadmap_item_id.in_(old_ids)
            ).delete(synchronize_session=False)
            # Skill.roadmap_item_id is a FK into roadmap_items - unlink before
            # deleting the old items or Postgres blocks the delete. The skill
            # itself stays (so progress isn't lost) and _sync_skill_for_item
            # re-links it to the matching new item by name below.
            db.query(Skill).filter(Skill.roadmap_item_id.in_(old_ids)).update(
                {Skill.roadmap_item_id: None}, synchronize_session=False
            )
        db.query(RoadmapItem).filter(RoadmapItem.roadmap_id == existing.id).delete()
        existing.career_title = chosen["title"]
        roadmap = existing
        db.commit()
    else:
        roadmap = Roadmap(user_id=user_id, career_title=chosen["title"])
        db.add(roadmap)
        db.commit()
        db.refresh(roadmap)

    order_index = 0
    for phase in phases:
        for item_title in phase.get("items", []):
            new_item = RoadmapItem(
                roadmap_id=roadmap.id,
                phase_number=phase.get("phase_number", 0),
                phase_title=phase.get("phase_title", ""),
                title=item_title,
                order_index=order_index,
                status="not_started",
            )
            db.add(new_item)
            db.flush()  # assigns new_item.id so the skill row can link to it
            order_index += 1

            _sync_skill_for_item(db, user_id, new_item)

    db.commit()

    # Generate + store every item's guide now, while we're already in the
    # roadmap-creation flow, instead of burning a fresh AI call (and making
    # the student wait) every time they open an item later.
    new_items = (
        db.query(RoadmapItem)
        .filter(RoadmapItem.roadmap_id == roadmap.id)
        .all()
    )
    try:
        guides_by_item_id = _build_guides_for_items(roadmap.career_title, new_items)
    except Exception:
        guides_by_item_id = {}

    for item_id, content in guides_by_item_id.items():
        db.add(RoadmapItemGuide(roadmap_item_id=item_id, content=content))
    if guides_by_item_id:
        db.commit()

    return _serialize_roadmap(roadmap, db)


@router.get("/")
def get_roadmap(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roadmap = db.query(Roadmap).filter(Roadmap.user_id == current_user.id).first()
    if not roadmap:
        return {"message": "No roadmap available"}
    return _serialize_roadmap(roadmap, db)


@router.patch("/items/{item_id}/status")
def update_item_status(
    item_id: int,
    payload: RoadmapItemStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(ALLOWED_STATUSES)}",
        )

    item = db.query(RoadmapItem).filter(RoadmapItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")

    # an item alone doesn't prove ownership - walk up to its roadmap to check
    roadmap = db.query(Roadmap).filter(Roadmap.id == item.roadmap_id).first()
    if not roadmap or roadmap.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this item")

    item.status = payload.status

    # keep the linked skill's status in lockstep with the roadmap item
    skill = (
        db.query(Skill)
        .filter(Skill.user_id == current_user.id, Skill.name == item.title)
        .first()
    )
    if skill:
        skill.status = payload.status

    db.commit()
    db.refresh(item)

    return {"id": item.id, "title": item.title, "status": item.status}

@router.get("/items/{item_id}/guide")
def get_item_guide(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(RoadmapItem).filter(RoadmapItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item not found")
    roadmap = db.query(Roadmap).filter(Roadmap.id == item.roadmap_id).first()
    if not roadmap or roadmap.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this item")
    cached = (
        db.query(RoadmapItemGuide)
        .filter(RoadmapItemGuide.roadmap_item_id == item.id)
        .first()
    )
    if cached:
        return {
            "item_id": item.id,
            "title": item.title,
            "phase_title": item.phase_title,
            "status": item.status,
            "guide": cached.content,
        }
    try:
        content = generate_item_guide(
            career_title=roadmap.career_title,
            item_title=item.title,
            phase_title=item.phase_title or "",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI guide generation failed: {str(e)}")
    cached = RoadmapItemGuide(roadmap_item_id=item.id, content=content)
    db.add(cached)
    db.commit()
    return {
        "item_id": item.id,
        "title": item.title,
        "phase_title": item.phase_title,
        "status": item.status,
        "guide": content,
    }


@router.get("/items/{item_id}/chat")
def get_item_chat(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item, _ = _authorize_item(item_id, current_user, db)
    chat = (
        db.query(RoadmapItemChat)
        .filter(RoadmapItemChat.roadmap_item_id == item.id)
        .first()
    )
    return {"item_id": item.id, "messages": chat.messages if chat else []}


@router.post("/items/{item_id}/ask")
def ask_item_doubt(
    item_id: int,
    payload: ChatAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    item, roadmap = _authorize_item(item_id, current_user, db)

    guide = (
        db.query(RoadmapItemGuide)
        .filter(RoadmapItemGuide.roadmap_item_id == item.id)
        .first()
    )
    guide_summary = (guide.content or {}).get("summary") if guide else None

    chat = (
        db.query(RoadmapItemChat)
        .filter(RoadmapItemChat.roadmap_item_id == item.id)
        .first()
    )
    messages = list(chat.messages) if chat and chat.messages else []

    try:
        answer = generate_chat_reply(
            career_title=roadmap.career_title,
            item_title=item.title,
            phase_title=item.phase_title,
            guide_summary=guide_summary,
            messages=messages,
            question=question,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat failed: {str(e)}")

    if not answer:
        raise HTTPException(status_code=500, detail="AI returned an empty answer")

    messages.append({"role": "user", "content": question})
    messages.append({"role": "assistant", "content": answer})

    if chat:
        chat.messages = messages
    else:
        chat = RoadmapItemChat(roadmap_item_id=item.id, messages=messages)
        db.add(chat)

    db.commit()

    return {"item_id": item.id, "messages": messages}