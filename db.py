"""
BT LEARNING — database layer.
Backed by SQLAlchemy Core. Uses PostgreSQL when DATABASE_URL is set
(production / Render), otherwise a local SQLite file (development / preview).

The same public functions work on both engines; all SQL uses portable named
parameters and ON CONFLICT / RETURNING syntax supported by both.
"""
import os
import json
import datetime

from sqlalchemy import create_engine, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = bool(DATABASE_URL)

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DB_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "bt.db"))
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _norm(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    return v


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_row(m):
    return {k: _norm(v) for k, v in m.items()} if m else None


def _norm_rows(rows):
    return [_norm_row(dict(r._mapping)) for r in rows]


def _fetch(sql, params=None):
    with engine.connect() as conn:
        return _norm_rows(conn.execute(text(sql), params or {}))


def _fetch_one(sql, params=None):
    with engine.connect() as conn:
        r = conn.execute(text(sql), params or {}).mappings().first()
        return _norm_row(dict(r)) if r else None


def _execute(sql, params=None):
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def _insert_id(sql, params=None):
    with engine.begin() as conn:
        return conn.execute(text(sql), params or {}).scalar()


def get_conn():
    """Compatibility connection (used by legacy call sites)."""
    return engine.connect()


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------
def init_db():
    if IS_PG:
        for st in _PG_DDL:
            _execute(st)
    else:
        for st in _SQLITE_DDL:
            _execute(st)


_SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE, student_id TEXT UNIQUE,
        password_hash TEXT NOT NULL, role TEXT NOT NULL, class_id INTEGER,
        interests TEXT DEFAULT '', must_change_password INTEGER DEFAULT 0,
        elo INTEGER DEFAULT 1200, streak INTEGER DEFAULT 0, last_active DATE,
        study_start_hour INTEGER DEFAULT 0, study_end_hour INTEGER DEFAULT 23,
        points INTEGER DEFAULT 0, academic_level TEXT DEFAULT '',
        blend_regional INTEGER DEFAULT 1, learning_mode TEXT DEFAULT 'video',
        session_length INTEGER DEFAULT 45, break_length INTEGER DEFAULT 15,
        onboarded INTEGER DEFAULT 0, language TEXT DEFAULT 'en', location TEXT DEFAULT '')""",
    "CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS teacher_classes (id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, class_id INTEGER NOT NULL, subject TEXT)",
    "CREATE TABLE IF NOT EXISTS class_subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL, subject TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS user_subjects (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subject TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, subject TEXT NOT NULL,
        category TEXT NOT NULL, owner_id INTEGER, owner_role TEXT DEFAULT 'teacher',
        class_id INTEGER, content TEXT, status TEXT DEFAULT 'active',
        enabled INTEGER DEFAULT 1, chunk_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')))""",
    "CREATE TABLE IF NOT EXISTS note_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL, subject TEXT NOT NULL, chunk_index INTEGER NOT NULL, title TEXT, content TEXT)",
    "CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY AUTOINCREMENT, chunk_id INTEGER NOT NULL, question TEXT, options TEXT, answer_index INTEGER)",
    """CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
        subject TEXT, concept_index INTEGER, correct INTEGER,
        created_at TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS weaknesses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subject TEXT, concept TEXT,
        fail_count INTEGER DEFAULT 0, resolved INTEGER DEFAULT 0, note TEXT,
        transcript TEXT, analogy TEXT, language_note TEXT,
        last_fail_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))""",
    """CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subject TEXT NOT NULL,
        current_chunk INTEGER DEFAULT 0, started_at TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, subject))""",
    """CREATE TABLE IF NOT EXISTS completed_concepts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subject TEXT, chunk_index INTEGER,
        passed_at TEXT DEFAULT (datetime('now')), UNIQUE(user_id, subject, chunk_index))""",
    """CREATE TABLE IF NOT EXISTS focus_log (
        user_id INTEGER NOT NULL, subject TEXT, active_seconds INTEGER DEFAULT 0,
        idle_seconds INTEGER DEFAULT 0, updated_at TEXT DEFAULT (datetime('now')),
        PRIMARY KEY(user_id, subject))""",
    "CREATE TABLE IF NOT EXISTS study_schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, day INTEGER NOT NULL, start_hour INTEGER NOT NULL, end_hour INTEGER NOT NULL, subject TEXT)",
    "CREATE TABLE IF NOT EXISTS music_favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT 'artist')",
    "CREATE TABLE IF NOT EXISTS books (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, subject TEXT, filename TEXT, size INTEGER, status TEXT DEFAULT 'processing', note_id INTEGER, created_at TEXT DEFAULT (datetime('now')))",
    "CREATE TABLE IF NOT EXISTS ai_state (user_id INTEGER PRIMARY KEY, casual_count INTEGER DEFAULT 0, last_casual TEXT, cooldown_until TEXT, good_streak INTEGER DEFAULT 0)",
]

