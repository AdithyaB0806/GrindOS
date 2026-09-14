import { createContext, useContext, useEffect, useState, useRef } from "react";
import { api, ApiError } from "./api";
import "./theme.css";

/* ============================================================
   Auth context — holds the JWT + current user, persisted to
   localStorage so a refresh doesn't log you out.
   ============================================================ */

const AuthContext = createContext(null);
const useAuth = () => useContext(AuthContext);

function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("gos_token"));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me(token)
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("gos_token");
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const login = async (email, password) => {
    const res = await api.login({ email, password });
    localStorage.setItem("gos_token", res.access_token);
    setToken(res.access_token);
  };

  const register = async (name, email, password) => {
    await api.register({ name, email, password });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("gos_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/* ============================================================
   Shared bits
   ============================================================ */

function Alert({ kind = "error", children }) {
  if (!children) return null;
  return <div className={`gos-alert gos-alert-${kind}`}>{children}</div>;
}

function errorMessage(err) {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong. Try again.";
}

function BrandMark() {
  return (
    <div className="gos-brand">
      <span className="gos-brand-mark" />
       GRINDOS <small>career OS</small>
    </div>
  );
}

function youtubeSearch(query) {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}


/* ---------- circuit track: aggregate progress readout ---------- */

function CircuitTrack({ percent = 0, label }) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div className="circuit-track-wrap">
      {label && <div className="circuit-track-label">{label}</div>}
      <div className="circuit-track">
        <div className="circuit-track-fill" style={{ width: `${clamped}%` }}>
          <span className="circuit-track-head" />
        </div>
      </div>
      <div className="circuit-track-readout">
        <strong>{clamped}%</strong> grind complete
      </div>
    </div>
  );
}

/* ---------- stage rail: per-item status control ---------- */

const TRACKED_STAGES = ["learning", "practicing", "completed"];
const STAGE_LABEL = {
  not_started: "NOT STARTED",
  learning: "LEARNING",
  practicing: "PRACTICING",
  completed: "COMPLETED",
};
const STAGE_ORDER = ["not_started", ...TRACKED_STAGES];

const JOB_STATUSES = ["wishlist", "applied", "oa", "interview", "offer", "rejected"];
const JOB_STATUS_LABEL = {
  wishlist: "WISHLIST",
  applied: "APPLIED",
  oa: "OA / TEST",
  interview: "INTERVIEW",
  offer: "OFFER",
  rejected: "REJECTED",
};
const JOB_SOURCES = ["LinkedIn", "Naukri", "Internshala", "Referral", "Career page", "Twitter / X", "Other"];

const INTERVIEW_STAGES = ["practicing", "nailed"];
const INTERVIEW_STAGE_ORDER = ["not_started", ...INTERVIEW_STAGES];
const INTERVIEW_STAGE_LABEL = {
  not_started: "NOT STARTED",
  practicing: "PRACTICING",
  nailed: "NAILED",
};
const INTERVIEW_CATEGORY_LABEL = {
  dsa: "DSA",
  system_design: "SYSTEM DESIGN",
  domain: "ROLE / DOMAIN",
  behavioral: "BEHAVIORAL",
  hr: "HR",
};

function youtubeSearchUrl(query) {
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
}

function StageRail({ status, onChange, disabled }) {
  const currentIndex = STAGE_ORDER.indexOf(status);

  return (
    <div className="stage-rail">
      <div className="stage-ticks">
        {TRACKED_STAGES.map((stage, i) => {
          const stageIndex = i + 1;
          const filled = stageIndex < currentIndex;
          const active = stageIndex === currentIndex;
          return (
            <button
              key={stage}
              type="button"
              title={STAGE_LABEL[stage]}
              aria-label={`Set status to ${STAGE_LABEL[stage]}`}
              className={`stage-tick ${filled ? "filled" : ""} ${active ? "active" : ""}`}
              disabled={disabled}
              onClick={() => onChange(active ? "not_started" : stage)}
            />
          );
        })}
      </div>
      <span className={`stage-label stage-label-${status}`}>{STAGE_LABEL[status] || status}</span>
    </div>
  );
}

