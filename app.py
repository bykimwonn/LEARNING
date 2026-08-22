"""
BT LEARNING — Flask web application.
BT LEARNING — Owned by BONGANI TSHUMA.

Roles: admin, teacher, school_student, independent.
Core experience (Phases 4-6): timetable gatekeeper, staged AI tutor with
knowledge checks, weakness detection + reporting, ELO ranking.
"""
import os
import csv
import io
import json
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import (Flask, request, session, redirect, url_for,
                   render_template, flash, jsonify, abort)

import db
import ai_engine as ai
import btai

import markdown as _md

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bt-learning-demo-secret")
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB book uploads
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    uid = session.get("uid")
    return db.get_user(uid) if uid else None


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


app.jinja_env.globals["class_subjects"] = db.class_subjects


@app.template_filter("md")
def md_filter(text):
    """Render Markdown (from BT AI) to safe HTML for nice, structured answers."""
    if not text:
        return ""
    return _md.markdown(str(text), extensions=["extra"])


def login_required(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not current_user():
            return redirect(url_for("splash"))
        return f(*a, **kw)
    return wrap


def role_required(*roles):
    def deco(f):
        @wraps(f)
        def wrap(*a, **kw):
            u = current_user()
            if not u or u["role"] not in roles:
                abort(403)
            return f(*a, **kw)
        return wrap
    return deco


def touch_streak(user):
    today = datetime.date.today()
    last = user["last_active"]
    if last == str(today):
        return
    if last is None:
        streak = 1
    else:
        try:
            last_d = datetime.date.fromisoformat(last)
            streak = user["streak"] + 1 if (today - last_d).days == 1 else 1
        except Exception:
            streak = 1
    db.update_user(user["id"], streak=streak, last_active=str(today))


# ---------------------------------------------------------------------------
# Curriculum assembly
# ---------------------------------------------------------------------------
def curriculum(subject):
    """Flatten note chunks across a subject's ENABLED notes into a linear lesson."""
    notes = db.list_notes(subject=subject, category="notes")
    out = []
    for n in notes:
        if n["enabled"] != 1:
            continue
        for c in db.chunks_for_note(n["id"]):
            out.append({
                "chunk_id": c["id"],
                "note_id": n["id"],
                "note_title": n["title"],
                "title": c["title"],
                "content": c["content"],
            })
    return out


def past_papers(subject):
    notes = [n for n in db.list_notes(subject=subject, category="past_exams") if n["enabled"] == 1]
    qs = []
    for n in notes:
        for c in db.chunks_for_note(n["id"]):
            qs += db.questions_for_chunk(c["id"])
    return notes, qs


# ---------------------------------------------------------------------------
# Landing & entry portals  (Phase 2)
# ---------------------------------------------------------------------------
@app.route("/")
def splash():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("splash.html", owner="BONGANI TSHUMA")


@app.route("/choose")
def choose():
    return render_template("choose.html")


@app.route("/login/school", methods=["GET", "POST"])
def login_school():
    if request.method == "POST":
        sid = request.form.get("student_id", "").strip()
        pw = request.form.get("password", "")
        u = db.user_by_student_id(sid)
        if u and u["role"] == "school_student" and check_password_hash(u["password_hash"], pw):
            session["uid"] = u["id"]
            touch_streak(u)
            if u["must_change_password"]:
                flash("Welcome! Please set your private password on first entry.", "info")
                return redirect(url_for("set_password"))
            return redirect(url_for("dashboard"))
        flash("Invalid Student ID or password. If you haven't set your password yet, your school provided a temporary one.", "error")
    return render_template("login_school.html")


@app.route("/login/independent", methods=["GET", "POST"])
def login_independent():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = db.user_by_email(email)
        if u and u["role"] == "independent" and check_password_hash(u["password_hash"], pw):
            session["uid"] = u["id"]
            touch_streak(u)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login_independent.html")


@app.route("/login/staff", methods=["GET", "POST"])
def login_staff():
    """Staff (admin / teacher) login by email + password."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        u = db.user_by_email(email)
        if u and u["role"] in ("admin", "teacher") and \
                check_password_hash(u["password_hash"], pw):
            session["uid"] = u["id"]
            touch_streak(u)
            return redirect(url_for("dashboard"))
        flash("Invalid staff credentials.", "error")
    return render_template("login_staff.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        academic_level = request.form.get("academic_level", "").strip()
        blend = 1 if request.form.get("blend_regional") else 0
        if not name or not email or not pw:
            flash("Please fill in all required fields.", "error")
        elif db.user_by_email(email):
            flash("An account with that email already exists.", "error")
        else:
            uid = db.create_user(name=name, email=email,
                                 password_hash=generate_password_hash(pw),
                                 role="independent",
                                 academic_level=academic_level,
                                 blend_regional=blend,
                                 interests="",
                                 must_change_password=0, onboarded=0)
            session["uid"] = uid
            return redirect(url_for("onboard_stage2"))
    return render_template("register.html")


# ---------------------------------------------------------------------------
# INDEPENDENT LEARNER ONBOARDING WIZARD (5 stages)
# ---------------------------------------------------------------------------
INTEREST_TAGS = ["Chess", "Football/Soccer", "Basketball", "Industrial Mechanics",
                 "Software Engineering", "Legal/Corporate TV Dramas", "Competitive Sports",
                 "Music", "Farming", "Cooking", "Gaming", "Art & Drawing", "Reading",
                 "Cars & Engines", "Business", "Technology", "Science Fiction", "Hiking"]


@app.route("/onboard/stage2", methods=["GET", "POST"])
@login_required
@role_required("independent")
def onboard_stage2():
    u = current_user()
    if u["onboarded"]:
        return redirect(url_for("student_home"))
    if request.method == "POST":
        interests = request.form.get("interests", "").strip()
        # merge tag selections with open text
        tags = request.form.getlist("tags")
        all_int = ", ".join(dict.fromkeys([t.strip() for t in ([interests] + tags) if t.strip()]))
        mode = request.form.get("learning_mode", "video")
        db.update_user(u["id"], interests=all_int, learning_mode=mode)
        return redirect(url_for("onboard_stage3"))
    return render_template("onboard/stage2.html", user=u, tags=INTEREST_TAGS, stage=2)


@app.route("/onboard/stage3", methods=["GET", "POST"])
@login_required
@role_required("independent")
def onboard_stage3():
    u = current_user()
    if u["onboarded"]:
        return redirect(url_for("student_home"))
    subjects = db.user_subjects(u["id"])
    # count documents per subject for processing indicators
    subject_docs = {}
    for s in subjects:
        subject_docs[s] = db.list_notes(subject=s, category="notes") + \
                          db.list_notes(subject=s, category="past_exams")
    if request.method == "POST":
        return redirect(url_for("onboard_stage4"))
    return render_template("onboard/stage3.html", user=u, subjects=subjects,
                           subject_docs=subject_docs, stage=3)


@app.route("/onboard/stage3/add-subject", methods=["POST"])
@login_required
@role_required("independent")
def onboard_add_subject():
    u = current_user()
    name = request.form.get("name", "").strip()
    if name:
        subs = db.user_subjects(u["id"])
        if name not in subs:
            db.set_user_subjects(u["id"], subs + [name])
    return redirect(url_for("onboard_stage3"))


@app.route("/onboard/stage3/upload", methods=["POST"])
@login_required
@role_required("independent")
def onboard_upload():
    u = current_user()
    subject = request.form.get("subject", "").strip()
    category = request.form.get("category", "notes")
    title = request.form.get("title", "").strip()
    text = request.form.get("content", "").strip()
    file = request.files.get("file")
    if file and file.filename.lower().endswith((".txt", ".md")):
        text = file.read().decode("utf-8", errors="ignore").strip()
    elif file and file.filename.lower().endswith(".pdf"):
        text = _extract_pdf(file)
    if not subject or not title or not text:
        flash("Please provide a subject, title and content/file.", "error")
        return redirect(url_for("onboard_stage3"))
    if subject not in db.user_subjects(u["id"]):
        db.set_user_subjects(u["id"], db.user_subjects(u["id"]) + [subject])
    nid = db.add_note(title=title, subject=subject,
                      category="notes" if category == "notes" else "past_exams",
                      owner_id=u["id"], owner_role="independent", class_id=None,
                      content=text, status="processing")
    chunks = ai.chunk_content(text)
    db.save_chunks(nid, subject, chunks)
    db.set_note_status(nid, "active", chunk_count=len(chunks))
    flash(f"'{title}' chunked into {len(chunks)} concepts and indexed.", "success")
    return redirect(url_for("onboard_stage3"))


@app.route("/onboard/stage4", methods=["GET", "POST"])
@login_required
@role_required("independent")
def onboard_stage4():
    u = current_user()
    if u["onboarded"]:
        return redirect(url_for("student_home"))
    schedule = db.get_schedule(u["id"])
    if request.method == "POST":
        session_len = int(request.form.get("session_length", 45))
        break_len = int(request.form.get("break_length", 15))
        db.update_user(u["id"], session_length=session_len, break_length=break_len)
        # collect per-day blocks
        blocks = []
        for day in range(7):
            start = request.form.get(f"start_{day}")
            end = request.form.get(f"end_{day}")
            subj = request.form.get(f"subject_{day}") or None
            if start and end and int(end) > int(start):
                blocks.append((day, int(start), int(end), subj))
        db.set_schedule(u["id"], blocks)
        return redirect(url_for("onboard_stage5"))
    subjects = db.user_subjects(u["id"])
    return render_template("onboard/stage4.html", user=u, schedule=schedule,
                           subjects=subjects, days=ai.WEEKDAYS, stage=4)


@app.route("/onboard/stage4/auto-balance", methods=["POST"])
@login_required
@role_required("independent")
def onboard_auto_balance():
    """Distribute selected weekly study hours across subjects by document density."""
    u = current_user()
    subjects = db.user_subjects(u["id"])
    # total weekly hours selected (from current form state) is captured client-side;
    # here we allocate proportions based on note/chunk density.
    density = []
    for s in subjects:
        n = 0
        for cat in ("notes", "past_exams"):
            for doc in db.list_notes(subject=s, category=cat):
                n += doc["chunk_count"] or 1
        density.append((s, n))
    total = sum(d for _, d in density) or 1
    alloc = {s: round(d * 100 / total) for s, d in density}
    return jsonify(alloc)


@app.route("/onboard/stage5")
@login_required
@role_required("independent")
def onboard_stage5():
    u = current_user()
    schedule = db.get_schedule(u["id"])
    now = datetime.datetime.now()
    state = ai.schedule_state(schedule, now) if schedule else {"in_block": False, "next": None}
    compiled = []
    for day in range(7):
        blocks = [b for b in schedule if b["day"] == day]
        if blocks:
            for b in sorted(blocks, key=lambda x: x["start_hour"]):
                compiled.append({"day": ai.WEEKDAYS[day], "start": b["start_hour"],
                                 "end": b["end_hour"], "subject": b["subject"]})
    # find first subject with notes for launch
    launch_subject = None
    for s in db.user_subjects(u["id"]):
        if curriculum(s):
            launch_subject = s
            break
    return render_template("onboard/stage5.html", user=u, schedule=schedule,
                           compiled=compiled, state=state, launch_subject=launch_subject,
                           now=now, ai_hold_message=ai.schedule_hold_message(state), stage=5)


@app.route("/onboard/stage5/complete", methods=["POST"])
@login_required
@role_required("independent")
def onboard_complete():
    u = current_user()
    db.update_user(u["id"], onboarded=1)
    flash("Welcome aboard! Your AI-guided learning environment is ready.", "success")
    launch = request.form.get("launch_subject")
    if launch and curriculum(launch):
        return redirect(url_for("learn", subject=launch))
    return redirect(url_for("student_home"))


@app.route("/set-password", methods=["GET", "POST"])
@login_required
def set_password():
    u = current_user()
    if request.method == "POST":
        p1 = request.form.get("p1", "")
        p2 = request.form.get("p2", "")
        if len(p1) < 4:
            flash("Password must be at least 4 characters.", "error")
        elif p1 != p2:
            flash("Passwords do not match.", "error")
        else:
            db.update_user(u["id"], password_hash=generate_password_hash(p1),
                           must_change_password=0)
            flash("Your private password is set. Happy learning!", "success")
            return redirect(url_for("dashboard"))
    return render_template("set_password.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("splash"))


@app.route("/dashboard")
@login_required
def dashboard():
    u = current_user()
    if u["role"] == "admin":
        return redirect(url_for("admin_home"))
    if u["role"] == "teacher":
        return redirect(url_for("teacher_home"))
    return redirect(url_for("student_home"))


# ---------------------------------------------------------------------------
# ADMIN PANEL  (Phase 2) — rosters, classes, teachers
# ---------------------------------------------------------------------------
@app.route("/admin")
@login_required
@role_required("admin")
def admin_home():
    teachers = db.list_teachers()
    classes = db.list_classes()
    students = [s for s in db.list_users() if s["role"] == "school_student"]
    independents = [s for s in db.list_users() if s["role"] == "independent"]
    return render_template("admin_home.html", teachers=teachers, classes=classes,
                           students=students, independents=independents,
                           roster_status=session.pop("roster_status", None))


@app.route("/admin/add-class", methods=["POST"])
@login_required
@role_required("admin")
def admin_add_class():
    name = request.form.get("name", "").strip()
    subjects = [s.strip() for s in request.form.get("subjects", "").split(",") if s.strip()]
    if name:
        cid = db.create_class(name)
        if subjects:
            db.set_class_subjects(cid, subjects)
        flash(f"Class '{name}' created.", "success")
    return redirect(url_for("admin_home"))


@app.route("/admin/add-teacher", methods=["POST"])
@login_required
@role_required("admin")
def admin_add_teacher():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    pw = request.form.get("password", "") or "teacher123"
    class_id = request.form.get("class_id") or None
    if name and email and not db.user_by_email(email):
        tid = db.create_user(name=name, email=email,
                             password_hash=generate_password_hash(pw),
                             role="teacher", class_id=int(class_id) if class_id else None,
                             must_change_password=0)
        # Link the teacher to their assigned class(es) so the dashboard has a class dropdown
        if class_id:
            cid = int(class_id)
            subs = db.class_subjects(cid) or [None]
            db.set_teacher_classes(tid, [(cid, s) for s in subs])
        flash(f"Teacher {name} created (temp password: {pw}).", "success")
    else:
        flash("Could not create teacher. Check details/email uniqueness.", "error")
    return redirect(url_for("admin_home"))


@app.route("/admin/upload-roster", methods=["POST"])
@login_required
@role_required("admin")
def admin_upload_roster():
    """CSV: student_id, name, class_name, subjects(comma-separated, optional)"""
    file = request.files.get("roster")
    class_id = request.form.get("class_id") or None
    if not file:
        flash("No file selected.", "error")
        return redirect(url_for("admin_home"))
    stream = io.StringIO(file.read().decode("utf-8-sig"))
    reader = csv.reader(stream)
    header = next(reader, None)
    temp_pw = "btlearn123"
    created = 0
    for row in reader:
        if len(row) < 3 or not row[0].strip():
            continue
        sid, name, class_name = row[0].strip(), row[1].strip(), row[2].strip()
        subjects = [s.strip() for s in row[3].split(",")] if len(row) > 3 and row[3] else []
        if db.user_by_student_id(sid):
            continue
        if class_id is None:
            # resolve class by name or create
            cid = db.get_class_by_name(class_name) or db.create_class(class_name)
        else:
            cid = int(class_id)
        uid = db.create_user(name=name, student_id=sid, class_id=cid,
                             password_hash=generate_password_hash(temp_pw),
                             role="school_student", must_change_password=1,
                             interests="")
        if subjects:
            db.set_user_subjects(uid, subjects)
        created += 1
    session["roster_status"] = f"Roster processed: {created} student(s) added. " \
                               f"Temporary password for all: {temp_pw} (forced change on first login)."
    return redirect(url_for("admin_home"))


# ---------------------------------------------------------------------------
# TEACHER DASHBOARD — command center (Phase 2 + Phase 5 + blueprint)
# ---------------------------------------------------------------------------
import threading


def _activate_after(nid, seconds=3):
    """Simulate AI chunking finishing asynchronously: flips a note's status
    from 'processing' to 'active' after a short delay."""
    def flip():
        try:
            import time
            time.sleep(seconds)
            db.set_note_status(nid, "active")
        except Exception:
            pass
    t = threading.Thread(target=flip, daemon=True)
    t.start()


def teacher_context():
    """Return the teacher's classes and the currently selected teaching link."""
    u = current_user()
    links = db.teacher_classes(u["id"])
    sel_id = session.get("teacher_class_link")
    if links and sel_id not in [l["id"] for l in links]:
        sel_id = links[0]["id"]
        session["teacher_class_link"] = sel_id
    sel = next((l for l in links if l["id"] == sel_id), None)
    return links, sel


def teacher_notification_count():
    u = current_user()
    total = 0
    for tc in db.teacher_classes(u["id"]):
        total += len(db.class_action_items(tc["class_id"], tc["subject"], threshold=2))
    return total


@app.route("/teacher")
@login_required
@role_required("teacher")
def teacher_home():
    u = current_user()
    links, sel = teacher_context()
    notes_count = 0
    weaknesses = []
    leaderboard = []
    health = None
    action_items = []
    students = []
    if sel:
        class_id, subject = sel["class_id"], sel["subject"]
        notes_count = len(db.list_notes(subject=subject, class_id=class_id))
        weaknesses = db.list_weaknesses_for_subject(class_id, subject)
        action_items = db.class_action_items(class_id, subject, threshold=2)
        health = db.class_health(class_id, subject)
        students = db.students_in_class(class_id)
        # class leaderboard (Board 1 = top 3 this week)
        board = sorted(students, key=lambda s: (s["elo"] + s["streak"] * 3), reverse=True)
        leaderboard = [{"student": s, "board1": i < 3, "pos": i + 1}
                       for i, s in enumerate(board)]
    return render_template("teacher/home.html", user=u, links=links, sel=sel,
                           notes_count=notes_count, weaknesses=weaknesses,
                           action_items=action_items, health=health,
                           leaderboard=leaderboard, students=students,
                           notifications=teacher_notification_count())


@app.route("/teacher/select-class", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_select_class():
    link_id = request.form.get("link_id")
    if link_id:
        session["teacher_class_link"] = int(link_id)
    nxt = request.form.get("next") or url_for("teacher_home")
    return redirect(nxt)


@app.route("/teacher/curriculum")
@login_required
@role_required("teacher")
def teacher_curriculum():
    u = current_user()
    links, sel = teacher_context()
    tab = request.args.get("tab", "notes")
    notes = exams = []
    if sel:
        notes = db.list_notes(subject=sel["subject"], class_id=sel["class_id"], category="notes")
        exams = db.list_notes(subject=sel["subject"], class_id=sel["class_id"], category="past_exams")
        # ensure disabled notes are not taught
    return render_template("teacher/curriculum.html", user=u, links=links, sel=sel,
                           notes=notes, exams=exams, tab=tab,
                           notifications=teacher_notification_count())


@app.route("/teacher/weaknesses")
@login_required
@role_required("teacher")
def teacher_weaknesses():
    u = current_user()
    links, sel = teacher_context()
    students = []
    if sel:
        class_id, subject = sel["class_id"], sel["subject"]
        students = db.students_in_class(class_id)
        for s in students:
            ws = db.weakness_for_student_subject(s["id"], subject)
            s = dict(s)
            s["weak_count"] = len(ws)
            s["max_fails"] = max((w["fail_count"] for w in ws), default=0)
            if s["weak_count"] == 0:
                s["status"] = "green"
            elif s["weak_count"] == 1 and s["max_fails"] < 3:
                s["status"] = "yellow"
            else:
                s["status"] = "red"
    return render_template("teacher/weaknesses.html", user=u, links=links, sel=sel,
                           students=students, notifications=teacher_notification_count())


@app.route("/teacher/student/<int:uid>")
@login_required
@role_required("teacher")
def teacher_student_detail(uid):
    u = current_user()
    links, sel = teacher_context()
    stu = db.get_user(uid)
    if not stu or stu["role"] != "school_student":
        abort(404)
    weaknesses = db.weakness_for_student_subject(uid, sel["subject"]) if sel else []
    return render_template("teacher/student_detail.html", user=u, links=links, sel=sel,
                           stu=stu, weaknesses=weaknesses,
                           notifications=teacher_notification_count())


@app.route("/teacher/roster")
@login_required
@role_required("teacher")
def teacher_roster():
    u = current_user()
    links, sel = teacher_context()
    students = db.students_in_class(sel["class_id"]) if sel else []
    return render_template("teacher/roster.html", user=u, links=links, sel=sel,
                           students=students, notifications=teacher_notification_count())


@app.route("/teacher/upload", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_upload():
    u = current_user()
    links, sel = teacher_context()
    nxt = request.form.get("next") or url_for("teacher_home")
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    category = request.form.get("category", "notes")
    text = request.form.get("content", "").strip()
    file = request.files.get("file")
    if file and file.filename.lower().endswith((".txt", ".md")):
        text = file.read().decode("utf-8", errors="ignore").strip()
    elif file and file.filename.lower().endswith(".pdf"):
        text = _extract_pdf(file)
    if not title or not subject or not text:
        flash("Please provide a title, subject, and note content/file.", "error")
        return redirect(nxt)
    class_id = sel["class_id"] if sel else u["class_id"]
    note_id = db.add_note(title=title, subject=subject, category=category,
                          owner_id=u["id"], owner_role="teacher", class_id=class_id,
                          content=text, status="processing")
    chunks = ai.chunk_content(text)
    db.save_chunks(note_id, subject, chunks)
    db.set_note_status(note_id, "processing", chunk_count=len(chunks))
    _activate_after(note_id)
    flash(f"'{title}' is being chunked by the AI — it will be Active in a moment.", "success")
    return redirect(nxt)


@app.route("/teacher/note/<int:nid>/toggle", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_note_toggle(nid):
    n = db.get_note(nid)
    if n and n["owner_id"] == current_user()["id"]:
        db.set_note_enabled(nid, not n["enabled"])
        flash(f"'{n['title']}' is now {'Enabled' if not n['enabled'] else 'Disabled'} for students.", "success")
    return redirect(request.form.get("next") or url_for("teacher_curriculum"))


@app.route("/teacher/note/<int:nid>/delete", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_note_delete(nid):
    n = db.get_note(nid)
    if n and n["owner_id"] == current_user()["id"]:
        db.delete_note(nid)
        flash(f"'{n['title']}' deleted.", "success")
    return redirect(request.form.get("next") or url_for("teacher_curriculum"))


@app.route("/teacher/weakness/<int:wid>/resolve", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_resolve(wid):
    db.resolve_weakness(wid)
    flash("Weakness marked as resolved. AI tracking for this concept has been reset.", "success")
    nxt = request.form.get("next") or url_for("teacher_home")
    return redirect(nxt)


@app.route("/teacher/reset-password/<int:uid>", methods=["POST"])
@login_required
@role_required("teacher")
def teacher_reset_password(uid):
    stu = db.get_user(uid)
    if stu and stu["role"] == "school_student":
        db.reset_student_password(uid)
        flash(f"Password reset for {stu['name']} to temporary password 'btlearn123' "
              f"(forced change on next login).", "success")
    return redirect(request.form.get("next") or url_for("teacher_roster"))


def _extract_pdf(file):
    """Best-effort text extraction from a PDF. If pypdf is unavailable,
    fall back to raw binary text stripping (keeps prototype simple)."""
    try:
        from pypdf import PdfReader
        r = PdfReader(file)
        return "\n".join((p.extract_text() or "") for p in r.pages).strip()
    except Exception:
        try:
            data = file.read()
            return data.decode("latin-1", errors="ignore")[:20000]
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# STUDENT home / setup
# ---------------------------------------------------------------------------
@app.route("/student/setup", methods=["GET", "POST"])
@login_required
def student_setup():
    u = current_user()
    if request.method == "POST":
        interests = request.form.get("interests", "").strip()
        start = int(request.form.get("start_hour", 18))
        end = int(request.form.get("end_hour", 21))
        language = request.form.get("language", "en")
        db.update_user(u["id"], interests=interests, language=language,
                       study_start_hour=start, study_end_hour=end)
        flash("Your preferences and study schedule are saved.", "success")
        return redirect(url_for("student_home"))
    return render_template("student_setup.html", user=u)


@app.route("/student")
@login_required
@role_required("school_student", "independent")
def student_home():
    u = current_user()
    # independent learners must complete onboarding first
    if u["role"] == "independent" and not u["onboarded"]:
        return redirect(url_for("onboard_stage2"))
    touch_streak(db.get_user(u["id"]))
    u = db.get_user(u["id"])
    subjects = db.subjects_for_student(u)
    subjects_with_progress = []
    for s in subjects:
        curr = db.get_progress(u["id"], s)
        done = db.completed_concepts(u["id"], s)
        total = len(curriculum(s))
        subjects_with_progress.append({
            "subject": s,
            "current": (curr["current_chunk"] if curr else 0),
            "done": len(done),
            "total": total,
        })
    weaknesses = db.list_weaknesses(user_id=u["id"])
    my_notes = [n for n in db.list_notes() if n["owner_id"] == u["id"]]
    books = db.list_books(u["id"])
    return render_template("student_home.html", user=u, subjects=subjects_with_progress,
                           weaknesses=weaknesses, my_notes=my_notes, books=books,
                           ai_enabled=btai.ai_enabled())


@app.route("/student/upload", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def student_upload():
    u = current_user()
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    text = request.form.get("content", "").strip()
    file = request.files.get("file")
    if file and file.filename.lower().endswith((".txt", ".md")):
        text = file.read().decode("utf-8", errors="ignore").strip()
    elif file and file.filename.lower().endswith(".pdf"):
        text = _extract_pdf(file)
    if not title or not subject or not text:
        flash("Please provide title, subject and content.", "error")
        return redirect(url_for("student_home"))
    nid = db.add_note(title=title, subject=subject, category="notes",
                      owner_id=u["id"], owner_role=u["role"], class_id=u["class_id"],
                      content=text, status="active")
    chunks = ai.chunk_content(text)
    db.save_chunks(nid, subject, chunks)
    db.set_note_status(nid, "active", chunk_count=len(chunks))
    if subject not in db.user_subjects(u["id"]):
        subs = db.user_subjects(u["id"]) + [subject]
        db.set_user_subjects(u["id"], subs)
    flash(f"Your notes '{title}' were ingested into the AI index.", "success")
    return redirect(url_for("student_home"))


# ---------------------------------------------------------------------------
# LEARNING EXPERIENCE  (Phase 4) — timetable gatekeeper + staged AI tutor
# ---------------------------------------------------------------------------
def _learn_state(subject, idx):
    st = session.get("learn_state", {}).get(subject)
    if not st or st["idx"] != idx:
        st = {"idx": idx, "qo": 0, "wrong": 0}
    return st


def _save_learn_state(subject, st):
    d = session.get("learn_state", {})
    d[subject] = st
    session["learn_state"] = d


@app.route("/learn/<subject>")
@login_required
@role_required("school_student", "independent")
def learn(subject):
    u = current_user()
    touch_streak(db.get_user(u["id"]))
    u = db.get_user(u["id"])
    course = curriculum(subject)
    if not course:
        return render_template("learn_empty.html", subject=subject)
    prog = db.get_progress(u["id"], subject)
    idx = prog["current_chunk"] if prog else 0
    if idx >= len(course):
        idx = len(course) - 1
    chunk = course[idx]
    questions = db.questions_for_chunk(chunk["chunk_id"])
    is_last = idx >= len(course) - 1

    now = datetime.datetime.now()
    # Gatekeeper: independent learners use their weekly schedule; others use legacy hours
    schedule = db.get_schedule(u["id"]) if u["role"] == "independent" else []
    if schedule:
        sched_state = ai.schedule_state(schedule, now)
        study_ok = sched_state["in_block"] or session.get("override_study", False)
        study_msg = ai.schedule_hold_message(sched_state)
    else:
        sched_state = None
        study_ok = ai.is_study_time(now.hour, u["study_start_hour"], u["study_end_hour"]) \
            or session.get("override_study", False)
        study_msg = ai.study_window_message(u["study_start_hour"], u["study_end_hour"])
    feedback = session.pop("learn_feedback", None)
    wrong_msg = session.pop("wrong_msg", None)
    roadblock_msg = session.pop("roadblock_msg", None)
    advance_msg = session.pop("advance_msg", None)

    # --- learn state: pick which knowledge-check question to show ---
    st = _learn_state(subject, idx)
    qo = st["qo"]
    current_q = questions[qo % len(questions)] if questions else None

    # --- progression map: lock/done/current states ---
    done = db.completed_concepts(u["id"], subject)
    course_map = []
    for i, c in enumerate(course):
        if i in done:
            state = "done"
        elif i == idx:
            state = "current"
        elif i < idx:
            state = "unlocked"   # skipped (e.g. after a roadblock)
        else:
            state = "locked"
        course_map.append({"i": i, "title": c["title"], "state": state})

    # --- focus + timer ---
    foc = db.focus_for(u["id"], subject)
    if schedule:
        # timer reflects the current (or nearest) scheduled block
        blk = None
        if sched_state and sched_state.get("block"):
            blk = sched_state["block"]
        else:
            # first block today or next session
            today = [b for b in schedule if b["day"] == now.weekday()] or schedule[:1]
            blk = today[0] if today else None
        if blk:
            timer = ai.session_countdown(blk["start_hour"], blk["end_hour"], now)
        else:
            timer = {"remaining_min": 0, "total_min": 60, "in_window": False,
                     "start_hour": 0, "end_hour": 23}
    else:
        timer = ai.session_countdown(u["study_start_hour"], u["study_end_hour"], now)
    # Per-concept video (BT AI picks a relevant supporting video; falls back to subject video)
    if btai.ai_enabled():
        v = btai.recommend_video(subject, chunk["title"], u["interests"])
    else:
        v = ai.video_for(subject)
    # ensure we always have a direct watch link as a fallback
    if not v.get("watch_url"):
        q = v.get("query") or v.get("title", subject)
        v["watch_url"] = f"https://www.youtube.com/results?search_query={q.replace(' ', '+')}"
    video = v
    # gather note context for the AI chat panel on this subject
    ai_context = "\n".join(c["content"] for c in course)

    blend = bool(u["blend_regional"])
    personalized = ai.personalized_explain(chunk["title"], u["interests"], blend=blend)

    # subject switcher: list all the student's subjects so they can jump between them
    all_subjects = db.subjects_for_student(u)

    return render_template("learn.html", user=u, subject=subject, course=course,
                           idx=idx, chunk=chunk, questions=questions, is_last=is_last,
                           study_ok=study_ok, now=now, feedback=feedback,
                           wrong_msg=wrong_msg, roadblock_msg=roadblock_msg,
                           advance_msg=advance_msg, current_q=current_q,
                           course_map=course_map, focus=foc, timer=timer, video=video,
                           personalized=personalized,
                           study_msg=study_msg,
                           greeting=ai.greet(u["interests"], now.hour, blend=blend),
                           shona=ai.SHONA, ai_context=ai_context,
                           all_subjects=all_subjects)


@app.route("/learn/<subject>/answer", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def learn_answer(subject):
    u = current_user()
    qid = int(request.form.get("qid"))
    chosen = int(request.form.get("choice"))
    course = curriculum(subject)
    prog = db.get_progress(u["id"], subject)
    idx = prog["current_chunk"] if prog else 0
    if idx >= len(course):
        idx = len(course) - 1
    chunk = course[idx]
    question = None
    for q in db.questions_for_chunk(chunk["chunk_id"]):
        if q["id"] == qid:
            question = q
            break
    if question is None:
        return redirect(url_for("learn", subject=subject))
    correct = (chosen == question["answer_index"])
    db.log_attempt(u["id"], qid, subject, idx, 1 if correct else 0)

    st = _learn_state(subject, idx)
    if correct:
        db.mark_concept_complete(u["id"], subject, idx)
        gain = 8
        points = 5
        db.update_user(u["id"], elo=u["elo"] + gain, points=u["points"] + points)
        flashmsg = f"{ai.praise(first_try=True)} +{gain} ELO, +{points} points."
        _auto_resolve_weakness(u["id"], subject, chunk["title"])
        new_idx = idx + 1 if not is_last_idx(idx, course) else idx
        db.set_progress_current(u["id"], subject, new_idx)
        _save_learn_state(subject, {"idx": new_idx, "qo": 0, "wrong": 0})
        if not is_last_idx(idx, course):
            session["advance_msg"] = f"Concept unlocked! Moving on to Concept {new_idx+1}."
        else:
            session["advance_msg"] = "🎉 You mastered the final concept of this module!"
        session["learn_feedback"] = {"correct": True, "msg": flashmsg,
                                     "answer": question["answer_index"]}
    else:
        iv = ai.intervention_log(chunk["title"], u["interests"])
        db.upsert_weakness(u["id"], subject, chunk["title"], add=1,
                           transcript=iv["transcript"], analogy=iv["analogy"],
                           language_note=iv["language_note"])
        db.update_user(u["id"], elo=max(800, u["elo"] - 1))
        st["wrong"] += 1
        st["qo"] += 1

        # Re-explain: highlight where the logic failed by revealing the answer
        correct_text = question["options"][question["answer_index"]]
        reexplain = (
            f"{ai.SHONA['mistake']} The answer we were looking for is "
            f"<b>'{correct_text}'</b>. {iv['analogy']} "
            f"{ai.SHONA['try_again']} Let's try a fresh question."
        )
        if st["wrong"] >= 3:
            # --- ROADBLOCK: silently report to teacher, unlock next topic ---
            _save_learn_state(subject, {"idx": idx + 1 if not is_last_idx(idx, course) else idx,
                                        "qo": 0, "wrong": 0})
            if not is_last_idx(idx, course):
                db.set_progress_current(u["id"], subject, idx + 1)
            session["roadblock_msg"] = (
                f"🚧 '{chunk['title']}' is flagged as a <b>Roadblock</b>. We've silently sent "
                f"a weakness report to your teacher. To avoid frustration, we've opened the next "
                f"topic — you can return to this concept anytime."
            )
            session["learn_feedback"] = {"correct": False, "msg": reexplain,
                                         "answer": question["answer_index"]}
        else:
            _save_learn_state(subject, st)
            session["wrong_msg"] = reexplain
            session["learn_feedback"] = {
                "correct": False,
                "msg": f"{ai.SHONA['try_again']} {ai.SHONA['motivate']} "
                       f"(failure #{st['wrong']} on this concept). A new question is ready.",
                "answer": question["answer_index"]}
    return redirect(url_for("learn", subject=subject, qid=qid))


@app.route("/focus", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def focus_heartbeat():
    try:
        active = int(request.json.get("active", 0))
        idle = int(request.json.get("idle", 0))
    except Exception:
        active = idle = 0
    subject = request.json.get("subject", "")
    if subject:
        db.add_focus(current_user()["id"], subject, max(0, active), max(0, idle))
    return jsonify({"ok": True})


def is_last_idx(idx, course):
    return idx >= len(course) - 1


def _concept_failures(user_id, subject, idx):
    return db.concept_failure_count(user_id, subject, idx)


def _auto_resolve_weakness(user_id, subject, concept):
    db.resolve_weakness_by(user_id, subject, concept)


@app.route("/learn/<subject>/override", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def learn_override(subject):
    # Demo convenience: temporarily lift the timetable gatekeeper so the
    # reviewer can enter the lesson outside the student's study window.
    session["override_study"] = True
    flash("Demo override: the timetable gatekeeper has been lifted for this session.", "info")
    return redirect(url_for("learn", subject=subject))


@app.route("/learn/<subject>/diagnostic")
@login_required
@role_required("school_student", "independent")
def diagnostic(subject):
    u = current_user()
    weak = [w for w in db.list_weaknesses(user_id=u["id"]) if w["subject"] == subject]
    return render_template("diagnostic.html", user=u, subject=subject, weaknesses=weak)


# ---------------------------------------------------------------------------
# PRACTICE / past papers  (Phase 4/5)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# BT AI TOOLS  (Gemini-powered; falls back to rule-based automatically)
# ---------------------------------------------------------------------------
@app.route("/ai/chat", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_chat():
    """Persistent AI tutor chat bound to the uploaded notes."""
    u = current_user()
    subject = request.form.get("subject", "")
    message = request.form.get("message", "").strip()
    # gather note context for this subject
    context_parts = []
    for n in db.list_notes(subject=subject, category="notes"):
        for c in db.chunks_for_note(n["id"]):
            context_parts.append(c["content"])
    context = "\n".join(context_parts)
    # simple per-session history stored in the flask session
    hist = session.get("ai_chat", [])
    reply = btai.chat(context, message, u["interests"], u["academic_level"], hist)
    hist.append({"role": "user", "text": message})
    hist.append({"role": "ai", "text": reply})
    session["ai_chat"] = hist[-12:]
    return render_template("chat.html", user=u, subject=subject, message=message,
                           reply=reply, history=hist, ai_enabled=btai.ai_enabled())


@app.route("/ai/coach")
@login_required
@role_required("school_student", "independent")
def ai_coach():
    """AI progress coach: weekly review from quiz attempts."""
    u = current_user()
    subjects = db.subjects_for_student(u)
    reports = []
    for subj in subjects:
        atts = db.attempts_for_user_subject(u["id"], subj)
        total = len(atts)
        correct = sum(1 for a in atts if a["correct"])
        wrong = total - correct
        weak = db.weakness_for_student_subject(u["id"], subj)
        weak_names = [w["concept"] for w in weak][:3]
        coach = btai.progress_coach(subj, total, correct, wrong, weak_names, u["interests"])
        reports.append({"subject": subj, "total": total, "correct": correct,
                        "wrong": wrong, "weak": weak_names, "coach": coach})
    return render_template("coach.html", user=u, reports=reports,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/answer-explain", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_answer_explain():
    """Explain a failed knowledge-check answer via BT AI."""
    u = current_user()
    question = request.form.get("question", "")
    correct = request.form.get("correct", "")
    chosen = request.form.get("chosen", "")
    subject = request.form.get("subject", "")
    explanation = btai.explain_answer(question, correct, chosen, u["interests"])
    return render_template("answer_explain.html", user=u, explanation=explanation,
                           subject=subject, question=question, correct=correct,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/timetable", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_timetable():
    """AI timetable builder: restructure schedule + print/save-as-PDF."""
    u = current_user()
    subjects = db.subjects_for_student(u)
    ai_note = None
    if request.method == "POST":
        prefs = request.form.get("preferences", "").strip()
        hours = request.form.get("hours", "10")
        try:
            hours = int(hours)
        except Exception:
            hours = 10
        tbl = btai.generate_timetable(subjects, total_hours=hours, preferences=prefs)
        # persist as schedule blocks
        blocks = []
        day_map = {d: i for i, d in enumerate(ai.WEEKDAYS)}
        for day, sched in tbl.items():
            day_idx = day_map.get(day, 0)
            for slot in sched:
                s = int(slot.get("start", 9))
                e = int(slot.get("end", 10))
                blocks.append((day_idx, s, e, slot.get("subject")))
        db.set_schedule(u["id"], blocks)
        if btai.ai_enabled():
            ai_note = "BT AI restructured your timetable from your subjects and preferences."
        else:
            ai_note = "Balanced timetable generated (Gemini not reachable right now — using fallback engine)."
    sched = db.get_schedule(u["id"])
    compiled = {}
    for b in sched:
        compiled.setdefault(ai.WEEKDAYS[b["day"]], []).append(
            {"subject": b["subject"], "start": b["start_hour"], "end": b["end_hour"]})
    return render_template("timetable.html", user=u, subjects=subjects,
                           compiled=compiled, days=ai.WEEKDAYS, ai_note=ai_note,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/explain", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_explain():
    """Explain a chunk of notes via BT AI in plain English."""
    u = current_user()
    content = request.form.get("content", "")
    subject = request.form.get("subject", "")
    note_title = request.form.get("note_title", subject)
    explanation = btai.explain_notes(content, u["interests"], u["academic_level"])
    return render_template("ai_explain.html", user=u, explanation=explanation,
                           subject=subject, note_title=note_title,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/video", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_video():
    u = current_user()
    if request.method == "POST":
        subject = request.form.get("subject", "")
        topic = request.form.get("topic", "")
    else:
        subject = request.args.get("subject", "")
        topic = request.args.get("topic", "")
    video = btai.recommend_video(subject, topic, u["interests"])
    return render_template("video.html", user=u, video=video, subject=subject,
                           ai_enabled=btai.ai_enabled())


# ---------------------------------------------------------------------------
# MUSIC FAVORITES + BREAK PLAYLIST (autoplay + length-aware)
# ---------------------------------------------------------------------------
@app.route("/ai/music")
@login_required
@role_required("school_student", "independent")
def ai_music():
    u = current_user()
    favs = db.list_music_favorites(u["id"])
    return render_template("music_home.html", user=u, favorites=favs,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/music/favorite", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_music_favorite():
    u = current_user()
    name = request.form.get("name", "")
    kind = request.form.get("kind", "artist")
    if name.strip():
        db.add_music_favorite(u["id"], name, kind)
        flash(f"Added '{name.strip()}' to your favourites.", "success")
    return redirect(url_for("ai_music"))


@app.route("/ai/music/favorite/<int:fid>/delete", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_music_favorite_delete(fid):
    db.delete_music_favorite(fid)
    return redirect(url_for("ai_music"))


@app.route("/ai/break", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_break():
    """Auto-generated break playlist from favorites, autoplay + length-aware."""
    u = current_user()
    favs = db.list_music_favorites(u["id"])
    break_minutes = u.get("break_length") or 15
    if request.method == "POST":
        m = request.form.get("minutes")
        try:
            break_minutes = int(m)
        except Exception:
            pass
    playlist = btai.break_playlist(favs, break_minutes, u["interests"])
    return render_template("break.html", user=u, playlist=playlist,
                           favorites=favs, break_minutes=break_minutes,
                           ai_enabled=btai.ai_enabled())


@app.route("/ai/playlist", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_playlist():
    u = current_user()
    mode = request.form.get("mode") if request.method == "POST" else request.args.get("mode", "focus")
    subject = request.form.get("subject") if request.method == "POST" else ""
    mode = mode if mode in ("focus", "break") else "focus"
    songs = btai.recommend_playlist(u["interests"], mode)
    return render_template("playlist.html", user=u, songs=songs, mode=mode,
                           subject=subject, ai_enabled=btai.ai_enabled())


# ---------------------------------------------------------------------------
# BOOK UPLOAD (up to 25MB) with progress + SOURCES library
# ---------------------------------------------------------------------------
@app.route("/book/upload", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def book_upload():
    u = current_user()
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Please select a book file to upload.", "error")
        return redirect(url_for("student_home"))
    size = file.seek(0, 2); file.seek(0)
    if not title:
        title = file.filename.rsplit(".", 1)[0]
    # save the file
    safe_name = f"u{u['id']}_{int(datetime.datetime.now().timestamp())}_{file.filename.replace(' ','_')}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
    file.save(path)
    # extract text
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext == "pdf":
        text = _extract_pdf_file(path)
    elif ext in ("txt", "md"):
        text = open(path, encoding="utf-8", errors="ignore").read()
    else:
        # fallback: try pdf extraction or decode as text
        try:
            text = _extract_pdf_file(path)
        except Exception:
            text = open(path, encoding="utf-8", errors="ignore").read()
    if not text or not text.strip():
        flash("Could not read any text from that file. Upload a PDF or text file.", "error")
        return redirect(url_for("student_home"))
    # create note + chunks
    nid = db.add_note(title=title, subject=subject or "General", category="notes",
                      owner_id=u["id"], owner_role=u["role"], class_id=u["class_id"],
                      content=text, status="processing")
    chunks = ai.chunk_content(text)
    db.save_chunks(nid, subject or "General", chunks)
    db.set_note_status(nid, "active", chunk_count=len(chunks))
    if subject and subject not in db.user_subjects(u["id"]):
        db.set_user_subjects(u["id"], db.user_subjects(u["id"]) + [subject])
    bid = db.add_book(u["id"], title, subject or "General", file.filename, size)
    db.set_book_status(bid, "active", note_id=nid)
    flash(f"'{title}' uploaded ({size//1024} KB) and indexed into {len(chunks)} concepts.", "success")
    return redirect(url_for("student_sources"))


def _extract_pdf_file(path):
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in r.pages).strip()
    except Exception:
        # fallback: read as text (works for text-like files; PDFs without pypdf won't parse)
        return open(path, encoding="utf-8", errors="ignore").read()[:50000]


@app.route("/student/sources")
@login_required
@role_required("school_student", "independent")
def student_sources():
    u = current_user()
    books = db.list_books(u["id"])
    return render_template("sources.html", user=u, books=books)


@app.route("/book/<int:bid>/delete", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def book_delete(bid):
    b = db.get_book(bid)
    if b and b["user_id"] == current_user()["id"]:
        if b["note_id"]:
            db.delete_note(b["note_id"])
        db.delete_book(bid)
        flash("Book removed from your sources.", "success")
    return redirect(url_for("student_sources"))


# ---------------------------------------------------------------------------
# FRIENDLY INTERACTIVE AI CHAT (behaviour-based gating)
# ---------------------------------------------------------------------------
@app.route("/ai/talk", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_talk():
    if request.method == "GET":
        u = current_user()
        subject = request.args.get("subject", "")
        all_subjects = db.subjects_for_student(u)
        return render_template("talk_form.html", user=u, subject=subject,
                               all_subjects=all_subjects, ai_enabled=btai.ai_enabled())
    """Interactive, friendly AI chat with behaviour-based gating."""
    u = current_user()
    subject = request.form.get("subject", "")
    message = request.form.get("message", "").strip()
    # build notes context
    context = "\n".join(c["content"] for c in curriculum(subject)) if curriculum(subject) else ""
    ai_state = db.get_ai_state(u["id"]) or {"casual_count": 0}
    reply, action = btai.chat_interactive(message, subject, context, u, ai_state)
    # persist state
    if action == "exam":
        db.set_ai_state(u["id"], casual_count=0,
                        cooldown_until=(datetime.datetime.now() + datetime.timedelta(hours=8)).isoformat())
    elif action == "cooldown":
        pass
    else:
        new_casual = int(ai_state.get("casual_count", 0) or 0)
        # reset casual on educational questions
        new_casual = 0 if btai._is_educational(message) else new_casual
        db.set_ai_state(u["id"], casual_count=new_casual, last_casual=datetime.datetime.now().isoformat())
    return render_template("talk.html", user=u, subject=subject, message=message,
                           reply=reply, action=action, ai_enabled=btai.ai_enabled())


# ---------------------------------------------------------------------------
# SUBJECT SWITCHER + CROSS-SUBJECT EXPLANATION
# ---------------------------------------------------------------------------
@app.route("/learn/<subject>/cross/<strong_subject>")
@login_required
@role_required("school_student", "independent")
def learn_cross_subject(subject, strong_subject):
    """Explain current subject's topic using examples from a strong subject."""
    u = current_user()
    course = curriculum(subject)
    if not course:
        return redirect(url_for("learn", subject=subject))
    prog = db.get_progress(u["id"], subject)
    idx = prog["current_chunk"] if prog else 0
    idx = min(idx, len(course) - 1)
    topic = course[idx]["title"]
    strong_content = "\n".join(c["content"] for c in curriculum(strong_subject)) if curriculum(strong_subject) else ""
    explanation = btai.cross_subject_explain(topic, subject, strong_subject, strong_content)
    return render_template("cross_explain.html", user=u, subject=subject,
                           strong_subject=strong_subject, topic=topic, explanation=explanation,
                           ai_enabled=btai.ai_enabled())


# ---------------------------------------------------------------------------
# BT AI — quizzes, progress, exam sim, reminders (new features)
# ---------------------------------------------------------------------------
@app.route("/ai/quiz/<subject>", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def ai_quiz(subject):
    """AI-generated quiz from the student's notes."""
    u = current_user()
    context = "\n".join(c["content"] for c in curriculum(subject)) if curriculum(subject) else ""
    questions = []
    ai_note = None
    if request.method == "POST":
        num = int(request.form.get("num", 5))
        questions = btai.generate_quiz(subject, context, u["interests"], num, u.get("language") or "en")
        session[f"ai_quiz_{subject}"] = questions
        if btai.ai_enabled():
            ai_note = "BT AI wrote these questions from your notes."
        else:
            ai_note = "Quiz generated (BT AI fallback engine — add GROQ_API_KEY for AI-written questions)."
    return render_template("quiz.html", user=u, subject=subject, questions=questions,
                           ai_note=ai_note, ai_enabled=btai.ai_enabled())


@app.route("/ai/quiz/<subject>/answer", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def ai_quiz_answer(subject):
    u = current_user()
    qs = session.get(f"ai_quiz_{subject}", [])
    qid = int(request.form.get("qid"))
    chosen = int(request.form.get("choice"))
    if 0 <= qid < len(qs):
        q = qs[qid]
        correct = chosen == q["answer_index"]
        db.log_attempt(u["id"], -1 - qid, subject, -2, 1 if correct else 0)
        flash("Correct!" if correct else f"Not quite. The answer was {q['options'][q['answer_index']]}.",
              "success" if correct else "error")
    return redirect(url_for("ai_quiz", subject=subject))


@app.route("/ai/progress")
@login_required
@role_required("school_student", "independent")
def ai_progress():
    """Progress dashboard: accuracy, concepts, streak per subject."""
    u = current_user()
    subjects = db.subjects_for_student(u)
    data = []
    for subj in subjects:
        atts = db.attempts_for_user_subject(u["id"], subj)
        total = len(atts)
        correct = sum(1 for a in atts if a["correct"])
        done = db.completed_concepts(u["id"], subj)
        total_concepts = len(curriculum(subj))
        data.append({"subject": subj, "total": total, "correct": correct,
                     "accuracy": round(correct * 100 / total) if total else 0,
                     "mastered": len(done), "concepts": total_concepts,
                     "elo": u["elo"], "streak": u["streak"]})
    return render_template("progress.html", user=u, data=data)


@app.route("/ai/reminder")
@login_required
@role_required("school_student", "independent")
def ai_reminder():
    u = current_user()
    sched = db.get_schedule(u["id"])
    state = ai.schedule_state(sched, datetime.datetime.now()) if sched else {"next": None}
    message = btai.study_reminder(state, u["name"].split()[0])
    return render_template("reminder.html", user=u, message=message)


@app.route("/exam/<subject>", methods=["GET", "POST"])
@login_required
@role_required("school_student", "independent")
def exam(subject):
    """Timed exam simulation from past papers."""
    u = current_user()
    papers, qs = past_papers(subject)
    if not qs:
        return render_template("learn_empty.html", subject=subject)
    import random
    if request.method == "POST":
        qid = int(request.form.get("qid"))
        chosen = int(request.form.get("choice"))
        exam_answers = session.get(f"exam_{subject}", {})
        exam_answers[str(qid)] = chosen
        session[f"exam_{subject}"] = exam_answers
        return redirect(url_for("exam", subject=subject, qid=qid))
    # pick question based on query param or first unanswered
    cur_qid = request.args.get("qid")
    if cur_qid and int(cur_qid) in [q["id"] for q in qs]:
        idx = next(i for i, q in enumerate(qs) if q["id"] == int(cur_qid))
    else:
        exam_answers = session.get(f"exam_{subject}", {})
        # find first unanswered
        idx = next((i for i, q in enumerate(qs) if str(q["id"]) not in exam_answers), 0)
    question = qs[idx]
    total = len(qs)
    answered = len(session.get(f"exam_{subject}", {}))
    return render_template("exam.html", user=u, subject=subject, question=question,
                           total=total, answered=answered, idx=idx)


@app.route("/exam/<subject>/submit", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def exam_submit(subject):
    """Score the exam simulation."""
    u = current_user()
    papers, qs = past_papers(subject)
    exam_answers = session.get(f"exam_{subject}", {})
    correct = 0
    for q in qs:
        if str(q["id"]) in exam_answers and exam_answers[str(q["id"])] == q["answer_index"]:
            correct += 1
            db.log_attempt(u["id"], q["id"], subject, -1, 1)
        else:
            db.log_attempt(u["id"], q["id"], subject, -1, 0)
    total = len(qs)
    feedback = btai.exam_feedback(subject, correct, total)
    # ELO reward
    db.update_user(u["id"], elo=u["elo"] + round(correct * 3), points=u["points"] + correct)
    session.pop(f"exam_{subject}", None)
    return render_template("exam_result.html", user=u, subject=subject, correct=correct,
                           total=total, feedback=feedback)


@app.route("/teacher/ai-insights")
@login_required
@role_required("teacher")
def teacher_ai_insights():
    """Teacher-facing AI summary of class performance."""
    u = current_user()
    links, sel = teacher_context()
    insights = []
    if sel:
        class_id, subject = sel["class_id"], sel["subject"]
        health = db.class_health(class_id, subject)
        weak_items = db.list_weaknesses_for_subject(class_id, subject)
        students = db.students_in_class(class_id)
        summary = btai.class_summary(subject, health, weak_items[:5], len(students),
                                     language=u.get("language") or "en")
        insights.append({"subject": subject, "health": health, "summary": summary,
                         "weak_items": weak_items})
    return render_template("teacher/ai_insights.html", user=u, links=links, sel=sel,
                           insights=insights, ai_enabled=btai.ai_enabled(),
                           notifications=teacher_notification_count())


@app.route("/practice/<subject>")
@login_required
@role_required("school_student", "independent")
def practice(subject):
    u = current_user()
    touch_streak(db.get_user(u["id"]))
    u = db.get_user(u["id"])
    papers, qs = past_papers(subject)
    feedback = session.pop("practice_feedback", None)
    return render_template("practice.html", user=u, subject=subject, papers=papers, qs=qs, feedback=feedback)


@app.route("/practice/<subject>/answer", methods=["POST"])
@login_required
@role_required("school_student", "independent")
def practice_answer(subject):
    u = current_user()
    qid = int(request.form.get("qid"))
    chosen = int(request.form.get("choice"))
    # find question
    papers, qs = past_papers(subject)
    q = next((x for x in qs if x["id"] == qid), None)
    if q:
        correct = chosen == q["answer_index"]
        db.log_attempt(u["id"], qid, subject, -1, 1 if correct else 0)
        if correct:
            db.update_user(u["id"], elo=u["elo"] + 2, points=u["points"] + 1)
            msg = "Correct! +2 ELO."
        else:
            db.update_user(u["id"], elo=max(800, u["elo"] - 1))
            msg = "Not quite. Review the notes and try again."
    else:
        msg = "Question not found."
    session["practice_feedback"] = {"correct": correct if 'correct' in locals() else False,
                                    "msg": msg}
    return redirect(url_for("practice", subject=subject, qid=qid))


# ---------------------------------------------------------------------------
# RANKINGS  (Phase 5)
# ---------------------------------------------------------------------------
@app.route("/ranking")
@login_required
def ranking():
    u = current_user()
    rows = db.ranking()
    return render_template("ranking.html", user=u, rows=rows)


# ---------------------------------------------------------------------------
# API: quick demo actions
# ---------------------------------------------------------------------------
@app.route("/demo/time", methods=["GET"])
def demo_time():
    return jsonify({"hour": datetime.datetime.now().hour})


@app.route("/healthz", methods=["GET"])
def healthz():
    """Render health check: confirm the database is reachable."""
    try:
        db.user_by_email("healthz-probe@none")
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "db-unreachable"}), 500


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404,
                           title="Page not found",
                           message="The page you're looking for doesn't exist."), 404


@app.errorhandler(500)
def internal_error(e):
    if request.path.startswith(("/healthz",)):
        return jsonify({"status": "error"}), 500
    return render_template("error.html", code=500,
                           title="Something went wrong",
                           message="An unexpected internal error occurred. Please try again."), 500


# ---------------------------------------------------------------------------
def bootstrap_admin():
    """Create the initial admin account from environment variables (launch mode).
    No demo accounts are ever created automatically."""
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    pw = os.environ.get("ADMIN_PASSWORD") or ""
    name = os.environ.get("ADMIN_NAME") or "Administrator"
    if email and pw and not db.user_by_email(email):
        try:
            db.create_user(name=name, email=email,
                           password_hash=generate_password_hash(pw),
                           role="admin", must_change_password=0, onboarded=1)
            print(f"[bootstrap] Admin account created for {email}")
        except Exception as e:  # race-safe under multiple gunicorn workers
            print(f"[bootstrap] Admin create skipped (already exists / {e})")


# Initialize the database schema and (optionally) the admin account at import
# time so production servers (gunicorn) have the schema ready on start.
db.init_db()
bootstrap_admin()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
