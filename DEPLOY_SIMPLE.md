# BT LEARNING — Foolproof Render Deployment (Manual Web Service)

## Your exact situation (diagnosed from the build logs)

Your GitHub repo (`bykimwonn/BT-LEARNING`) is **private** and its files are **corrupted**:
`build.sh` contains README text instead of the shell script. This is the *only* reason the build
fails — your actual project files are correct.

The corruption happens because the files were **copy/pasted into GitHub's web editor**, mixing
content between files. **Do not copy/paste. Use git.**

---

## The most reliable path — fix `build.sh` on GitHub (2 minutes)

Go to `github.com/bykimwonn/BT-LEARNING` → open **`build.sh`** → click the **pencil ✏️ (edit)** →
select all, delete, and paste EXACTLY this:

```
#!/usr/bin/env bash
# BT LEARNING robust build script (used by Render).
set -e
cd "$(dirname "$0")"
echo "► BT LEARNING build starting..."
pip install --upgrade pip
pip install \
  "flask>=3.0" \
  "sqlalchemy>=2.0" \
  "psycopg2-binary>=2.9" \
  "gunicorn>=21.0" \
  "pypdf>=4.0"
echo "► Build complete."
```

Click **Commit changes**.

Then check **`requirements.txt`** — it must be EXACTLY these 5 lines:
```
flask>=3.0
sqlalchemy>=2.0
psycopg2-binary>=2.9
gunicorn>=21.0
pypdf>=4.0
```
If it has anything else, fix it the same way (delete all, paste the 5 lines, commit).

Then in Render → your `bt-learning` service → **Manual Deploy → Deploy latest commit**.

---

## OR use the git script (recommended, no copy/paste)

On your computer, from the `bt_learning` folder:
```bash
./push_to_github.sh https://github.com/bykimwonn/BT-LEARNING.git
```
This pushes the **actual files** via git (no copy/paste), verifies `build.sh` and
`requirements.txt` are correct first, and force-pushes cleanly. Then redeploy on Render.

---

## Why this keeps failing (so you can avoid it forever)

- Build failed #1: `requirements.txt` had Python junk → fix via clean files.
- Build failed #2: `build.sh` not found → file wasn't in repo.
- Build failed #3: `build.sh` had README text → copy/paste mixed up files.

**All three are the same root cause: files not pushed correctly to GitHub.** Using `git push`
of the actual files (not web-editor copy/paste) solves it permanently.

---

## Remaining parts (only after the build succeeds)

**Part 1 — Database:** Render → New → PostgreSQL → copy Internal Database URL → paste into
`DATABASE_URL` env var on your service. (Without it, data resets on redeploy.)

**Part 2 — Admin:** set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME` env vars. Log in at
`/login/staff`.

**Part 3 — Verify:** open `https://bt-learning.onrender.com/healthz` → should show
`{"status":"ok"}`.