function Navbar({ view, setView, hasRecommendation }) {
  const { user, logout } = useAuth();

  return (
    <div className="gos-navbar">
      <BrandMark />
      {user && (
        <div className="gos-nav-links">
          <button
            className={`gos-nav-btn ${view === "dashboard" ? "active" : ""}`}
            onClick={() => setView("dashboard")}
          >
            DASHBOARD
          </button>
          <button
            className={`gos-nav-btn ${
              view === "assessment" || view === "results" ? "active" : ""
            }`}
            onClick={() => setView(hasRecommendation ? "results" : "assessment")}
          >
            ASSESSMENT
          </button>
          <button
            className={`gos-nav-btn ${view === "roadmap" ? "active" : ""}`}
            onClick={() => setView("roadmap")}
          >
            ROADMAP
          </button>
          <button
            className={`gos-nav-btn ${view === "skills" ? "active" : ""}`}
            onClick={() => setView("skills")}
          >
            SKILLS
          </button>
           <button
            className={`gos-nav-btn ${view === "jobs" ? "active" : ""}`}
            onClick={() => setView("jobs")}
          >
            JOBS
          </button>
          <button
            className={`gos-nav-btn ${view === "interview" ? "active" : ""}`}
            onClick={() => setView("interview")}
          >
            INTERVIEW
          </button>
        </div>
      )}
      <div className="gos-nav-user">
        {user && (
          <>
            <span className="gos-user-chip">
              <strong>{user.name}</strong>
            </span>
            <button className="gos-btn" onClick={logout}>
              LOG OUT
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Auth screen — login / register toggle
   ============================================================ */

function AuthScreen() {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const { login, register } = useAuth();

  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register(form.name, form.email, form.password);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="gos-panel gos-card">
      <div className="gos-eyebrow">{mode === "login" ? "Sign in" : "Create account"}</div>
      <h1 className="gos-title">{mode === "login" ? "Welcome back" : "Start the grind"}</h1>
      <p className="gos-subtitle">
        {mode === "login"
          ? "Sign in to pick up your roadmap, assessment, and progress."
          : "One account tracks your assessment, roadmap, and interview prep."}
      </p>

      <Alert>{error}</Alert>

      <form onSubmit={submit}>
        {mode === "register" && (
          <div className="gos-field">
            <label className="gos-label">Name</label>
            <input
              className="gos-input"
              value={form.name}
              onChange={update("name")}
              placeholder="Adhi Kumar"
              required
            />
          </div>
        )}
        <div className="gos-field">
          <label className="gos-label">Email</label>
          <input
            className="gos-input"
            type="email"
            value={form.email}
            onChange={update("email")}
            placeholder="you@domain.com"
            required
          />
        </div>
        <div className="gos-field">
          <label className="gos-label">Password</label>
          <input
            className="gos-input"
            type="password"
            value={form.password}
            onChange={update("password")}
            placeholder="••••••••"
            required
          />
        </div>

        <button className="gos-btn gos-btn-primary" disabled={busy}>
          {busy ? "WORKING…" : mode === "login" ? "SIGN IN" : "CREATE ACCOUNT"}
        </button>
      </form>

      <div className="gos-form-footer">
        {mode === "login" ? (
          <>
            New here?{" "}
            <button className="gos-btn gos-btn-ghost" onClick={() => setMode("register")}>
              Create an account
            </button>
          </>
        ) : (
          <>
            Already grinding?{" "}
            <button className="gos-btn gos-btn-ghost" onClick={() => setMode("login")}>
              Sign in
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Assessment screen — one question at a time, grind-meter progress
   ============================================================ */

function Assessment({ onDone }) {
  const { token } = useAuth();
  const [questions, setQuestions] = useState(null);
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [otherAnswers, setOtherAnswers] = useState({});
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .getQuestions()
      .then(setQuestions)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  if (error && !questions) {
    return (
      <div className="gos-panel assess-card">
        <Alert>{error}</Alert>
      </div>
    );
  }

  if (!questions) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading assessment…
      </div>
    );
  }

  const q = questions[step];
  const selected = answers[q.key];
  const isLast = step === questions.length - 1;

  const choose = (option) => {
    setAnswers((a) => ({ ...a, [q.key]: option }));
  };

  const next = async () => {
    if (!isLast) {
      setStep((s) => s + 1);
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const finalAnswers = { ...answers };

      Object.keys(otherAnswers).forEach((key) => {
        if (answers[key] === "Other" && otherAnswers[key]?.trim()) {
          finalAnswers[key] = otherAnswers[key].trim();
        }
      });

      await api.submitAssessment({ answers: finalAnswers, token });

      const recommendation = await api.generateRecommendation(token);

      onDone(recommendation);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  const back = () => setStep((s) => Math.max(0, s - 1));

  return (
    <div className="gos-panel assess-card">
      <div className="grind-meter-label">
        <span>
          QUESTION <strong>{step + 1}</strong> / {questions.length}
        </span>
        <span>{Math.round(((step + (selected ? 1 : 0)) / questions.length) * 100)}% GRIND</span>
      </div>
      <div className="grind-meter">
        {questions.map((_, i) => (
          <div
            key={i}
            className={`grind-seg ${
              i < step || (i === step && selected) ? "done" : i === step ? "current" : ""
            }`}
          />
        ))}
      </div>

      <Alert>{error}</Alert>

      <div className="assess-qnum">SKILL_PROBE // {q.key}</div>
      <h2 className="assess-question">{q.question}</h2>

      <div className="assess-options">
        {q.options.map((opt, i) => (
          <div key={opt}>
            <button
              type="button"
              className={`assess-option ${selected === opt ? "selected" : ""}`}
              onClick={() => choose(opt)}
            >
              <span className="assess-option-key">{String.fromCharCode(65 + i)}</span>
              {opt}
            </button>

            {opt === "Other" && selected === "Other" && (
              <input
                className="gos-input"
                type="text"
                placeholder="Tell us more..."
                value={otherAnswers[q.key] || ""}
                onChange={(e) =>
                  setOtherAnswers((prev) => ({
                    ...prev,
                    [q.key]: e.target.value,
                  }))
                }
                autoFocus
              />
            )}
          </div>
        ))}
      </div>

      <div className="assess-nav">
        <button className="gos-btn" onClick={back} disabled={step === 0}>
          BACK
        </button>
        <button
          className="gos-btn gos-btn-primary"
          style={{ width: "auto" }}
          onClick={next}
          disabled={
            !selected ||
            submitting ||
            (selected === "Other" && !otherAnswers[q.key]?.trim())
          }
        >
          {submitting ? "SAVING…" : isLast ? "SUBMIT ASSESSMENT" : "NEXT"}
        </button>
      </div>
    </div>
  );
}

/* ============================================================
   Dashboard — profile readout + roadmap teaser
   ============================================================ */

function RecommendationResult({ result, onRetake, onChoosePath, onResultUpdated }) {
  const { token } = useAuth();
  const [feedback, setFeedback] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState("");

  if (!result) return null;

  const regenerate = async (e) => {
    e.preventDefault();
    const note = feedback.trim();
    if (!note || regenerating) return;
    setRegenerating(true);
    setError("");
    try {
      const data = await api.regenerateRecommendation({ token, feedback: note });
      onResultUpdated?.(data);
      setFeedback("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRegenerating(false);
    }
  };

  return (
    <div className="gos-shell gos-shell-wide">
      <div className="gos-eyebrow">AI analysis complete</div>
      <h1 className="gos-title">Your career profile</h1>
      <p className="gos-subtitle">
        GrindOS analyzed your assessment answers. Pick a path to build a roadmap for it, or tell
        it what to change and get an updated set.
      </p>

      <Alert>{error}</Alert>

      <div className="rec-grid">
        {result.career_paths?.map((career, index) => (
          <div className="gos-panel terminal-panel rec-card" key={career.title}>
            <div className="terminal-head">
              <span className="terminal-dot" /> path_{String(index + 1).padStart(2, "0")}
            </div>
            <h2 className="guide-title">{career.title}</h2>
            <p className="guide-summary">{career.fit_reason}</p>

            {career.matching_skills?.length > 0 && (
              <>
                <h3 className="guide-h">Matching skills</h3>
                <ul className="guide-list">
                  {career.matching_skills.map((skill) => (
                    <li key={skill}>{skill}</li>
                  ))}
                </ul>
              </>
            )}

            {career.skill_gaps?.length > 0 && (
              <>
                <h3 className="guide-h">Skill gaps</h3>
                <ul className="guide-list">
                  {career.skill_gaps.map((gap) => (
                    <li key={gap}>{gap}</li>
                  ))}
                </ul>
              </>
            )}

            {career.example_roles?.length > 0 && (
              <>
                <h3 className="guide-h">Roles to search for</h3>
                <ul className="guide-list">
                  {career.example_roles.map((role) => (
                    <li key={role}>{role}</li>
                  ))}
                </ul>
              </>
            )}

            <button
              type="button"
              className="gos-btn gos-btn-primary rec-choose-btn"
              onClick={() => onChoosePath?.(career.title)}
            >
              BUILD ROADMAP FOR THIS PATH →
            </button>
          </div>
        ))}
      </div>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> next_skill
        </div>
        <h2 className="guide-title">{result.next_skill_to_learn}</h2>
      </div>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> refine.suggestions
        </div>
        <p className="gos-empty-note" style={{ marginBottom: 12 }}>
          Not quite it? Tell it what to change — more remote-friendly roles, less data-heavy,
          lean more into your Python projects, whatever's on your mind — and it'll rebuild these
          three paths with that in mind.
        </p>
        <form onSubmit={regenerate}>
          <textarea
            className="gos-input rec-feedback-input"
            rows={3}
            placeholder="e.g. I'd rather avoid pure data roles and lean more backend…"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={regenerating}
          />
          <div className="rec-actions-row">
            <button
              type="submit"
              className="gos-btn gos-btn-primary"
              style={{ width: "auto" }}
              disabled={regenerating || !feedback.trim()}
            >
              {regenerating ? "UPDATING…" : "GET UPDATED SUGGESTIONS"}
            </button>
            <button type="button" className="gos-btn gos-btn-ghost" onClick={onRetake}>
              RETAKE ASSESSMENT
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Dashboard({ justSubmitted, refreshKey, onViewAnalysis, onGoRoadmap, onGoJobs, onGoInterview, onGoSkills, onGoAssessment }) {
  const { user, token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getDashboardSummary(token)
      .then(setSummary)
      .catch((err) => setError(errorMessage(err)));
  }, [token, refreshKey]);

  if (!summary && !error) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading command center…
      </div>
    );
  }

  const skills = summary?.skills;
  const roadmap = summary?.roadmap;
  const jobs = summary?.jobs;
  const interview = summary?.interview;
  const rec = summary?.recommendation;
  const firstName = user.name.split(" ")[0];

  return (
    <div className="gos-shell gos-shell-wide">
      <div>
        <div className="gos-eyebrow">Command center</div>
        <h1 className="gos-title">Welcome back, {firstName}</h1>
        <p className="gos-subtitle">
          {justSubmitted
            ? "Assessment logged. Your career path, roadmap, and prep modules are ready to run."
            : roadmap
              ? `Tracking ${roadmap.career_title}. Keep the circuit moving.`
              : "Live readout of your grind — assessment, roadmap, jobs, and interviews."}
        </p>
      </div>

      <Alert>{error}</Alert>

      <div className="dash-stats">
        <button className="dash-stat gos-panel" type="button" onClick={onGoRoadmap}>
          <span className="dash-stat-key">ROADMAP</span>
          <span className="dash-stat-val">{roadmap ? `${roadmap.progress_percent}%` : "—"}</span>
          <span className="dash-stat-sub">
            {roadmap ? `${roadmap.completed_items}/${roadmap.total_items} items` : "Not generated"}
          </span>
        </button>
        <button className="dash-stat gos-panel" type="button" onClick={onGoSkills}>
          <span className="dash-stat-key">SKILLS</span>
          <span className="dash-stat-val">{skills ? `${skills.average_percent}%` : "0%"}</span>
          <span className="dash-stat-sub">
            {skills ? `${skills.completed_skills}/${skills.total_skills} completed` : "None tracked"}
          </span>
        </button>
        <button className="dash-stat gos-panel" type="button" onClick={onGoJobs}>
          <span className="dash-stat-key">JOB PIPELINE</span>
          <span className="dash-stat-val">{jobs?.pipeline ?? 0}</span>
          <span className="dash-stat-sub">{jobs?.total ?? 0} tracked applications</span>
        </button>
        <button className="dash-stat gos-panel" type="button" onClick={onGoInterview}>
          <span className="dash-stat-key">INTERVIEW</span>
          <span className="dash-stat-val">{interview?.total ? `${interview.progress_percent}%` : "—"}</span>
          <span className="dash-stat-sub">
            {interview?.total ? `${interview.nailed}/${interview.total} nailed` : "Prep not generated"}
          </span>
        </button>
      </div>

      <div className="gos-grid-2">
        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> next.grind
          </div>
          {roadmap?.next_item ? (
            <>
              <div className="dash-next-phase">{roadmap.next_item.phase_title}</div>
              <h2 className="dash-next-title">{roadmap.next_item.title}</h2>
              <p className="gos-empty-note">
                Open the roadmap and click this item for how to learn it — channels, docs, and a practice project.
              </p>
              <button className="gos-btn gos-btn-primary" style={{ width: "auto" }} onClick={onGoRoadmap}>
                OPEN ROADMAP
              </button>
            </>
          ) : rec ? (
            <>
              <h2 className="dash-next-title">{summary.next_skill_to_learn || rec.next_skill_to_learn}</h2>
              <p className="gos-empty-note">Generate a roadmap to break this into a week-by-week path.</p>
              <button className="gos-btn gos-btn-primary" style={{ width: "auto" }} onClick={onGoRoadmap}>
                GENERATE ROADMAP
              </button>
            </>
          ) : (
            <>
              <p className="gos-empty-note">Take the assessment so GrindOS can pick your first move.</p>
              <button className="gos-btn gos-btn-primary" style={{ width: "auto" }} onClick={onGoAssessment}>
                START ASSESSMENT
              </button>
            </>
          )}
        </div>

        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> career.paths
          </div>
          {rec?.career_paths?.length ? (
            <>
              {rec.career_paths.slice(0, 3).map((career, i) => (
                <div className="dash-path-row" key={career.title}>
                  <span className="dash-path-idx">{String(i + 1).padStart(2, "0")}</span>
                  <div>
                    <div className="roadmap-item-title">{career.title}</div>
                    <div className="roadmap-item-desc">{career.example_roles?.slice(0, 2).join(" · ")}</div>
                  </div>
                </div>
              ))}
              <button className="gos-btn gos-btn-ghost" onClick={onViewAnalysis}>
                View full analysis →
              </button>
            </>
          ) : (
            <p className="gos-empty-note" style={{ marginBottom: 0 }}>
              No AI analysis yet. Complete the assessment to unlock career paths.
            </p>
          )}
        </div>
      </div>

      <div className="gos-grid-2">
        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> jobs.recent
          </div>
          {jobs?.recent?.length ? (
            <>
              {jobs.recent.map((job) => (
                <div className="terminal-row" key={job.id}>
                  <span className="terminal-row-key">
                    {job.company}
                    <span className="dash-job-role"> — {job.role}</span>
                  </span>
                  <span className={`job-chip job-chip-${job.status}`}>
                    {JOB_STATUS_LABEL[job.status] || job.status}
                  </span>
                </div>
              ))}
              <button className="gos-btn gos-btn-ghost" onClick={onGoJobs}>
                Open job tracker →
              </button>
            </>
          ) : (
            <>
              <p className="gos-empty-note">No applications yet. Track internships and roles as you apply.</p>
              <button className="gos-btn" onClick={onGoJobs}>
                ADD A JOB
              </button>
            </>
          )}
        </div>

        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> skills.circuit
          </div>
          <CircuitTrack percent={skills?.average_percent ?? 0} label="Average skill progress" />
          {skills?.next_skill && (
            <p className="gos-empty-note" style={{ marginTop: 14, marginBottom: 0 }}>
              Next skill in the queue: <strong>{skills.next_skill}</strong>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Roadmap — phase-based learning path with per-item status
   ============================================================ */

function GuideBody({ payload, loading, error }) {
  const guide = payload?.guide;

  return (
    <>
      <Alert>{error}</Alert>
      {loading && (
        <div className="gos-loading">
          <span className="gos-spinner" /> Building a learning brief…
        </div>
      )}
      {guide && (
        <>
          <p className="guide-summary">{guide.summary}</p>
          {guide.learn_this?.length > 0 && (
            <>
              <h3 className="guide-h">What to learn</h3>
              <ul className="guide-list">
                {guide.learn_this.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </>
          )}
          {guide.practice && (
            <>
              <h3 className="guide-h">How to practice</h3>
              <p className="guide-summary">{guide.practice}</p>
            </>
          )}
          {guide.youtube?.length > 0 && (
            <>
              <h3 className="guide-h">YouTube channels</h3>
              <div className="guide-cards">
                {guide.youtube.map((yt) => (
                  <a
                    key={`${yt.channel}-${yt.search_query}`}
                    className="guide-card"
                    href={youtubeSearch(yt.search_query || yt.channel)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="guide-card-name">{yt.channel}</div>
                    <div className="guide-card-why">{yt.focus}</div>
                    <div className="guide-card-cta">Search on YouTube →</div>
                  </a>
                ))}
              </div>
            </>
          )}
          {guide.resources?.length > 0 && (
            <>
              <h3 className="guide-h">Docs & sites</h3>
              <div className="guide-cards">
                {guide.resources.map((res) => (
                  <a
                    key={res.name}
                    className="guide-card"
                    href={res.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <div className="guide-card-name">{res.name}</div>
                    <div className="guide-card-why">{res.why}</div>
                  </a>
                ))}
              </div>
            </>
          )}
          {guide.project_idea && (
            <>
              <h3 className="guide-h">Project to lock it in</h3>
              <p className="guide-summary">{guide.project_idea}</p>
            </>
          )}
        </>
      )}
    </>
  );
}

/* ---------- ask-AI doubt chat, scoped to one roadmap item ---------- */

function RoadmapChat({ token, itemId }) {
  const [messages, setMessages] = useState(undefined); // undefined = loading
  const [error, setError] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setMessages(undefined);
    setError("");
    api
      .getRoadmapItemChat({ token, itemId })
      .then((data) => {
        if (!cancelled) setMessages(data.messages || []);
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, itemId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  const send = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || sending) return;
    setInput("");
    setError("");
    setSending(true);
    setMessages((m) => [...(m || []), { role: "user", content: question }]);
    try {
      const data = await api.askRoadmapItemDoubt({ token, itemId, question });
      setMessages(data.messages || []);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-scroll" ref={scrollRef}>
        {messages === undefined && (
          <div className="gos-loading">
            <span className="gos-spinner" /> Loading conversation…
          </div>
        )}
        {messages?.length === 0 && (
          <p className="gos-empty-note">
            Stuck on a concept, need a simpler explanation, or not sure where to start? Ask here.
          </p>
        )}
        {messages?.map((m, i) => (
          <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
            <span className="chat-bubble-role">{m.role === "user" ? "YOU" : "MENTOR"}</span>
            <p>{m.content}</p>
          </div>
        ))}
        {sending && (
          <div className="chat-bubble chat-bubble-assistant chat-bubble-pending">
            <span className="chat-bubble-role">MENTOR</span>
            <p>thinking…</p>
          </div>
        )}
      </div>
      <Alert>{error}</Alert>
      <form className="chat-input-row" onSubmit={send}>
        <input
          className="gos-input"
          placeholder="Ask a doubt about this topic…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button
          className="gos-btn gos-btn-primary chat-send-btn"
          type="submit"
          disabled={sending || !input.trim()}
        >
          {sending ? "…" : "ASK"}
        </button>
      </form>
    </div>
  );
}

/* ---------- side workspace: guide + chat, tabbed, for one node ---------- */

function RoadmapSidePanel({ item, token, guidePayload, guideLoading, guideError, updating, onStatusChange, onClose }) {
  const [tab, setTab] = useState("guide");

  useEffect(() => {
    setTab("guide");
  }, [item.id]);

  return (
    <div className="gos-panel terminal-panel side-panel">
      <div className="terminal-head">
        <span className="terminal-dot" /> item.workspace
        <button className="gos-btn gos-btn-ghost guide-close" type="button" onClick={onClose}>
          CLOSE
        </button>
      </div>
      <h2 className="guide-title">{item.title}</h2>
      {item.phase_title && <div className="dash-next-phase">{item.phase_title}</div>}
      <StageRail status={item.status} disabled={updating} onChange={onStatusChange} />

      <div className="filter-row side-tabs">
        <button
          type="button"
          className={`filter-chip ${tab === "guide" ? "active" : ""}`}
          onClick={() => setTab("guide")}
        >
          GUIDE
        </button>
        <button
          type="button"
          className={`filter-chip ${tab === "chat" ? "active" : ""}`}
          onClick={() => setTab("chat")}
        >
          ASK AI
        </button>
      </div>

      {tab === "guide" ? (
        <GuideBody payload={guidePayload} loading={guideLoading} error={guideError} />
      ) : (
        <RoadmapChat token={token} itemId={item.id} />
      )}
    </div>
  );
}

function RoadmapView({ hasRecommendation, onSkillsSynced, initialCareerTitle, onCareerTitleConsumed }) {
  const { token } = useAuth();
  const [roadmap, setRoadmap] = useState(undefined); // undefined = loading, null = none yet
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);
  const [openItem, setOpenItem] = useState(null);
  const [guidePayload, setGuidePayload] = useState(null);
  const [guideLoading, setGuideLoading] = useState(false);
  const [guideError, setGuideError] = useState("");

  const load = () => {
    api
      .getRoadmap(token)
      .then((data) => setRoadmap(data && data.phases ? data : null))
      .catch((err) => setError(errorMessage(err)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const generate = async (regenerate, careerTitleOverride) => {
    if (
      regenerate &&
      !window.confirm(
        "Regenerate your roadmap? This rebuilds every phase from scratch — current item progress on this roadmap will be lost."
      )
    ) {
      return;
    }
    setGenerating(true);
    setError("");
    try {
      const data = await api.generateRoadmap({
        token,
        regenerate,
        careerTitle: careerTitleOverride || undefined,
      });
      setRoadmap(data);
      setOpenItem(null);
      setGuidePayload(null);
      onSkillsSynced?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  // A path chosen from the results screen either builds a fresh roadmap
  // (none exists yet) or, if a roadmap for a different path already
  // exists, regenerates it for the newly chosen path.
  useEffect(() => {
    if (roadmap === undefined) return; // still loading
    if (!initialCareerTitle) return;
    if (roadmap && roadmap.career_title === initialCareerTitle) {
      onCareerTitleConsumed?.();
      return;
    }
    generate(!!roadmap, initialCareerTitle);
    onCareerTitleConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roadmap, initialCareerTitle]);

  const setItemStatus = async (itemId, status) => {
    setUpdatingId(itemId);
    setRoadmap((r) =>
      r
        ? {
            ...r,
            phases: r.phases.map((p) => ({
              ...p,
              items: p.items.map((it) => (it.id === itemId ? { ...it, status } : it)),
            })),
          }
        : r
    );
    try {
      await api.updateRoadmapItemStatus({ token, itemId, status });
      load(); // resync progress_percent from the server
      onSkillsSynced?.();
    } catch (err) {
      setError(errorMessage(err));
      load();
    } finally {
      setUpdatingId(null);
    }
  };

  const openGuide = async (item) => {
    if (openItem?.id === item.id) {
      setOpenItem(null);
      return;
    }
    setOpenItem(item);
    setGuideError("");
    setGuidePayload(null);
    setGuideLoading(true);
    try {
      const data = await api.getRoadmapItemGuide({ token, itemId: item.id });
      setGuidePayload(data);
    } catch (err) {
      setGuideError(errorMessage(err));
    } finally {
      setGuideLoading(false);
    }
  };

  if (roadmap === undefined) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading roadmap…
      </div>
    );
  }

  if (!roadmap) {
    if (generating) {
      return (
        <div className="gos-loading">
          <span className="gos-spinner" /> Building your roadmap…
        </div>
      );
    }

    return (
      <div className="gos-shell">
        <div>
          <div className="gos-eyebrow">Learning path</div>
          <h1 className="gos-title">No roadmap yet</h1>
          <p className="gos-subtitle">
            {hasRecommendation
              ? "Generate a phase-by-phase roadmap built from your AI career analysis."
              : "Complete the assessment first — your roadmap is built from your AI career analysis."}
          </p>
        </div>

        <Alert>{error}</Alert>

        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> roadmap.generate
          </div>
          <p className="gos-empty-note" style={{ marginBottom: 18 }}>
            {hasRecommendation
              ? "This builds an ordered set of phases from foundational to job-ready, ending in a project/portfolio phase — matched to your weekly study time and career goal."
              : "Head to the dashboard, run the assessment, and come back once your AI analysis is ready."}
          </p>
          <button
            className="gos-btn gos-btn-primary"
            style={{ width: "auto" }}
            disabled={!hasRecommendation || generating}
            onClick={() => generate(false)}
          >
            {generating ? "BUILDING…" : "GENERATE ROADMAP"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="gos-shell gos-shell-flow">
      <div>
        <div className="gos-eyebrow">Learning path</div>
        <h1 className="gos-title">{roadmap.career_title}</h1>
        <p className="gos-subtitle">
          Click a node to open it — how to learn it, resources, and an AI mentor for doubts.
          Track progress from the side panel.
        </p>
      </div>

      <Alert>{error}</Alert>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> roadmap.progress
        </div>
        <CircuitTrack percent={roadmap.progress_percent} />
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button className="gos-btn gos-btn-ghost" onClick={() => generate(true, roadmap.career_title)} disabled={generating}>
            {generating ? "REBUILDING…" : "REGENERATE ROADMAP"}
          </button>
        </div>
      </div>

      <div className="flow-layout">
        <div className="gos-panel terminal-panel flow-canvas-wrap">
          <div className="terminal-head">
            <span className="terminal-dot" /> roadmap.flow
          </div>
          <div className="flow-canvas">
            {roadmap.phases.map((phase) => (
              <div className="flow-phase" key={phase.phase_number}>
                <div className="flow-phase-marker">
                  <span className="flow-phase-num">
                    PHASE {String(phase.phase_number).padStart(2, "0")}
                  </span>
                  <span className="flow-phase-title">{phase.phase_title}</span>
                </div>
                {phase.items.map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    className={`flow-node status-${item.status} ${
                      openItem?.id === item.id ? "is-active" : ""
                    }`}
                    onClick={() => openGuide({ ...item, phase_title: phase.phase_title })}
                  >
                    <span className="flow-node-title">{item.title}</span>
                    <span className={`flow-node-status stage-label-${item.status}`}>
                      {STAGE_LABEL[item.status] || item.status}
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="flow-side">
          {openItem ? (
            <RoadmapSidePanel
              item={openItem}
              token={token}
              guidePayload={guidePayload}
              guideLoading={guideLoading}
              guideError={guideError}
              updating={updatingId === openItem.id}
              onStatusChange={(status) => setItemStatus(openItem.id, status)}
              onClose={() => setOpenItem(null)}
            />
          ) : (
            <div className="gos-panel terminal-panel flow-side-empty">
              <div className="terminal-head">
                <span className="terminal-dot" /> item.workspace
              </div>
              <p className="gos-empty-note">
                Select a node on the left to see how to learn it, track progress, or ask the AI
                mentor a doubt.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Skills — dashboard summary + full tracked list + manual add
   ============================================================ */

function SkillsView({ refreshKey }) {
  const { token } = useAuth();
  const [skills, setSkills] = useState(undefined); // undefined = loading
  const [dash, setDash] = useState(null);
  const [error, setError] = useState("");
  const [newSkill, setNewSkill] = useState("");
  const [adding, setAdding] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [filter, setFilter] = useState("all"); // all | in_progress | completed

  const load = () => {
    Promise.all([api.listSkills(token), api.getSkillsDashboard(token)])
      .then(([list, dashboard]) => {
        setSkills(list);
        setDash(dashboard);
      })
      .catch((err) => setError(errorMessage(err)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const addSkill = async (e) => {
    e.preventDefault();
    if (!newSkill.trim()) return;
    setAdding(true);
    setError("");
    try {
      await api.addSkill({ token, name: newSkill.trim() });
      setNewSkill("");
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  };

  const setSkillStatus = async (skillId, status) => {
    setUpdatingId(skillId);
    setSkills((list) => list.map((s) => (s.id === skillId ? { ...s, status } : s)));
    try {
      await api.updateSkillStatus({ token, skillId, status });
      load();
    } catch (err) {
      setError(errorMessage(err));
      load();
    } finally {
      setUpdatingId(null);
    }
  };

  const removeSkill = async (skillId) => {
    setDeletingId(skillId);
    setError("");
    try {
      await api.deleteSkill({ token, skillId });
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setDeletingId(null);
    }
  };

  if (skills === undefined) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading skills…
      </div>
    );
  }

  const matchesFilter = (s) => {
    if (filter === "completed") return s.status === "completed";
    if (filter === "in_progress") return s.status === "learning" || s.status === "practicing";
    return true;
  };

  const visible = skills.filter(matchesFilter);

  const roadmapSkills = visible.filter((s) => s.source === "roadmap");
  const manualSkills = visible.filter((s) => s.source === "manual");

  // group roadmap skills by phase, keeping phases in first-seen order
  const phaseOrder = [];
  const roadmapByPhase = {};
  roadmapSkills.forEach((s) => {
    const key = s.phase_title || "Other";
    if (!roadmapByPhase[key]) {
      roadmapByPhase[key] = [];
      phaseOrder.push(key);
    }
    roadmapByPhase[key].push(s);
  });

  const inProgress = (dash?.by_status?.learning ?? 0) + (dash?.by_status?.practicing ?? 0);

  const renderRow = (s) => (
    <div className="roadmap-row" key={s.id}>
      <span className="roadmap-row-title">{s.name}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <StageRail
          status={s.status}
          disabled={updatingId === s.id}
          onChange={(status) => setSkillStatus(s.id, status)}
        />
        {s.source === "manual" && (
          <button
            type="button"
            className="gos-btn gos-btn-ghost"
            disabled={deletingId === s.id}
            onClick={() => removeSkill(s.id)}
          >
            {deletingId === s.id ? "…" : "REMOVE"}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="gos-shell">
      <div>
        <div className="gos-eyebrow">Skill tracker</div>
        <h1 className="gos-title">Skills</h1>
        <p className="gos-subtitle">
          Roadmap items land here automatically, grouped by phase. Add anything else you're
          picking up on your own below.
        </p>
      </div>

      <Alert>{error}</Alert>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> skills.summary
        </div>
        <CircuitTrack percent={dash?.average_percent ?? 0} />
        <div className="stat-inline-row">
          <div className="stat-inline">
            <span className="stat-inline-val">{dash?.total_skills ?? 0}</span>
            <span className="stat-inline-key">TRACKED</span>
          </div>
          <div className="stat-inline">
            <span className="stat-inline-val">{inProgress}</span>
            <span className="stat-inline-key">IN PROGRESS</span>
          </div>
          <div className="stat-inline">
            <span className="stat-inline-val">{dash?.completed_skills ?? 0}</span>
            <span className="stat-inline-key">COMPLETED</span>
          </div>
        </div>
      </div>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> add_skill
        </div>
        <form className="skill-add-form" onSubmit={addSkill}>
          <input
            className="gos-input"
            placeholder="e.g. Docker, System Design, DSA…"
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
          />
          <button className="gos-btn gos-btn-primary" style={{ width: "auto" }} disabled={adding || !newSkill.trim()}>
            {adding ? "ADDING…" : "ADD"}
          </button>
        </form>
      </div>

      {skills.length > 0 && (
        <div className="gos-nav-links" style={{ marginBottom: 4 }}>
          {[
            { key: "all", label: "ALL" },
            { key: "in_progress", label: "IN PROGRESS" },
            { key: "completed", label: "COMPLETED" },
          ].map((f) => (
            <button
              key={f.key}
              type="button"
              className={`gos-nav-btn ${filter === f.key ? "active" : ""}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {skills.length === 0 ? (
        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> skills.list
          </div>
          <p className="gos-empty-note" style={{ marginBottom: 0 }}>
            No skills yet — generate a roadmap for an AI-built list, or add one above.
          </p>
        </div>
      ) : (
        <>
          <div className="gos-panel terminal-panel">
            <div className="terminal-head">
              <span className="terminal-dot" /> skills.from_roadmap
            </div>
            {phaseOrder.length === 0 ? (
              <p className="gos-empty-note" style={{ marginBottom: 0 }}>
                {roadmapSkills.length === 0 && manualSkills.length > 0
                  ? "No roadmap skills match this filter."
                  : "Generate a roadmap to auto-populate this section, phase by phase."}
              </p>
            ) : (
              phaseOrder.map((phaseTitle) => (
                <div key={phaseTitle} style={{ marginBottom: 18 }}>
                  <div className="flow-phase-marker" style={{ marginBottom: 8 }}>
                    <span className="flow-phase-title">{phaseTitle}</span>
                  </div>
                  {roadmapByPhase[phaseTitle].map(renderRow)}
                </div>
              ))
            )}
          </div>

          <div className="gos-panel terminal-panel">
            <div className="terminal-head">
              <span className="terminal-dot" /> skills.self_added
            </div>
            {manualSkills.length === 0 ? (
              <p className="gos-empty-note" style={{ marginBottom: 0 }}>
                {skills.some((s) => s.source === "manual")
                  ? "No self-added skills match this filter."
                  : "Nothing here yet — anything you add above (outside the roadmap) shows up in this section."}
              </p>
            ) : (
              manualSkills.map(renderRow)
            )}
          </div>
        </>
      )}
    </div>
  );
}

/* ============================================================
   Jobs — application tracker
   ============================================================ */

function JobsView({ onChanged }) {
  const { token } = useAuth();
  const [jobs, setJobs] = useState(undefined);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    company: "",
    role: "",
    location: "",
    source: "",
    url: "",
    status: "wishlist",
    notes: "",
  });

  const load = () => {
    api
      .listJobs(token)
      .then(setJobs)
      .catch((err) => setError(errorMessage(err)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const update = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createJob({ token, ...form });
      setForm({
        company: "",
        role: "",
        location: "",
        source: "",
        url: "",
        status: "wishlist",
        notes: "",
      });
      load();
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (jobId, status) => {
    setJobs((list) => list.map((j) => (j.id === jobId ? { ...j, status } : j)));
    try {
      await api.updateJob({ token, jobId, status });
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
      load();
    }
  };

  const remove = async (jobId) => {
    if (!window.confirm("Remove this application from the tracker?")) return;
    try {
      await api.deleteJob({ token, jobId });
      setJobs((list) => list.filter((j) => j.id !== jobId));
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (jobs === undefined) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading jobs…
      </div>
    );
  }

  const counts = JOB_STATUSES.reduce((acc, s) => {
    acc[s] = jobs.filter((j) => j.status === s).length;
    return acc;
  }, {});
  const visible = filter === "all" ? jobs : jobs.filter((j) => j.status === filter);

  return (
    <div className="gos-shell gos-shell-wide">
      <div>
        <div className="gos-eyebrow">Pipeline</div>
        <h1 className="gos-title">Job tracker</h1>
        <p className="gos-subtitle">
          Wishlist internships and roles, then walk them through OA → interview → offer.
        </p>
      </div>

      <Alert>{error}</Alert>

      <div className="filter-row">
        <button
          type="button"
          className={`filter-chip ${filter === "all" ? "active" : ""}`}
          onClick={() => setFilter("all")}
        >
          ALL {jobs.length}
        </button>
        {JOB_STATUSES.map((s) => (
          <button
            type="button"
            key={s}
            className={`filter-chip ${filter === s ? "active" : ""}`}
            onClick={() => setFilter(s)}
          >
            {JOB_STATUS_LABEL[s]} {counts[s]}
          </button>
        ))}
      </div>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> add.application
        </div>
        <form className="job-form" onSubmit={submit}>
          <input className="gos-input" placeholder="Company" value={form.company} onChange={update("company")} required />
          <input className="gos-input" placeholder="Role" value={form.role} onChange={update("role")} required />
          <input className="gos-input" placeholder="Location / Remote" value={form.location} onChange={update("location")} />
          <input className="gos-input" placeholder="Source (LinkedIn, Naukri…)" value={form.source} onChange={update("source")} />
          <input className="gos-input" placeholder="Posting URL" value={form.url} onChange={update("url")} />
          <select className="gos-input" value={form.status} onChange={update("status")}>
            {JOB_STATUSES.map((s) => (
              <option key={s} value={s}>
                {JOB_STATUS_LABEL[s]}
              </option>
            ))}
          </select>
          <input className="gos-input job-notes" placeholder="Notes" value={form.notes} onChange={update("notes")} />
          <button className="gos-btn gos-btn-primary" style={{ width: "auto" }} disabled={saving}>
            {saving ? "ADDING…" : "ADD"}
          </button>
        </form>
      </div>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> applications.list
        </div>
        {visible.length === 0 ? (
          <p className="gos-empty-note" style={{ marginBottom: 0 }}>
            Nothing in this column yet.
          </p>
        ) : (
          visible.map((job) => (
            <div className="job-row" key={job.id}>
              <div className="job-row-main">
                <div className="roadmap-item-title">
                  {job.company} <span className="dash-job-role">— {job.role}</span>
                </div>
                <div className="roadmap-item-desc">
                  {[job.location, job.source].filter(Boolean).join(" · ")}
                  {job.url && (
                    <>
                      {" · "}
                      <a href={job.url} target="_blank" rel="noreferrer">
                        posting
                      </a>
                    </>
                  )}
                  {job.notes ? ` · ${job.notes}` : ""}
                </div>
              </div>
              <select
                className="gos-input job-status-select"
                value={job.status}
                onChange={(e) => setStatus(job.id, e.target.value)}
              >
                {JOB_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {JOB_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
              <button type="button" className="gos-btn gos-btn-ghost" onClick={() => remove(job.id)}>
                REMOVE
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ============================================================
   Interview prep — question bank from the target career
   ============================================================ */

const INTERVIEW_CAT_LABEL = {
  dsa: "DSA",
  system_design: "SYSTEM DESIGN",
  domain: "DOMAIN",
  behavioral: "BEHAVIORAL",
  hr: "HR",
};

function InterviewView({ hasRecommendation, onChanged }) {
  const { token } = useAuth();
  const [prep, setPrep] = useState(undefined);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [category, setCategory] = useState("all");
  const [openId, setOpenId] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);

  const load = () => {
    api
      .getInterview(token)
      .then((data) => setPrep(data && data.questions ? data : null))
      .catch((err) => setError(errorMessage(err)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const generate = async (regenerate) => {
    if (
      regenerate &&
      !window.confirm("Regenerate interview prep? Your nailed / practicing marks will reset.")
    ) {
      return;
    }
    setGenerating(true);
    setError("");
    try {
      const data = await api.generateInterview({ token, regenerate });
      setPrep(data);
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGenerating(false);
    }
  };

  const setStatus = async (questionId, status) => {
    setUpdatingId(questionId);
    setPrep((p) =>
      p
        ? {
            ...p,
            questions: p.questions.map((q) => (q.id === questionId ? { ...q, status } : q)),
          }
        : p
    );
    try {
      await api.updateInterviewStatus({ token, questionId, status });
      load();
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
      load();
    } finally {
      setUpdatingId(null);
    }
  };

  if (prep === undefined) {
    return (
      <div className="gos-loading">
        <span className="gos-spinner" /> Loading interview prep…
      </div>
    );
  }

  if (!prep) {
    return (
      <div className="gos-shell">
        <div>
          <div className="gos-eyebrow">Interview lab</div>
          <h1 className="gos-title">No prep set yet</h1>
          <p className="gos-subtitle">
            {hasRecommendation
              ? "Generate a question bank matched to your target career — DSA, system design, role, behavioral, HR."
              : "Complete the assessment first so questions match your career path."}
          </p>
        </div>
        <Alert>{error}</Alert>
        <div className="gos-panel terminal-panel">
          <button
            className="gos-btn gos-btn-primary"
            style={{ width: "auto" }}
            disabled={!hasRecommendation || generating}
            onClick={() => generate(false)}
          >
            {generating ? "BUILDING…" : "GENERATE INTERVIEW PREP"}
          </button>
        </div>
      </div>
    );
  }

  const questions = category === "all" ? prep.questions : prep.questions.filter((q) => q.category === category);
  const cats = ["all", ...Object.keys(INTERVIEW_CAT_LABEL)];

  return (
    <div className="gos-shell gos-shell-wide">
      <div>
        <div className="gos-eyebrow">Interview lab</div>
        <h1 className="gos-title">{prep.career_title || "Interview prep"}</h1>
        <p className="gos-subtitle">
          Work the bank out loud. Open a question for hints and talking points, then mark it nailed when it's clean.
        </p>
      </div>

      <Alert>{error}</Alert>

      <div className="gos-panel terminal-panel">
        <div className="terminal-head">
          <span className="terminal-dot" /> prep.progress
        </div>
        <CircuitTrack percent={prep.progress_percent} />
        <div className="stat-inline-row">
          <div className="stat-inline">
            <span className="stat-inline-val">{prep.total}</span>
            <span className="stat-inline-key">QUESTIONS</span>
          </div>
          <div className="stat-inline">
            <span className="stat-inline-val">{prep.practicing}</span>
            <span className="stat-inline-key">IN PLAY</span>
          </div>
          <div className="stat-inline">
            <span className="stat-inline-val">{prep.nailed}</span>
            <span className="stat-inline-key">NAILED</span>
          </div>
        </div>
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <button className="gos-btn gos-btn-ghost" onClick={() => generate(true)} disabled={generating}>
            {generating ? "REBUILDING…" : "REGENERATE PREP"}
          </button>
        </div>
      </div>

      <div className="filter-row">
        {cats.map((c) => (
          <button
            type="button"
            key={c}
            className={`filter-chip ${category === c ? "active" : ""}`}
            onClick={() => setCategory(c)}
          >
            {c === "all" ? "ALL" : INTERVIEW_CAT_LABEL[c]}
          </button>
        ))}
      </div>

      {questions.map((q) => {
        const open = openId === q.id;
        return (
          <div className={`gos-panel terminal-panel interview-q ${open ? "is-open" : ""}`} key={q.id}>
            <button type="button" className="interview-q-head" onClick={() => setOpenId(open ? null : q.id)}>
              <span className="interview-cat">{INTERVIEW_CAT_LABEL[q.category] || q.category}</span>
              <span className="interview-prompt">{q.prompt}</span>
            </button>
            <div className="interview-status-row">
              {["not_started", "practicing", "nailed"].map((st) => (
                <button
                  type="button"
                  key={st}
                  className={`filter-chip ${q.status === st ? "active" : ""}`}
                  disabled={updatingId === q.id}
                  onClick={() => setStatus(q.id, st)}
                >
                  {INTERVIEW_STAGE_LABEL[st]}
                </button>
              ))}
            </div>
            {open && (
              <div className="interview-body">
                {q.hint && (
                  <>
                    <h3 className="guide-h">Hint</h3>
                    <p className="guide-summary">{q.hint}</p>
                  </>
                )}
                {q.talking_points?.length > 0 && (
                  <>
                    <h3 className="guide-h">Talking points</h3>
                    <ul className="guide-list">
                      {q.talking_points.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ============================================================
   Root shell — routes between auth / assessment / dashboard /
   roadmap / skills / jobs / interview
   ============================================================ */

function Shell() {
  const { token, user, loading } = useAuth();
  const [view, setView] = useState("dashboard");
  const [justSubmitted, setJustSubmitted] = useState(false);
  const [recommendation, setRecommendation] = useState(null);
  const [chosenCareerTitle, setChosenCareerTitle] = useState(null);
  const [skillsRefreshKey, setSkillsRefreshKey] = useState(0);
  const [dashRefreshKey, setDashRefreshKey] = useState(0);

  const bumpDash = () => setDashRefreshKey((k) => k + 1);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api
      .getRecommendation(token)
      .then((data) => {
        if (cancelled) return;
        if (data && data.career_paths) setRecommendation(data);
      })
      .catch(() => {
        /* no saved recommendation yet */
      });
    return () => {
      cancelled = true;
    };
  }, [user, token]);

  if (loading) {
    return (
      <div className="gos-main">
        <div className="gos-loading">
          <span className="gos-spinner" /> Booting GrindOS…
        </div>
      </div>
    );
  }

  return (
    <div className="gos-app">
      <Navbar view={view} setView={setView} hasRecommendation={!!recommendation} />
      <div className="gos-main">
        {!token || !user ? (
          <AuthScreen />
        ) : view === "assessment" ? (
          <Assessment
            onDone={(result) => {
              setRecommendation(result);
              setJustSubmitted(true);
              setView("results");
              bumpDash();
            }}
          />
        ) : view === "results" ? (
          <RecommendationResult
            result={recommendation}
            onRetake={() => setView("assessment")}
            onChoosePath={(title) => {
              setChosenCareerTitle(title);
              setView("roadmap");
            }}
            onResultUpdated={(data) => setRecommendation(data)}
          />
        ) : view === "roadmap" ? (
          <RoadmapView
            hasRecommendation={!!recommendation}
            initialCareerTitle={chosenCareerTitle}
            onCareerTitleConsumed={() => setChosenCareerTitle(null)}
            onSkillsSynced={() => {
              setSkillsRefreshKey((k) => k + 1);
              bumpDash();
            }}
          />
        ) : view === "skills" ? (
          <SkillsView refreshKey={skillsRefreshKey} />
        ) : view === "jobs" ? (
          <JobsView onChanged={bumpDash} />
        ) : view === "interview" ? (
          <InterviewView hasRecommendation={!!recommendation} onChanged={bumpDash} />
        ) : (
          <Dashboard
            justSubmitted={justSubmitted}
            refreshKey={dashRefreshKey}
            onViewAnalysis={() => setView("results")}
            onGoRoadmap={() => setView("roadmap")}
            onGoJobs={() => setView("jobs")}
            onGoInterview={() => setView("interview")}
            onGoSkills={() => setView("skills")}
            onGoAssessment={() => setView("assessment")}
          />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}