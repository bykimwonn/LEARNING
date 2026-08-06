# Upload BT LEARNING to GitHub — WITHOUT losing folders

**The one rule that fixes everything:**
GitHub's "Upload files" keeps folders **only if you upload real folders**, never a `.zip`.
So you MUST unzip on your computer FIRST, then drag the actual folders.

---

## Step 1 — Unzip on your computer

Open the `BT-LEARNING-upload.zip` file. It creates a folder named `BT-LEARNING-upload`.
Open that folder. You'll see:

```
BT-LEARNING-upload/
├── app.py              (a Python file)
├── db.py
├── ai_engine.py
├── build.sh
├── requirements.txt
├── Procfile
├── runtime.txt
├── render.yaml
├── seed.py
├── run.sh
├── .gitignore
├── README.md
├── templates/          (a FOLDER)
│   ├── base.html
│   ├── learn.html
│   ├── ...
│   ├── teacher/        (a sub-FOLDER)
│   └── onboard/        (a sub-FOLDER)
└── static/             (a FOLDER)
    └── style.css
```

---

## Step 2 — Delete the broken repo (cleanest)

Your current `LEARNING` repo has files in the wrong places. **Delete it and start fresh:**

1. GitHub → `bykimwonn/LEARNING` → **Settings** (bottom of left sidebar) → **Danger Zone** → **Delete this repository** → type the repo name to confirm.

2. Create a new repo: **+ → New repository** → name it `LEARNING` (or anything) → **Public** → **Create repository**.

---

## Step 3 — Upload the FOLDERS (not loose files)

On your new empty repo:

1. Click **Add file → Upload files**.
2. **Drag the `templates` folder** onto the upload area. → GitHub creates `templates/`.
3. Drag the **`static` folder** onto it. → creates `static/`.
4. Drag the remaining **loose files** (`app.py`, `db.py`, `build.sh`, `requirements.txt`, `Procfile`, `runtime.txt`, `render.yaml`, `seed.py`, `run.sh`) onto it.

When you drag the `templates` folder, GitHub **automatically includes** `templates/teacher/` and `templates/onboard/` because they're inside it. **Don't upload the teacher/onboard files separately.**

5. Scroll down → **Commit changes**.

---

## Step 4 — Connect Render to the NEW repo

1. Render → **Dashboard → New → Web Service** (or re-connect the existing one).
2. **Connect repository** → pick the new `LEARNING` repo → **Connect**.
3. Set:
   - **Build Command:** `bash ./build.sh`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
4. Add env vars: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NAME`, `SECRET_KEY` (Generate).
5. **Create Web Service.**

---

## Step 5 — Verify

Open `https://<your-app>.onrender.com/healthz` → should show `{"status":"ok"}`.

---

## Common mistake to avoid

❌ Dragging a `.zip` file → GitHub extracts only loose files, folders lost.
✅ Unzip first, then drag the **folders** `templates/` and `static/` individually.

If your OS "unzips" by showing you the contents when you double-click, use **right-click → Extract All** (Windows) or double-click then drag out the folder (Mac) so a real `templates` folder exists on disk.
