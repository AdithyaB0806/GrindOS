import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Backend.ai import AIError, ai_unavailable, generate_json, generate_text
from Backend.database import SessionLocal, get_db
from Backend.ratelimit import spend_ai_budget
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

log = logging.getLogger("grindos.roadmap")

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
being job-ready for this career path.The tech stack should be of the latest requirnments of the company, Search for the latest requirements of the company and make sure you are aware of the latest technologies and tools that are in demand in the Indian job market. Each phase should be a logical step forward, with each item being a concrete skill or topic to learn.
Each phase should build on the previous one. Keep each
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

    data = generate_json(prompt, validate=_clean_phases)
    return data["phases"]


def _clean_phases(data) -> dict:
    """
    Make the AI's phases safe to store: real strings, sane lengths, a phase
    number for each, and no empty phases. An unusable reply is retried.
    """
    raw = data.get("phases") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        raise ValueError("no phases in AI reply")

    phases = []
    for index, phase in enumerate(raw, start=1):
        if not isinstance(phase, dict):
            continue
        items = [
            " ".join(str(i).split())[:140]
            for i in (phase.get("items") or [])
            if isinstance(i, (str, int, float)) and str(i).strip()
        ]
        if not items:
            continue
        phases.append(
            {
                "phase_number": len(phases) + 1,
                "phase_title": " ".join(str(phase.get("phase_title") or f"Phase {index}").split())[:140],
                "items": items,
            }
        )
    if not phases:
        raise ValueError("AI reply had no usable phases")
    return {"phases": phases}


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


def _require_guide(data):
    if not isinstance(data, dict) or not data.get("summary"):
        raise ValueError("guide is missing its summary")
    return data


