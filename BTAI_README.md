# BT AI — Deployment & API Key Guide

BT AI is the AI layer that powers the heavy lifting (explaining notes, timetables, videos,
music, coaching, chat). **In the app it's always called "BT AI"** — the underlying engine is
**Groq** (free, fast, no billing needed).

It always works because it **falls back to the built-in engine** whenever the AI service can't
answer (no key, offline, or an API error).

---

## 🔑 Where to put your Groq API key in Render (step by step)

The key goes in Render's **Environment Variables** — NEVER in a file you commit.

1. Go to your Render dashboard → click your **web service** (e.g. `bt-learning`).
2. Click the **Environment** tab (top of the service page).
3. Click **Add Environment Variable**.
4. In the **Key** box type exactly:  `GROQ_API_KEY`
5. In the **Value** box paste your key (starts with `gsk_`).
6. Click **Save Changes** → Render auto-redeploys.
7. After it's live, open your app → the BT AI tools should show **"BT AI on"** instead of
   **"fallback"**.

That's the only step — the app reads `GROQ_API_KEY` automatically.

---

## 🆓 How to get a free Groq key (no billing)

1. Go to [console.groq.com](https://console.groq.com) and sign up (free, no credit card).
2. Open the **API Keys** page.
3. Click **Create API Key** → copy it (starts with `gsk_`).
4. Paste it into `GROQ_API_KEY` on Render.

Groq's free tier is generous and does **not** require billing details.

---

## What happens without a key

No key set? The app still fully works — BT AI uses its **built-in engine** (smart templates +
the student's uploaded notes) to explain, timetable, recommend videos/music, and coach. You'll
see "BT AI fallback" instead of "BT AI on". Add the key to unlock real AI answers.

---

## Which files changed for the Groq switch

**New files to add:**
```
btai.py
templates/chat.html
templates/coach.html
templates/answer_explain.html
templates/timetable.html
templates/ai_explain.html
templates/music_home.html
templates/playlist.html
templates/video.html
```

**Files to replace (updated):**
```
app.py
templates/learn.html
templates/student_home.html
requirements.txt        (now uses groq>=1.0 instead of google-generativeai)
build.sh                (installs groq)
.gitignore              (protects secrets)
```

Remember to use **git** (or the phone slash-trick) so folders stay intact.

---

## 🆕 Additional features now built (from the robustness plan)

- **AI-generated quizzes** — BT AI writes multiple-choice questions from the student's own notes
  (`/ai/quiz/<subject>`), beyond the rule-based ones.
- **Progress dashboard** — a visual summary of ELO, streak, points, and per-subject accuracy +
  concepts mastered (`/ai/progress`).
- **Study reminder** — tells the student when their next scheduled session starts
  (`/ai/reminder`).
- **Exam simulation** — a timed, scored mock exam using past papers, with a final score and
  feedback (`/exam/<subject>`), plus ELO rewards.
- **Teacher AI insights** — a Groq-generated paragraph summarizing class performance and weak
  spots (`/teacher/ai-insights`).
- **Language preference** — students can choose English, English+Shona, or English+Ndebele in
  their setup.

## 🔒 Security actions YOU must do (not in code)

1. **Deactivate the old Gemini key** you shared in this chat (it was exposed). In Google AI Studio.
2. **Set `SECRET_KEY`** in Render's Environment tab to a random long string (not the default).
   You can generate one here: `python -c "import secrets; print(secrets.token_hex(32))"`.
3. **Set `GROQ_API_KEY`** in Render (free key from console.groq.com).
4. **Make the repo private** now that it's working, if you don't want the code public.
5. **Back up your Postgres data** periodically — see the note in DEPLOYMENT.md.

## Summary of the core features built

1. **Persistent AI chat** — a real back-and-forth tutor chat on the lesson screen, answered
   from the uploaded notes.
2. **Break auto-switch music** — when the study timer hits zero, BT AI nudges the student to
   their break playlist.
3. **Per-concept auto video** — BT AI picks a supporting video for the exact concept being
   taught and embeds it in the lesson.
4. **Listen-while-learning** — a corner player button plays calm focus music during study.
5. **AI progress coach** — a weekly review generated from the student's quiz attempts and
   weak concepts.
6. **AI answer explanations** — when a student gets a knowledge check wrong, BT AI explains
   the correct answer in their learning style.
