# Deploying BT LEARNING to Render (always-on, PostgreSQL)

BT LEARNING is production-ready: **no demo accounts**, no pre-seeded data. On first
launch the database is empty except for the admin you configure. The app runs on
**PostgreSQL** (data persists across redeploys) served by **gunicorn**.

---

## 1) Push the code to GitHub

```bash
cd bt_learning
git init
git add -A
git commit -m "BT LEARNING launch"
# create a repo on github.com and push it
git remote add origin https://github.com/YOUR_USERNAME/bt-learning.git
git push -u origin main
```

> The `.gitignore` keeps the local SQLite DB, uploads, and `__pycache__` out of the repo.

## 2) Create the Render service from the blueprint

1. Log in at [render.com](https://render.com) → **New** → **Blueprint**.
2. Connect your GitHub repo.
3. Render reads **`render.yaml`**, which provisions:
   - a **free PostgreSQL database** (`bt-learning-db`), and
   - the **web service** (`bt-learning`) that runs `gunicorn app:app`.
4. Click **Apply**.

## 3) Create the admin account

The app has **no signup for admins/teachers** (students are provisioned by admins).
Create the first admin via environment variables:

1. In your web service → **Environment** tab, add:
   - `ADMIN_EMAIL` = e.g. `boss@yourschool.co.zw`
   - `ADMIN_PASSWORD` = a strong password
   - `ADMIN_NAME` = e.g. `Bongani Tshuma` (optional)
2. Render **auto-redeploys** on env changes. On startup, `bootstrap_admin()` creates that
   account. It's race-safe and idempotent (won't create duplicates).

> `SECRET_KEY` and `DATABASE_URL` are set automatically by the blueprint.

## 4) Open it

Your service gets a URL like `https://bt-learning.onrender.com`. Log in at
`/login/staff` with the admin email/password, then use the Admin Panel to:
- create classes,
- add teachers,
- upload student rosters (CSV).

Teachers and students then log in through the normal portals.

---

## Environment variables (summary)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (set automatically by Render) |
| `SECRET_KEY` | Flask session signing key (auto-generated) |
| `ADMIN_EMAIL` | Email for the initial admin (create on first boot) |
| `ADMIN_PASSWORD` | Initial admin password |
| `ADMIN_NAME` | Display name for the initial admin |

> If the service was created manually rather than from this Blueprint, add
> `DATABASE_URL` in the Render Environment tab using your PostgreSQL database's
> **Internal Database URL**. The app will boot without it for recovery, but SQLite
> data on Render is temporary and accounts will not survive a redeploy.

## How persistence works

Render's filesystem is ephemeral, so all data lives in the managed **PostgreSQL** database.
This means user accounts, notes, scores, and schedules survive restarts and redeploys.
The same code falls back to **SQLite** automatically when `DATABASE_URL` is not set
(local development / preview).

## Deployment files

- `render.yaml` — Render blueprint (web service + PostgreSQL)
- `Procfile` — gunicorn start command
- `requirements.txt` — Python dependencies
- `runtime.txt` — Python version
- `app.py` — calls `db.init_db()` + `bootstrap_admin()` on startup

## Notes

- **No demo data ships with the app.** The dev/test files (`seed.py`, `test_*.py`) exist
  only for local testing and are never invoked in production.
- **AI** is a rule-based engine reading only the notes you upload — no external API needed.
- The sandboxed in-app preview here uses SQLite; your Render deploy uses PostgreSQL.

## ⚠️ IMPORTANT: make sure Render uses `build.sh` (not `pip install -r requirements.txt`)

The recurring build failure (`Invalid requirement: set -e` / `pip: error: -e option requires 1
argument`) happens when Render runs the **default** Python build command
(`pip install -r requirements.txt`) and `requirements.txt` contains junk.

`build.sh` is now written so it **never reads `requirements.txt`** — it installs the known
dependencies explicitly. So no matter what is in `requirements.txt`, the build always succeeds.

**You MUST make sure Render's Build Command points to `build.sh`. There are two ways you created
your service — check which one you used:**

### If you used the Blueprint (`render.yaml`)
It already has `buildCommand: ./build.sh`. Just make sure you pushed the latest `render.yaml` +
`build.sh` to GitHub and re-deployed.

### If you created the service manually (Web Service form)
1. Open your service → **Settings** → **Build & Deploy**.
2. In the **Build Command** field, replace whatever is there with:
   ```
   bash ./build.sh
   ```
3. Click **Save Changes**, then **Deploy**.

Using `bash ./build.sh` instead of `./build.sh` avoids any file-permission issues.

---

## If the build fails on Render ("Invalid requirement")

A common cause is a **corrupted `requirements.txt`** — e.g. a stray line of Python code like
`import db, io, app as appmod` accidentally saved into the file. `pip install -r
requirements.txt` then errors with:
`ERROR: Invalid requirement: 'import db, io, app as appmod'`.

The Render build command should be **`./build.sh`** (or `bash ./build.sh`). The script installs
the dependencies from `requirements.txt`, so local installs, CI, and Render use the same
dependency set. Remove any stray Python or shell lines before redeploying.

To keep things tidy, still try to keep `requirements.txt` to these lines:
```
flask>=3.0
sqlalchemy>=2.0
psycopg2-binary>=2.9
gunicorn>=21.0
pypdf>=4.0
groq>=1.0,<2.0
```

### CI validation on every push

A GitHub Action (`.github/workflows/validate.yml`) runs on every push / pull request and:
1. **Validates `requirements.txt`** with pip's own parser (`validate_requirements.py`) — catches
   a stray `import ...` line and fails the check loudly, *before* any install or Render build.
2. Installs dependencies via `build.sh` (the same robust script Render uses).
3. Verifies the app imports and the DB schema initializes.
4. Runs all three end-to-end test suites.

So a bad `requirements.txt` now fails the **GitHub check** with a clear message instead of
breaking the Render deploy.

## Backing up your PostgreSQL data

Your data lives in Render's managed Postgres. To back it up:
- Render → your **database** → **Backups** tab → create a backup (free tier may be limited).
- Or export manually with the `psql`/`pg_dump` connection info from the database's **Connections** tab.

## Generate a secure SECRET_KEY

In a terminal: `python -c "import secrets; print(secrets.token_hex(32))"` — paste the output
into `SECRET_KEY` in Render's Environment tab.

## If you see "Internal Server Error"

The app has been fixed for the Postgres-specific issue that caused a 500. A health check is
available at `/healthz` (Render checks this automatically). If an error still appears:
1. Open your web service → **Logs** tab and look for the latest `Traceback` — paste it to us and
   we'll fix it precisely.
2. Confirm `DATABASE_URL` is set and your PostgreSQL instance is running (free instances sleep
   after ~15 min idle and take a few seconds to wake on the first request).
3. Make sure you've added `ADMIN_EMAIL` / `ADMIN_PASSWORD` and redeployed so an admin exists.