def generate_item_guide(career_title: str, item_title: str, phase_title: str, retries: int = 1) -> dict:
    prompt = GUIDE_PROMPT.format(
        career_title=career_title,
        item_title=item_title,
        phase_title=phase_title,
    )
    return generate_json(prompt, validate=_require_guide, retries=retries)


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
        # no retry here: a guide that fails is generated on demand when opened
        content = generate_item_guide(
            career_title=career_title,
            item_title=item.title,
            phase_title=item.phase_title or "",
            retries=0,
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
    return generate_text(prompt)


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
    Create-or-link a Skill row for a roadmap item. Matched by (user_id, name)
    so regenerating re-links the same skill instead of duplicating it. A
    re-linked skill keeps its progress, and the new item starts at that status.
    """
    skill = (
        db.query(Skill)
        .filter(Skill.user_id == user_id, Skill.name == item.title)
        .first()
    )
    if skill:
        skill.roadmap_item_id = item.id
        item.status = skill.status or "not_started"
    else:
        db.add(
            Skill(
                user_id=user_id,
                roadmap_item_id=item.id,
                name=item.title,
                status="not_started",
            )
        )


def _generate_guides_in_background(roadmap_id: int) -> None:
    """
    Runs after the response. It opens its own short database sessions and keeps
    none open while waiting on the AI, so it doesn't hold a connection for minutes.
    """
    try:
        with SessionLocal() as db:
            roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
            if not roadmap:
                return
            career_title = roadmap.career_title
            items = db.query(RoadmapItem).filter(RoadmapItem.roadmap_id == roadmap_id).all()
            have = {
                g.roadmap_item_id
                for g in db.query(RoadmapItemGuide)
                .filter(RoadmapItemGuide.roadmap_item_id.in_([i.id for i in items]))
                .all()
            }
            todo = [
                RoadmapItem(id=i.id, title=i.title, phase_title=i.phase_title)  # detached copies
                for i in items
                if i.id not in have
            ]

        guides = _build_guides_for_items(career_title, todo)

        with SessionLocal() as db:
            for item_id, content in guides.items():
                try:
                    with db.begin_nested():
                        db.add(RoadmapItemGuide(roadmap_item_id=item_id, content=content))
                        db.flush()
                except IntegrityError:
                    # opened on demand meanwhile, or the roadmap was rebuilt
                    continue
            db.commit()
    except Exception:  # noqa: BLE001 - a background job must never crash the worker
        log.exception("Background guide generation failed for roadmap %s", roadmap_id)


@router.post("/generate")
def generate_roadmap(
    background_tasks: BackgroundTasks,
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
            (c for c in career_paths if str(c.get("title", "")).lower() == career_title.strip().lower()),
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

    spend_ai_budget(current_user)
    try:
        phases = generate_roadmap_phases(
            career_title=chosen["title"],
            matching_skills=chosen.get("matching_skills", []),
            skill_gaps=chosen.get("skill_gaps", []),
            career_goal=career_goal,
            study_time=study_time,
        )
    except AIError:
        raise ai_unavailable("Building your roadmap")

    orphan_candidates: list[int] = []
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
            # remember which skills were roadmap-linked, so unmatched,
            # never-started ones can be cleaned up after re-linking
            orphan_candidates = [
                s.id
                for s in db.query(Skill).filter(Skill.roadmap_item_id.in_(old_ids)).all()
            ]
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
                phase_number=phase["phase_number"],
                phase_title=phase["phase_title"],
                title=item_title,
                order_index=order_index,
                status="not_started",
            )
            db.add(new_item)
            db.flush()  # assigns new_item.id so the skill row can link to it
            order_index += 1

            _sync_skill_for_item(db, user_id, new_item)

    # autoflush is off, so save the last re-link before the cleanup query runs
    db.flush()

    # old roadmap skills that match nothing in the new roadmap and were never
    # started are just clutter; started ones are kept so progress isn't lost
    if orphan_candidates:
        db.query(Skill).filter(
            Skill.id.in_(orphan_candidates),
            Skill.roadmap_item_id.is_(None),
            Skill.status == "not_started",
        ).delete(synchronize_session=False)

    db.commit()

    # Guides for every item are generated AFTER the response goes out. Doing
    # 15-30 AI calls inside the request made it run for minutes, which hosts
    # cut off. An item opened before its guide is ready still works: the guide
    # endpoint generates it on demand.
    background_tasks.add_task(_generate_guides_in_background, roadmap.id)

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
        .filter(Skill.user_id == current_user.id, Skill.roadmap_item_id == item.id)
        .first()
    ) or (
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
    item, roadmap = _authorize_item(item_id, current_user, db)
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
    spend_ai_budget(current_user)
    try:
        content = generate_item_guide(
            career_title=roadmap.career_title,
            item_title=item.title,
            phase_title=item.phase_title or "",
        )
    except AIError:
        raise ai_unavailable("Building this guide")
    db.add(RoadmapItemGuide(roadmap_item_id=item.id, content=content))
    try:
        db.commit()
    except IntegrityError:
        # the background job stored one a moment ago; use that
        db.rollback()
        existing = (
            db.query(RoadmapItemGuide)
            .filter(RoadmapItemGuide.roadmap_item_id == item.id)
            .first()
        )
        content = existing.content if existing else content
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

    spend_ai_budget(current_user)
    try:
        answer = generate_chat_reply(
            career_title=roadmap.career_title,
            item_title=item.title,
            phase_title=item.phase_title,
            guide_summary=guide_summary,
            messages=messages,
            question=question,
        )
    except AIError:
        raise ai_unavailable("The mentor")

    if not answer:
        raise ai_unavailable("The mentor")

    messages.append({"role": "user", "content": question})
    messages.append({"role": "assistant", "content": answer})
    messages = messages[-40:]  # only the last 10 are sent to the model; don't store forever

    if chat:
        chat.messages = messages
    else:
        chat = RoadmapItemChat(roadmap_item_id=item.id, messages=messages)
        db.add(chat)

    db.commit()

    return {"item_id": item.id, "messages": messages}