_PG_DDL = [
    """CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE, student_id TEXT UNIQUE,
        password_hash TEXT NOT NULL, role TEXT NOT NULL, class_id INTEGER,
        interests TEXT DEFAULT '', must_change_password INTEGER DEFAULT 0,
        elo INTEGER DEFAULT 1200, streak INTEGER DEFAULT 0, last_active DATE,
        study_start_hour INTEGER DEFAULT 0, study_end_hour INTEGER DEFAULT 23,
        points INTEGER DEFAULT 0, academic_level TEXT DEFAULT '',
        blend_regional INTEGER DEFAULT 1, learning_mode TEXT DEFAULT 'video',
        session_length INTEGER DEFAULT 45, break_length INTEGER DEFAULT 15,
        onboarded INTEGER DEFAULT 0, language TEXT DEFAULT 'en', location TEXT DEFAULT '')""",
    "CREATE TABLE IF NOT EXISTS classes (id SERIAL PRIMARY KEY, name TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS teacher_classes (id SERIAL PRIMARY KEY, teacher_id INTEGER NOT NULL, class_id INTEGER NOT NULL, subject TEXT)",
    "CREATE TABLE IF NOT EXISTS class_subjects (id SERIAL PRIMARY KEY, class_id INTEGER NOT NULL, subject TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS user_subjects (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL,
        category TEXT NOT NULL, owner_id INTEGER, owner_role TEXT DEFAULT 'teacher',
        class_id INTEGER, content TEXT, status TEXT DEFAULT 'active',
        enabled INTEGER DEFAULT 1, chunk_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT now())""",
    "CREATE TABLE IF NOT EXISTS note_chunks (id SERIAL PRIMARY KEY, note_id INTEGER NOT NULL, subject TEXT NOT NULL, chunk_index INTEGER NOT NULL, title TEXT, content TEXT)",
    "CREATE TABLE IF NOT EXISTS questions (id SERIAL PRIMARY KEY, chunk_id INTEGER NOT NULL, question TEXT, options TEXT, answer_index INTEGER)",
    """CREATE TABLE IF NOT EXISTS quiz_attempts (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, question_id INTEGER NOT NULL,
        subject TEXT, concept_index INTEGER, correct INTEGER,
        created_at TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS weaknesses (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT, concept TEXT,
        fail_count INTEGER DEFAULT 0, resolved INTEGER DEFAULT 0, note TEXT,
        transcript TEXT, analogy TEXT, language_note TEXT,
        last_fail_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS progress (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT NOT NULL,
        current_chunk INTEGER DEFAULT 0, started_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE(user_id, subject))""",
    """CREATE TABLE IF NOT EXISTS completed_concepts (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT, chunk_index INTEGER,
        passed_at TIMESTAMPTZ DEFAULT now(), UNIQUE(user_id, subject, chunk_index))""",
    """CREATE TABLE IF NOT EXISTS focus_log (
        user_id INTEGER NOT NULL, subject TEXT, active_seconds INTEGER DEFAULT 0,
        idle_seconds INTEGER DEFAULT 0, updated_at TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY(user_id, subject))""",
    "CREATE TABLE IF NOT EXISTS study_schedule (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, day INTEGER NOT NULL, start_hour INTEGER NOT NULL, end_hour INTEGER NOT NULL, subject TEXT)",
    "CREATE TABLE IF NOT EXISTS music_favorites (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT 'artist')",
    "CREATE TABLE IF NOT EXISTS books (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, title TEXT NOT NULL, subject TEXT, filename TEXT, size INTEGER, status TEXT DEFAULT 'processing', note_id INTEGER, created_at TIMESTAMPTZ DEFAULT now())",
    "CREATE TABLE IF NOT EXISTS ai_state (user_id INTEGER PRIMARY KEY, casual_count INTEGER DEFAULT 0, last_casual TEXT, cooldown_until TEXT, good_streak INTEGER DEFAULT 0)",
]


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
def user_by_student_id(sid):
    return _fetch_one("SELECT * FROM users WHERE student_id=:s", {"s": sid})


def user_by_email(email):
    return _fetch_one("SELECT * FROM users WHERE email=:e", {"e": email})


def get_user(uid):
    return _fetch_one("SELECT * FROM users WHERE id=:i", {"i": uid})


def create_user(**kw):
    cols = list(kw.keys())
    binds = {c: kw[c] for c in cols}
    sql = (f"INSERT INTO users ({', '.join(cols)}) VALUES "
           f"({', '.join(':' + c for c in cols)}) RETURNING id")
    return _insert_id(sql, binds)


def update_user(uid, **kw):
    if not kw:
        return
    sets = ", ".join(f"{k}=:{k}" for k in kw)
    params = dict(kw)
    params["uid"] = uid
    _execute(f"UPDATE users SET {sets} WHERE id=:uid", params)


def list_users(role=None):
    if role:
        return _fetch("SELECT * FROM users WHERE role=:r ORDER BY name", {"r": role})
    return _fetch("SELECT * FROM users ORDER BY name")


def list_teachers():
    return list_users("teacher")


# ---------------------------------------------------------------------------
# classes / subjects
# ---------------------------------------------------------------------------
def list_classes():
    return _fetch("SELECT * FROM classes ORDER BY name")


def get_class(cid):
    return _fetch_one("SELECT * FROM classes WHERE id=:i", {"i": cid})


def get_class_by_name(name):
    r = _fetch_one("SELECT id FROM classes WHERE name=:n", {"n": name})
    return r["id"] if r else None


def create_class(name):
    return _insert_id("INSERT INTO classes (name) VALUES (:n) RETURNING id", {"n": name})


def set_class_subjects(class_id, subjects):
    _execute("DELETE FROM class_subjects WHERE class_id=:c", {"c": class_id})
    for s in subjects:
        _execute("INSERT INTO class_subjects (class_id, subject) VALUES (:c,:s)",
                 {"c": class_id, "s": s})


def class_subjects(class_id):
    return [r["subject"] for r in
            _fetch("SELECT subject FROM class_subjects WHERE class_id=:c", {"c": class_id})]


def set_user_subjects(user_id, subjects):
    _execute("DELETE FROM user_subjects WHERE user_id=:u", {"u": user_id})
    for s in subjects:
        _execute("INSERT INTO user_subjects (user_id, subject) VALUES (:u,:s)",
                 {"u": user_id, "s": s})


def user_subjects(user_id):
    return [r["subject"] for r in
            _fetch("SELECT subject FROM user_subjects WHERE user_id=:u", {"u": user_id})]


def subjects_for_student(user):
    if user["role"] == "school_student" and user["class_id"]:
        subs = class_subjects(user["class_id"])
        if subs:
            return subs
    return user_subjects(user["id"])


# ---------------------------------------------------------------------------
# notes / curriculum
# ---------------------------------------------------------------------------
def add_note(title, subject, category, owner_id, owner_role, class_id, content, status="processing"):
    return _insert_id(
        "INSERT INTO notes (title, subject, category, owner_id, owner_role, class_id, content, status) "
        "VALUES (:t,:s,:c,:o,:or,:cl,:co,:st) RETURNING id",
        {"t": title, "s": subject, "c": category, "o": owner_id, "or": owner_role,
         "cl": class_id, "co": content, "st": status})


def set_note_status(nid, status, chunk_count=None):
    if chunk_count is not None:
        _execute("UPDATE notes SET status=:s, chunk_count=:cc WHERE id=:i",
                 {"s": status, "cc": chunk_count, "i": nid})
    else:
        _execute("UPDATE notes SET status=:s WHERE id=:i", {"s": status, "i": nid})


def set_note_enabled(nid, enabled):
    _execute("UPDATE notes SET enabled=:e WHERE id=:i", {"e": 1 if enabled else 0, "i": nid})


def get_note(nid):
    return _fetch_one("SELECT * FROM notes WHERE id=:i", {"i": nid})


def list_notes(subject=None, category=None, class_id=None):
    sql = "SELECT * FROM notes WHERE 1=1"
    params = {}
    if subject:
        sql += " AND subject=:s"
        params["s"] = subject
    if category:
        sql += " AND category=:c"
        params["c"] = category
    if class_id:
        sql += " AND class_id=:cl"
        params["cl"] = class_id
    sql += " ORDER BY created_at DESC"
    return _fetch(sql, params)


def delete_note(nid):
    _execute("DELETE FROM notes WHERE id=:i", {"i": nid})


def save_chunks(note_id, subject, chunks):
    from ai_engine import generate_questions
    for i, ch in enumerate(chunks):
        chunk_id = _insert_id(
            "INSERT INTO note_chunks (note_id, subject, chunk_index, title, content) "
            "VALUES (:n,:s,:i,:t,:c) RETURNING id",
            {"n": note_id, "s": subject, "i": i,
             "t": ch.get("title", f"Concept {i+1}"), "c": ch["content"]})
        qs = generate_questions(ch["content"], all_chunks=chunks, seed=i, limit=5)
        for q in qs:
            _execute("INSERT INTO questions (chunk_id, question, options, answer_index) "
                     "VALUES (:c,:q,:o,:a)",
                     {"c": chunk_id, "q": q["question"],
                      "o": json.dumps(q["options"]), "a": q["answer_index"]})


def chunks_for_note(note_id):
    return _fetch("SELECT * FROM note_chunks WHERE note_id=:n ORDER BY chunk_index",
                  {"n": note_id})


def get_chunk(cid):
    return _fetch_one("SELECT * FROM note_chunks WHERE id=:i", {"i": cid})


def questions_for_chunk(chunk_id):
    rows = _fetch("SELECT * FROM questions WHERE chunk_id=:c", {"c": chunk_id})
    out = []
    for r in rows:
        out.append({"id": r["id"], "question": r["question"],
                    "options": json.loads(r["options"]), "answer_index": r["answer_index"]})
    return out


def log_attempt(user_id, question_id, subject, concept_index, correct):
    _execute("INSERT INTO quiz_attempts (user_id, question_id, subject, concept_index, correct) "
             "VALUES (:u,:q,:s,:c,:ok)",
             {"u": user_id, "q": question_id, "s": subject, "c": concept_index, "ok": correct})


def all_questions_for_subject(subject):
    rows = _fetch("""
        SELECT q.* FROM questions q
        JOIN note_chunks nc ON nc.id = q.chunk_id
        WHERE nc.subject=:s ORDER BY q.id""", {"s": subject})
    return [{"id": r["id"], "question": r["question"],
             "options": json.loads(r["options"]), "answer_index": r["answer_index"]} for r in rows]


# ---------------------------------------------------------------------------
# progress / completion
# ---------------------------------------------------------------------------
def get_progress(user_id, subject):
    return _fetch_one("SELECT * FROM progress WHERE user_id=:u AND subject=:s",
                      {"u": user_id, "s": subject})


def set_progress_current(user_id, subject, chunk_index):
    _execute("""INSERT INTO progress (user_id, subject, current_chunk) VALUES (:u,:s,:c)
                ON CONFLICT(user_id, subject) DO UPDATE SET current_chunk=excluded.current_chunk""",
             {"u": user_id, "s": subject, "c": chunk_index})


def mark_concept_complete(user_id, subject, chunk_index):
    _execute("""INSERT INTO completed_concepts (user_id, subject, chunk_index) VALUES (:u,:s,:c)
                ON CONFLICT(user_id, subject, chunk_index) DO NOTHING""",
             {"u": user_id, "s": subject, "c": chunk_index})


def completed_concepts(user_id, subject):
    return [r["chunk_index"] for r in _fetch(
        "SELECT chunk_index FROM completed_concepts WHERE user_id=:u AND subject=:s",
        {"u": user_id, "s": subject})]


# ---------------------------------------------------------------------------
# weaknesses
# ---------------------------------------------------------------------------
def upsert_weakness(user_id, subject, concept, add=1, transcript=None, analogy=None,
                    language_note=None):
    row = _fetch_one("""SELECT * FROM weaknesses WHERE user_id=:u AND subject=:s
                        AND concept=:c AND resolved=0""",
                     {"u": user_id, "s": subject, "c": concept})
    if row:
        old_t = row["transcript"] or ""
        new_t = (old_t + "\n" + transcript).strip() if transcript else old_t
        _execute("""UPDATE weaknesses SET fail_count=fail_count+:add, updated_at=:u,
                      last_fail_at=:lf, transcript=:t, analogy=:a, language_note=:l
                      WHERE id=:id""",
                 {"add": add, "t": new_t, "a": analogy or row["analogy"],
                  "l": language_note or row["language_note"], "id": row["id"],
                  "u": _now_str(), "lf": _now_str()})
        return row["id"]
    else:
        return _insert_id("""INSERT INTO weaknesses
                              (user_id, subject, concept, fail_count, transcript, analogy, language_note)
                              VALUES (:u,:s,:c,:add,:t,:a,:l) RETURNING id""",
                          {"u": user_id, "s": subject, "c": concept, "add": add,
                           "t": transcript, "a": analogy, "l": language_note})


def resolve_weakness(wid):
    _execute("UPDATE weaknesses SET resolved=1 WHERE id=:i", {"i": wid})


def resolve_weakness_by(user_id, subject, concept):
    _execute("""UPDATE weaknesses SET resolved=1 WHERE user_id=:u AND subject=:s
                AND concept=:c AND resolved=0""",
             {"u": user_id, "s": subject, "c": concept})


def concept_failure_count(user_id, subject, idx):
    rows = _fetch("""SELECT concept_index, correct FROM quiz_attempts
                     WHERE user_id=:u AND subject=:s AND concept_index=:c""",
                  {"u": user_id, "s": subject, "c": idx})
    return sum(1 for r in rows if r["correct"] == 0)


def list_weaknesses(class_id=None, user_id=None, all_students=False):
    q = """SELECT w.*, u.name AS student_name, u.student_id, u.class_id,
                  u.role AS student_role
           FROM weaknesses w JOIN users u ON u.id = w.user_id WHERE w.resolved=0"""
    params = {}
    if user_id is not None:
        q += " AND w.user_id=:uid"
        params["uid"] = user_id
    if all_students and class_id is not None:
        q += " AND u.class_id=:cid"
        params["cid"] = class_id
    q += " ORDER BY w.fail_count DESC"
    return _fetch(q, params)


def weakness_for_student_subject(user_id, subject):
    return _fetch("""SELECT * FROM weaknesses WHERE user_id=:u AND subject=:s AND resolved=0
                     ORDER BY fail_count DESC, updated_at DESC""",
                  {"u": user_id, "s": subject})


def list_weaknesses_for_subject(class_id, subject):
    return _fetch("""SELECT w.*, u.name AS student_name, u.student_id, u.class_id, u.role AS student_role
                     FROM weaknesses w JOIN users u ON u.id = w.user_id
                     WHERE w.resolved=0 AND u.class_id=:c AND w.subject=:s AND w.fail_count>0
                     ORDER BY w.fail_count DESC, w.updated_at DESC""",
                  {"c": class_id, "s": subject})


def set_study_hours(user_id, start, end):
    update_user(user_id, study_start_hour=start, study_end_hour=end)


def ranking():
    return _fetch("""SELECT * FROM users
                     WHERE role IN ('school_student','independent')
                     ORDER BY elo DESC""")


# ---------------------------------------------------------------------------
# teacher dashboard
# ---------------------------------------------------------------------------
def set_teacher_classes(teacher_id, links):
    _execute("DELETE FROM teacher_classes WHERE teacher_id=:t", {"t": teacher_id})
    for cid, sub in links:
        _execute("INSERT INTO teacher_classes (teacher_id, class_id, subject) VALUES (:t,:c,:s)",
                 {"t": teacher_id, "c": cid, "s": sub})


def teacher_classes(teacher_id):
    return _fetch("""SELECT tc.*, c.name AS class_name FROM teacher_classes tc
                     JOIN classes c ON c.id = tc.class_id
                     WHERE tc.teacher_id=:t ORDER BY c.name, tc.subject""", {"t": teacher_id})


def students_in_class(class_id):
    return _fetch("""SELECT * FROM users WHERE role='school_student' AND class_id=:c
                     ORDER BY name""", {"c": class_id})


def attempts_for_user_subject(user_id, subject):
    return _fetch("""SELECT * FROM quiz_attempts WHERE user_id=:u AND subject=:s
                     AND concept_index>=0 ORDER BY created_at""",
                  {"u": user_id, "s": subject})


def class_health(class_id, subject):
    students = students_in_class(class_id)
    total = 0
    correct = 0
    for st in students:
        for a in attempts_for_user_subject(st["id"], subject):
            total += 1
            if a["correct"]:
                correct += 1
    if total == 0:
        return None
    return round(correct * 100 / total)


def class_action_items(class_id, subject, threshold=3):
    items = [w for w in list_weaknesses_for_subject(class_id, subject)
             if w["fail_count"] >= threshold]
    items.sort(key=lambda w: w["fail_count"], reverse=True)
    return items


def reset_student_password(user_id, temp_pw="btlearn123"):
    from werkzeug.security import generate_password_hash
    update_user(user_id, password_hash=generate_password_hash(temp_pw),
                must_change_password=1)


# ---------------------------------------------------------------------------
# focus
# ---------------------------------------------------------------------------
def add_focus(user_id, subject, active_seconds, idle_seconds):
    _execute("""INSERT INTO focus_log (user_id, subject, active_seconds, idle_seconds)
                VALUES (:u,:s,:a,:i)
                ON CONFLICT(user_id, subject) DO UPDATE SET
                  active_seconds = focus_log.active_seconds + excluded.active_seconds,
                  idle_seconds   = focus_log.idle_seconds + excluded.idle_seconds,
                  updated_at     = :now""",
             {"u": user_id, "s": subject, "a": active_seconds, "i": idle_seconds,
              "now": _now_str()})


def focus_for(user_id, subject):
    return _fetch_one("SELECT * FROM focus_log WHERE user_id=:u AND subject=:s",
                      {"u": user_id, "s": subject})


# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------
def set_schedule(user_id, blocks):
    _execute("DELETE FROM study_schedule WHERE user_id=:u", {"u": user_id})
    for day, start, end, subject in blocks:
        _execute("INSERT INTO study_schedule (user_id, day, start_hour, end_hour, subject) "
                 "VALUES (:u,:d,:s,:e,:sb)",
                 {"u": user_id, "d": day, "s": start, "e": end, "sb": subject})


def get_schedule(user_id):
    return _fetch("SELECT * FROM study_schedule WHERE user_id=:u ORDER BY day, start_hour",
                  {"u": user_id})


def schedule_blocks_for_day(user_id, day):
    return _fetch("SELECT * FROM study_schedule WHERE user_id=:u AND day=:d ORDER BY start_hour",
                  {"u": user_id, "d": day})


def weekly_hours(user_id):
    return sum(max(0, b["end_hour"] - b["start_hour"]) for b in get_schedule(user_id))


def db_schedule_all(user_id):
    return get_schedule(user_id)


# ---------------------------------------------------------------------------
# music favorites
# ---------------------------------------------------------------------------
def add_music_favorite(user_id, name, kind="artist"):
    name = name.strip()
    if not name:
        return
    if _fetch_one("SELECT id FROM music_favorites WHERE user_id=:u AND name=:n",
                  {"u": user_id, "n": name}):
        return
    _execute("INSERT INTO music_favorites (user_id, name, kind) VALUES (:u,:n,:k)",
             {"u": user_id, "n": name, "k": kind})


def list_music_favorites(user_id):
    return _fetch("SELECT * FROM music_favorites WHERE user_id=:u ORDER BY id", {"u": user_id})


def delete_music_favorite(fid):
    _execute("DELETE FROM music_favorites WHERE id=:i", {"i": fid})


# ---------------------------------------------------------------------------
# books / sources
# ---------------------------------------------------------------------------
def add_book(user_id, title, subject, filename, size, status="processing"):
    return _insert_id(
        "INSERT INTO books (user_id, title, subject, filename, size, status) "
        "VALUES (:u,:t,:s,:f,:z,:st) RETURNING id",
        {"u": user_id, "t": title, "s": subject, "f": filename, "z": size, "st": status})


def set_book_status(bid, status, note_id=None):
    if note_id is not None:
        _execute("UPDATE books SET status=:s, note_id=:n WHERE id=:i",
                 {"s": status, "n": note_id, "i": bid})
    else:
        _execute("UPDATE books SET status=:s WHERE id=:i", {"s": status, "i": bid})


def get_book(bid):
    return _fetch_one("SELECT * FROM books WHERE id=:i", {"i": bid})


def list_books(user_id):
    return _fetch("SELECT * FROM books WHERE user_id=:u ORDER BY created_at DESC", {"u": user_id})


def delete_book(bid):
    _execute("DELETE FROM books WHERE id=:i", {"i": bid})


# ---------------------------------------------------------------------------
# AI interaction state (casual talk gating)
# ---------------------------------------------------------------------------
def get_ai_state(user_id):
    return _fetch_one("SELECT * FROM ai_state WHERE user_id=:u", {"u": user_id})


def set_ai_state(user_id, **kw):
    if not kw:
        return
    row = get_ai_state(user_id)
    if row:
        sets = ", ".join(f"{k}=:{k}" for k in kw)
        params = dict(kw); params["u"] = user_id
        _execute(f"UPDATE ai_state SET {sets} WHERE user_id=:u", params)
    else:
        cols = ["user_id"] + list(kw.keys())
        binds = {"u": user_id, **kw}
        _execute(f"INSERT INTO ai_state ({', '.join(cols)}) VALUES "
                 f"(:u, {', '.join(':'+k for k in kw)})", binds)


def delete_user_completely(user_id):
    """Delete a user and all their associated data."""
    for table in ("music_favorites", "books", "ai_state", "study_schedule", "focus_log",
                  "completed_concepts", "progress", "weaknesses", "quiz_attempts",
                  "user_subjects"):
        try:
            _execute(f"DELETE FROM {table} WHERE user_id=:u", {"u": user_id})
        except Exception:
            pass
    # delete their notes
    notes = _fetch("SELECT id FROM notes WHERE owner_id=:u", {"u": user_id})
    for n in notes:
        _execute("DELETE FROM note_chunks WHERE note_id=:i", {"i": n["id"]})
        _execute("DELETE FROM notes WHERE id=:i", {"i": n["id"]})
    _execute("DELETE FROM users WHERE id=:u", {"u": user_id})
