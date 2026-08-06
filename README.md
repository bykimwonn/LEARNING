# BT LEARNING — Production-Ready Web App
### Owned by Bongani Tshuma

A full-stack web app (Flask + **PostgreSQL** via SQLAlchemy, with an automatic SQLite fallback
for local/preview) implementing the **BT LEARNING** plan. The "AI" is a rule-based engine
written in code — no API key needed.

> 🚀 **This is the launch build.** There are **no demo accounts and no pre-seeded data**.
> On first start the database is empty except for the admin you configure. See
> **[DEPLOYMENT.md](DEPLOYMENT.md)** to put it live on Render with a managed PostgreSQL DB.

## ▶️ Deploy to Render (online, always-on, persistent data)

The repo includes `render.yaml`, a `Procfile`, `requirements.txt` and `runtime.txt`.
Follow **[DEPLOYMENT.md](DEPLOYMENT.md)**: push to GitHub → New → Blueprint → set `ADMIN_EMAIL`
/ `ADMIN_PASSWORD` to create your first admin.

---

## 🔑 Launch access model (no demo accounts)

There are **no seeded demo accounts**. Access flows through the admin:

- **Admin** — created on first boot from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars. Logs in at
  `/login/staff`.
- **Teachers** — created by the Admin in the Admin Panel (email + temp password), log in at
  `/login/staff`.
- **School students** — added by the Admin via **CSV roster upload** (temp password `btlearn123`,
  forced change on first login). Log in with their Student ID.
- **Independent learners** — self-register through the 5-stage onboarding wizard.

> **School students' temporary password is `btlearn123`**; they're **forced to create a private
> password on first entry**.

---

## 🧭 How the phases map to the app

**Phase 1 — Architecture.** Four roles with permissions enforced via route guards:
`admin`, `teacher`, `school_student`, `independent`. DB holds users, curriculum
(Notes + Past Exams categories), and analytics (attempts, weaknesses).

**Phase 2 — Portals & Auth.** Splash screen → **School Affiliated** vs **Independent Learner**.
School students validate a pre-loaded Student ID and are redirected to set a private password.
Admin panel uploads student rosters (CSV) and creates classes/teachers. Teacher panel uploads
notes/past papers.

**Phase 3 — Ingestion.** Uploaded text/PDF is split into **concept chunks** and indexed so the
AI tutor answers **only from the uploaded notes** (`ai_engine.chunk_content`). Auto-generated
knowledge checks draw their answers and options purely from the notes' own vocabulary.

**Phase 4 — Learning Experience.**
- **Timetable gatekeeper:** outside the student's study window, the app shows a friendly "not
  study time yet" message with their window (plus a demo override button).
- **Staged AI tutor:** teaches Concept 1, runs a knowledge check; you must pass to unlock
  Concept 2. Greets the student with a Shona/English blended greeting.
- **Personalized explanations:** analogies built from the student's listed interests (soccer,
  music, gaming, reading…) blended with Shona.

**Phase 5 — Analytics & Gamification.**
- **Weakness detection:** repeated failures on a concept flag a weakness and, for school
  students, automatically appear on the **Teacher's dashboard** for follow-up.
- **ELO rankings:** first-try passes, study streaks and mastering concepts raise your rating.
  Leaderboard at `/ranking`; diagnostic report per subject.

**Phase 6 — Deployment/verification.** `test_flow.py` runs the full simulation as Admin,
Teacher, and Student (roster load, note upload, weakness alerts, AI staying inside notes).

---

## 🧑‍🏫 Teacher Command Center (dashboard blueprint)

A dedicated teacher dashboard replaces the simple upload page. Log in as a teacher
(an account created by the Admin) to see it.

