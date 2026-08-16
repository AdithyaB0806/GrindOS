import { createContext, useContext, useEffect, useState } from "react";
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
      GRINDOS <small>v0.1 — career OS</small>
    </div>
  );
}

function Navbar({ view, setView }) {
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
            className={`gos-nav-btn ${view === "assessment" ? "active" : ""}`}
            onClick={() => setView("assessment")}
          >
            ASSESSMENT
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
  const { token, user } = useAuth();
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

await api.submitAssessment({
  userId: user.id,
  answers: finalAnswers,
  token,
});

const recommendation = await api.generateRecommendation(token);

onDone(recommendation);
      
      onDone();
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
        className={`assess-option ${
          selected === opt ? "selected" : ""
        }`}
        onClick={() => choose(opt)}
      >
        <span className="assess-option-key">
          {String.fromCharCode(65 + i)}
        </span>

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
            (selected === "Other" &&
            !otherAnswers[q.key]?.trim())
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
function RecommendationResult({ result }) {
  if (!result) return null;

  return (
    <div className="gos-shell">
      <div className="gos-eyebrow">AI ANALYSIS COMPLETE</div>

      <h1 className="gos-title">
        Your Career Profile
      </h1>

      <p className="gos-subtitle">
        GrindOS analyzed your assessment answers.
      </p>

      {result.career_paths?.map((career, index) => (
        <div className="gos-panel" key={career.title}>
          <div className="terminal-head">
            <span className="terminal-dot" />
            CAREER_{index + 1}
          </div>

          <h2>{career.title}</h2>

          <p>{career.fit_reason}</p>

          <h3>Matching Skills</h3>
          <ul>
            {career.matching_skills?.map((skill) => (
              <li key={skill}>{skill}</li>
            ))}
          </ul>

          <h3>Skill Gaps</h3>
          <ul>
            {career.skill_gaps?.map((gap) => (
              <li key={gap}>{gap}</li>
            ))}
          </ul>

          <h3>Example Roles</h3>
          <ul>
            {career.example_roles?.map((role) => (
              <li key={role}>{role}</li>
            ))}
          </ul>
        </div>
      ))}

      <div className="gos-panel">
        <div className="terminal-head">
          <span className="terminal-dot" />
          NEXT_SKILL
        </div>

        <h2>{result.next_skill_to_learn}</h2>
      </div>
    </div>
  );
}

function Dashboard({ justSubmitted }) {
  const { user } = useAuth();

  return (
    <div className="gos-shell">
      <div>
        <div className="gos-eyebrow">System status</div>
        <h1 className="gos-title">Welcome back, {user.name.split(" ")[0]}</h1>
        <p className="gos-subtitle">
          {justSubmitted
            ? "Assessment logged. Your roadmap builds on these answers as more modules come online."
            : "Here's where your GrindOS profile stands right now."}
        </p>
      </div>

      <div className="gos-grid-2">
        <div className="gos-panel terminal-panel">
          <div className="terminal-head">
            <span className="terminal-dot" /> profile.json
          </div>
          <div className="terminal-row">
            <span className="terminal-row-key">id</span>
            <span className="terminal-row-val">{user.id}</span>
          </div>
          <div className="terminal-row">
            <span className="terminal-row-key">name</span>
            <span className="terminal-row-val">{user.name}</span>
          </div>
          <div className="terminal-row">
            <span className="terminal-row-key">email</span>
            <span className="terminal-row-val">{user.email}</span>
          </div>
          <div className="terminal-row">
            <span className="terminal-row-key">status</span>
            <span className="terminal-row-val">
              active
              <span className="terminal-cursor" />
            </span>
          </div>
        </div>

        <div className="gos-panel roadmap-card">
          <div className="terminal-head">
            <span className="terminal-dot" /> roadmap.modules
          </div>
          <div className="roadmap-item">
            <span className="roadmap-item-status live">LIVE</span>
            <div>
              <div className="roadmap-item-title">Skill assessment</div>
              <div className="roadmap-item-desc">
                Baseline read on interests, strengths, and target roles.
              </div>
            </div>
          </div>
          <div className="roadmap-item">
            <span className="roadmap-item-status">SOON</span>
            <div>
              <div className="roadmap-item-title">AI-generated roadmap</div>
              <div className="roadmap-item-desc">
                Personalized learning path from your assessment answers.
              </div>
            </div>
          </div>
          <div className="roadmap-item">
            <span className="roadmap-item-status">SOON</span>
            <div>
              <div className="roadmap-item-title">Project & interview prep</div>
              <div className="roadmap-item-desc">
                Portfolio recommendations and mock interviews.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   Root shell — routes between auth / assessment / dashboard
   ============================================================ */

function Shell() {
  const { token, user, loading } = useAuth();
  const [view, setView] = useState("dashboard");
  const [justSubmitted, setJustSubmitted] = useState(false);
  const [recommendation, setRecommendation] = useState(null);

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
      <Navbar view={view} setView={setView} />
      <div className="gos-main">
        {!token || !user ? (
          <AuthScreen />
        ) : view === "assessment" ? (
          <Assessment
            onDone={(result) => {
              setRecommendation(result);
              setJustSubmitted(true);
              setView("results");
            }}
          />
        ) : view === "results" ? (
          <RecommendationResult result={recommendation} />
        ) : (
          <Dashboard justSubmitted={justSubmitted} />
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
