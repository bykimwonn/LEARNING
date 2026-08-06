# Fix GitHub folders with git (the method that actually works)

The GitHub web "Upload files" keeps **flattening your folders** — that's why templates are loose
at the root instead of in `templates/`. The only reliable fix is to push with **git**, which
preserves folders exactly.

**Your upload DID fix `build.sh` and `requirements.txt`** ✅ — those are correct now. We just need
to get the folders right. Delete and re-push with git below.

---

## On your computer, open a terminal

On **Windows**: press `Windows + R`, type `cmd`, press Enter.
On **Mac**: open the Terminal app.
On the phone: you'll need a GitHub app or use the web only (see note at bottom).

Then run these commands **one by one**:

```bash
# 1. Navigate to where you extracted the BT LEARNING folder.
#    Replace the path with your actual folder location, e.g.:
cd "C:\Users\YourName\Downloads\BT-LEARNING-upload"

# 2. Remove any old git history so we start clean
rm -rf .git

# 3. Start a fresh git repo
git init

# 4. Add ALL files (including the templates/ and static/ folders)
git add -A

# 5. Commit
git commit -m "BT LEARNING correct structure"

# 6. Point to your GitHub repo (REPLACE with your repo name)
git remote add origin https://github.com/bykimwonn/LEARNING.git

# 7. Rename the branch to main and push
git branch -M main
git push -u origin main --force
```

> ⚠️ Git may ask for your GitHub **username and password**. For the password, use a **Personal
> Access Token** (Settings → Developer settings → Personal access tokens → Generate new token,
> check "repo", copy it, paste as password). Git will remember it.

---

## How to check it worked

After the push, visit your repo on GitHub. You should now see a **`templates/`** folder that you
can click into — it contains `base.html`, `learn.html`, etc., and inside it `teacher/` and
`onboard/` subfolders. Also a **`static/`** folder with `style.css`.

If you see `templates/` as a folder, it worked.

---

## Then redeploy on Render

1. Go to your Render service.
2. **Settings → Build & Deploy** → confirm **Build Command** = `bash ./build.sh`.
3. **Manual Deploy → Deploy latest commit**.

---

## If you can't use a terminal (phone/tablet)

The web "Upload files" won't keep folders, so the best web-only option is:

1. On GitHub, go to the **`LEARNING`** repo → **Settings → Danger Zone → Delete repository**.
2. Create a new empty repo.
3. GitHub has an **"Add file → Upload files"** option, but to keep folders you must drag **real
   folders**, not a zip. On many phones this is hard.

   If you truly can't get folders via web, the fallback is: **upload the whole `templates` folder
   as one drag** if your OS lets you select the folder. Otherwise, the git method above is the
   reliable path.
