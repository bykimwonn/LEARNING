# Fix BT LEARNING folders — ON YOUR PHONE (works without a computer)

**The trick that makes folders on mobile:** in GitHub's **"Create new file"**, if you type a
**slash in the filename**, GitHub creates the folder automatically. Example: naming a file
`templates/base.html` creates a `templates/` folder and puts `base.html` inside it.

You already have ALL the files in your repo at the root. You just need to **move** each template
file into the right folder. Here's how, for each file:

---

## How to move ONE file (do this for each file below)

1. On your phone browser, open your repo → tap the file (e.g. `base.html`).
2. Tap the **pencil (edit)** icon → copy ALL the content (tap "Select all", "Copy").
3. Go **back** to the repo.
4. Tap **Add file → Create new file**.
5. In the **Name** box, type the full path from the list below (e.g. `templates/base.html`).
   **Don't leave it as just `base.html`.**
6. Tap the body and **Paste** the content you copied.
7. Tap **Commit changes**.
8. Now delete the old root file: tap `base.html` at the root → the **trash/delete** icon →
   **Commit changes**.

Repeat for every file in the list.

---

## List of files and where they must go

### Put in `templates/`
Create these as `templates/<name>` (then delete the root `<name>`):
```
base.html
choose.html
splash.html
learn.html
learn_empty.html
login_school.html
login_independent.html
login_staff.html
register.html
set_password.html
student_home.html
student_setup.html
practice.html
ranking.html
diagnostic.html
error.html
admin_home.html
```

### Put in `templates/teacher/`
Create these as `templates/teacher/<name>` (then delete root `<name>`):
```
_base.html
home.html
curriculum.html
weaknesses.html
student_detail.html
roster.html
```

### Put in `templates/onboard/`
Create these as `templates/onboard/<name>` (then delete root `<name>`):
```
_base.html
stage2.html
stage3.html
stage4.html
stage5.html
```

### Put in `static/`
Create `static/style.css` (then delete root `style.css`).

### LEAVE these in the ROOT (do NOT move them):
```
app.py
db.py
ai_engine.py
build.sh
requirements.txt
Procfile
runtime.txt
render.yaml
seed.py
run.sh
```
These are already correct at the root.

---

## The important check

After you finish, your repo should show a **`templates/` folder** and a **`static/` folder**
that you can tap into. That's the sign it worked.

---

## ⚠️ Honest heads-up

This is **~36 files** to move one-by-one, which is tedious and easy to make a mistake on.
If you can find **any computer** (a friend's, a school lab, an internet cafe) even for **5
minutes**, the git method is MUCH faster and cannot be done wrong:

```bash
cd "C:\Users\You\Downloads\BT-LEARNING-upload"
rm -rf .git
git init
git add -A
git commit -m "BT LEARNING"
git remote add origin https://github.com/bykimwonn/LEARNING.git
git branch -M main
git push -u origin main --force
```

That single set of commands fixes everything in one go.

---

## After either method: redeploy

1. Render → your service → **Settings → Build & Deploy** → Build Command = `bash ./build.sh`.
2. **Manual Deploy → Deploy latest commit**.
3. Check `https://<your-app>.onrender.com/healthz` shows `{"status":"ok"}`.
