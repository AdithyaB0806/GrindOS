# GrindOS

Your entire job search, in one place — instead of six.

I got tired of bouncing between a career quiz site, a random roadmap PDF,
a spreadsheet for job applications, a notes app for interview questions, and
a separate resume tool that never quite matched what I actually needed. So
I built GrindOS: one place that takes you from "I don't know what I want to
be" all the way to "I have a tailored resume, a cover letter, and I've
mock-interviewed for this exact role."

It's built specifically around the Indian fresher/SDE job market — the
assessment, the AI recommendations, the interview prep, all of it is tuned
for that, not a generic "career advice" template.

---

## What it actually does

**Figure out what to aim for.**
A 12-question assessment (no generic "what's your MBTI" nonsense — actual
questions about what you enjoy building and solving) feeds into Gemini,
which comes back with 3 career paths that genuinely fit your answers: why
each one fits, what skills you already have, what's missing, and real job
titles to search for. Don't like the suggestions? Tell it what to change in
plain English and it'll try again.

**Get a roadmap, not just a list.**
Pick a path and GrindOS builds a phase-by-phase roadmap for it. Each item
has its own AI guide and a chat you can ask follow-up questions in — "why
this before that," "what should I actually build," whatever.

**Track skills without a spreadsheet.**
Roadmap items turn into tracked skills automatically, grouped by phase.
Add your own on top for anything you're learning outside the roadmap.

**Keep the job hunt in one tab.**
Wishlist → Applied → OA → Interview → Offer / Rejected. Company, role,
source, link, notes. Nothing fancy, just doesn't lose track of things.

**Actually prep for interviews.**
Two modes, because they're different exercises:
- A **question bank** (DSA, system design, domain, behavioral, HR) you work
  through at your own pace, marking things practicing/nailed as you go.
- A **mock interview** — 8 questions, you type real answers, and it gives
  you honest feedback: a score, what you did well, what's missing, and what
  a strong answer would've covered. Not a participation trophy generator.

**Handle the resume properly.**
- No resume yet? Build one through a guided form and get back an actual
  ATS-safe `.docx` — single column, real headings, nothing an ATS parser
  chokes on.
- Already have one? Upload the PDF/DOCX and it pulls the text out.
- Got a JD you're applying to? Tailor your resume to it — it mirrors the
  JD's language where your real experience supports it, but it will not
  invent a project you never built.
- Curious if it'll even get past the bot? Run the ATS checker — score,
  what's broken, what keywords are missing.
- Need a cover letter? It writes one grounded only in what's actually on
  your resume — no "[Your Name]" placeholders, no fluff.

**One dashboard, all of it.**
Roadmap progress, skills average, job pipeline, interview-prep progress —
at a glance, with click-through to each section.

---

## Stack

Nothing exotic — I picked boring, reliable tools on purpose so I could
actually ship this instead of fighting the framework.

- **Backend:** FastAPI + SQLAlchemy + Pydantic. JWT auth (`python-jose`),
  bcrypt password hashing (`passlib`).
- **AI:** Google Gemini, via `google-genai`.
- **Resume parsing:** `pdfplumber` for PDFs, `python-docx` for DOCX (both
  reading and writing).
- **Frontend:** React + Vite, no UI framework — the whole design system is
  a single hand-written `theme.css` (dark, instrument-panel aesthetic,
  amber signal accent — GrindOS looks like GrindOS, not a Bootstrap site).
- **DB:** anything SQLAlchemy talks to — I use Postgres.

---

## Project layout

```
Backend/
  main.py                  # app + routers + CORS
  database.py                # engine/session
  models.py                   # ORM models
  schemas.py                   # Pydantic schemas
  auth.py, security.py           # JWT + hashing
  routes.py                       # register / login / me
  assessment.py, assessment_questions.py
  ai_recomendation.py               # career path recommendations
  roadmap.py                         # roadmap + per-item guide/chat
  skills.py
  jobs.py
  interview.py                        # question bank
  mock_interview.py                    # free-text mock interview
  resume.py                             # build / upload / tailor / ATS / cover letter
  dashboard.py                           # aggregate summary
  requirnments.txt

Frontend/
  index.html, main.jsx
  App.jsx      # yep, the whole app — every view lives here
  api.js        # fetch client for the backend
  theme.css      # the whole design system
  package.json, vite.config.js
```

---

## Running it yourself

### Backend

You'll need Python 3.11+, a Postgres DB (or point `DATABASE_URL` at
whatever SQLAlchemy supports), and a Gemini API key.

```bash
cd Backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirnments.txt
```

Drop a `.env` in `Backend/`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/grindos
SECRET_KEY=make-this-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
GEMINI_API_KEY=your-gemini-api-key
```

```bash
uvicorn main:app --reload
```

Tables create themselves on first run — no migration step for a fresh DB.
Swagger docs at `localhost:8000/docs` if you want to poke at the API
directly.

### Frontend

Node 18+.

```bash
cd Frontend
npm install
```

Only need a `.env` here if your backend isn't at `localhost:8000`:

```env
VITE_API_URL=http://localhost:8000
```

```bash
npm run dev
```

`npm run build` + `npm run preview` for a production build.

---

## How auth works, briefly

Login/register hand back a JWT, stashed in `localStorage`. Every request
after that sends `Authorization: Bearer <token>` — no `user_id` anywhere in
the API, the token *is* the identity.

---

## Rough edges 

- `database.py` still has some `print()` debug lines from when I was
  chasing a connection bug — harmless, but should go before this is
  actually deployed anywhere.
- Uploading a scanned/image-only PDF won't work — there's no OCR yet, so it
  just tells you it couldn't find any text instead of pretending.
- Every AI feature depends on `GEMINI_API_KEY` being valid and the model
  string being real on your account — if that's off, you'll get a loud 500
  instead of a silent failure, which is at least honest.
- Resume upload has a known bug worth digging into before relying on it.
- Mock interview is text-only right now — no speech input/analysis yet.

---

## License

Haven't picked one. MIT's the obvious default if you want to open it up
later — swap this section out when you decide.