**1. Global Navigation Bar** — static top bar with BT LEARNING branding, an **Active Class
dropdown** (toggle between "Form 2A · Mathematics", "Form 2A · Biology", "Form 3 Geography ·
Geography"), a persistent **Quick Upload** popover, and a **Notification Bell** showing the
count of urgent AI weakness alerts.

**2. Command Center (home)** — per-class **Class Health Score** (% retention from AI test
results), an **Action Required** panel of AI-flagged critical issues, and the class
**Leaderboard** with "Board 1" status for the top 3.

**3. Curriculum Hub** — two tabs:
- **Notes Category:** drag-and-drop upload zone, **Processing → Active** status indicators,
  and a library table with enable/disable/delete toggles.
- **Exams Category:** dedicated past-paper uploads tagged for **Exam Simulation**.

**4. AI Intervention & Weakness Reports** — a **searchable student roster** with green /
yellow / red status. Clicking a student opens a granular report: **The Roadblock** (the failing
concept), an **Attempt Counter**, the **AI Transcript**, and the **Language & Analogy Log**
(showing whether the AI pivoted to Shona / used a specific analogy), plus a **Mark as Resolved**
button that resets AI tracking.

**5. Settings & Roster Management** — view students assigned by the School Admin and one-click
**password resets** (resets to `btlearn123`, forcing a change on next login).

> Tip: switch the class dropdown to **Form 3 Geography** to see a second class's data.

---

## 🎓 Student Staged Learning Interface (the core engine)

The student learning screen (`/learn/<subject>`) is a focused, interactive workspace rather than
a static page. Log in as a school student (an account added via roster) and open a subject.

**1. Global Header** — a live **Session Timer** countdown of the study block, a **Subject /
Module** title, and a **Focus Status** pill that tracks **Active Learning** vs **Idle** time
(discouraging leaving the tab open in the background — activity is reported to the server).

**2. Progression Sidebar** — the AI's **Concept Map**: a vertical list of chunks with
**✅ mastered**, **🔵 pulsing current**, and **🔒 locked (grayed out)** future concepts. The
student can't skip ahead, enforcing a step-by-step foundation. A **Live Performance** widget
shows their ELO / streak / points.

**3. Active Workspace** — a conversational feed where the AI Tutor delivers each concept with
**adaptive delivery** (personalized analogies from the student's interests + Shona/English
blending) and embeds a **Supporting Visual** (YouTube) below the theory.

**4. Knowledge Check Gate** — after teaching a concept, the chat assistant locks and a mandatory
**verification question** (generated strictly from the uploaded notes) appears.
- **Correct:** success feedback, ELO ticks up, and the next concept's padlock unlocks.
- **Incorrect:** the AI reveals the correct answer, re-explains where the logic slipped with a
  fresh analogy, and presents a **new question**.
- **3 fails:** the concept is flagged a **Roadblock**, a weakness report is **silently sent to the
  teacher's dashboard**, and the next accessible topic is opened to prevent frustration.

> The timetable gatekeeper still applies — each student sets their own study window/schedule.
> If you open the lesson outside that window you'll see the friendly gate with a **Demo override**
> button to enter anyway.

---

## 🎒 Independent Learner Onboarding (5 stages)

Independent learners go through a 5-stage wizard when they sign up, converting a self-directed
student into a structured, AI-guided environment. Register as an independent learner to experience it.

1. **Profile & Language** — identity setup (name/email/password), **academic level** selection
   (High School → University, which sets the AI's complexity), and a **Shona-blending toggle** that
   actually controls whether the AI mixes in regional expressions.
2. **Interest & Analogy Profiler** — a **tag-selection grid** (Chess, Industrial Mechanics, Software
   Engineering, Legal/Corporate TV Dramas…) plus an open text box, and a **learning mode** pick
   (Video-heavy / Text-first / Practice-quiz). The AI uses these to build personalized analogies.
3. **Subjects & Custom Notes** — create **custom subject folders**, upload PDFs/Word/text into each,
   tag each document as **📘 Reading Notes** (for staged lessons) or **📝 Past Papers / Question
   Bank** (for testing), with a **● Indexed** processing indicator and concept count.
4. **Smart Schedule Builder** — a **weekly availability grid** (per-day start/end + optional subject
   allocation), an **⚖️ Auto-Balance** button that weights hours by document density, and **session
   pacing** (e.g. 45 min study + 15 min break).
5. **Synchronization & Launch** — the AI compiles the weekly calendar and runs the **active
   gatekeeping check**:
   - Outside a block → personalized hold screen (*"Next session starts at 19:00…"*).
   - Inside a block → greets the student by name, references their interests, and opens Stage 1 of
     their uploaded notes.

The **Timetable Gatekeeper** then uses the weekly schedule (not just fixed hours) for independent
learners. Try it: log out and register a fresh independent account.

---

## ▶️ Running locally (development)

```bash
cd bt_learning
pip install -r requirements.txt
ADMIN_EMAIL=you@school.co.zw ADMIN_PASSWORD=YourPass ./run.sh    # or: python3 app.py
# serves on http://localhost:8000
```

Without `DATABASE_URL` the app uses a local **SQLite** file (`bt.db`). Set `DATABASE_URL` to a
PostgreSQL connection string to use Postgres locally too. The first admin is created from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` (no demo data is ever auto-seeded).

## 📁 Project layout

```
bt_learning/
  app.py            Flask app + all routes + admin/teacher bootstrap
  db.py             Data-access layer (SQLAlchemy: Postgres or SQLite)
  ai_engine.py      chunking, question generation, Shona + interest analogies, gatekeeper
  seed.py           DEV/TEST-ONLY demo data (never run in production)
  test_*.py         end-to-end tests (dev only)
  templates/        splash, choose, logins, admin, teacher, student, learn, onboarding…
  static/style.css  styling
  render.yaml       Render blueprint (web service + PostgreSQL) — for launch
  Procfile          gunicorn start command
  requirements.txt  Python dependencies
  runtime.txt       Python version
  DEPLOYMENT.md     step-by-step Render deployment guide
```
