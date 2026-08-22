"""
BT LEARNING — AI engine (simulated / rule-based, no external API).
Responsibilities:
  * Split uploaded notes into digestible concept chunks.
  * Auto-generate knowledge-check questions from the notes.
  * Personalize explanations using a student's listed interests.
  * Blend English with Shona expressions.
  * Detect weaknesses from repeated failures.
"""
import re
import random

# ---------------------------------------------------------------------------
# Shona expressions blended into tutoring
# ---------------------------------------------------------------------------
SHONA = {
    "welcome": "Mauya! Zvakanaka kunzwa nazvo.",
    "lets_start": "Ngatitangei. Tingamhanya?",
    "ready": "Zvakagadzirira!",
    "good": "Zvakanaka.",
    "great": "Hezvo! Wabata zvinhu.",
    "excellent": "Wakaita basa rakanaka!",
    "think": "Funga zvakadzama...",
    "try_again": "Edza zvakare, usatya kukanganisa.",
    "well_done": "Mabasa zvakanaka. Zvino tichienda mberi.",
    "concept": "Pfungwa",
    "next": "Ngatitendei kune inotevera pfungwa.",
    "not_study": "Haisi nguva yekudzidza izvozvi.",
    "come_back": "Dzokai nguva yadzo.",
    "check": "Ndatizorodza kuti tione kuti wanzwisisa here.",
    "keep_going": "Ramba uchiedza, uri munzira yakarurama.",
    "motivate": "Ungakwanise! Usazorega.",
    "first_try": "Wapfura padanda kutanga!",
    "mistake": "Zvakanaka kukanganisa — ndizvo zvinoita munhu anodzidza.",
}

# Analogy templates keyed by student interest. {{X}} = the concept being taught.
ANALOGIES = {
    "soccer": "Funga kuti {{X}} yakafanana nemutambo wenhabvu: kana usina nhanho yekutanga, haungakwanise kunyangira zvakanaka.",
    "music": "Funga kuti {{X}} yakafanana nemimhanzi — zvinhu zvinotevedzana sezvakaita madimikira erwiyo.",
    "farming": "Funga kuti {{X}} yakafanana nokurima: unoshandisa yakasviba nyika (vhu) sevhudzii, zvino munzira, zvinokura.",
    "cooking": "Funga kuti {{X}} yakafanana nokubika sadza — kana katsirakiro kazhinji, nguva yose inogadzirwa zvakanaka.",
    "tech": "Funga kuti {{X}} yakafanana nealgorithm yekombuta: danho rimwe nerimwe rinotevera pane rakapfuura.",
    "business": "Funga kuti {{X}} yakafanana nebizinesi: mabasa madiki anowana mibairo mikuru kana akaitwa nenzira kwayo.",
    "art": "Funga kuti {{X}} yakafanana nekuvhenekesa (mufananidzo): unotanga nechikonzwa (skeleton) wozoisa ruvara.",
    "sports": "Funga kuti {{X}} yakafanana nokudzidzira mutambo: kudzokorora zvishoma nezvishoma kunosimudzira.",
    "gaming": "Funga kuti {{X}} yakafanana nemutambo wevideo: uko nhanho imwe neimwe yauri kutamba inovhura inotevera.",
    "reading": "Funga kuti {{X}} yakafanana nokupara chitsauko: iwe unofanira kusvika pakupera kwechikamu chimwe usati watanga chakatevera.",
}

DEFAULT_ANALOGY = (
    "Funga kuti {{X}} yakafanana nekuvaka imba: unofanira kuva nehwaro (foundation) hwakasimba "
    "usati wawedzera madziro nedenga."
)


def _interest_key(interests):
    text = (interests or "").lower()
    for k in ANALOGIES:
        if k in text:
            return k
    return None


def greet(interests, hour, blend=True):
    parts = []
    if 5 <= hour < 12:
        parts.append("Good morning!" if not blend else "Mangwanani akanaka! Good morning.")
    elif 12 <= hour < 17:
        parts.append("Good afternoon!" if not blend else "Masikati akanaka! Good afternoon.")
    else:
        parts.append("Good evening!" if not blend else "Manheru akanaka! Good evening.")
    if blend:
        parts.append(SHONA["welcome"])
    ik = _interest_key(interests)
    if ik:
        parts.append(f"I can see you enjoy {ik.title()} — I'll use examples like that to make things clear.")
    if blend:
        parts.append(SHONA["lets_start"])
    return " ".join(parts)


def personalized_explain(concept, interests, blend=True):
    """Return a personalized lead-in for a concept, optionally blending English + Shona."""
    template = DEFAULT_ANALOGY
    ik = _interest_key(interests)
    if ik:
        template = ANALOGIES[ik]
    analogy = template.replace("{{X}}", f'"{concept}"')
    if blend:
        return (
            f"{SHONA['concept']} {SHONA['think']} "
            f"Here is how I want you to picture it: {analogy}"
        )
    return f"Here is how I want you to picture it: {analogy}"


def praise(first_try):
    if first_try:
        return f"{SHONA['first_try']} {SHONA['excellent']} You got that right on the first attempt — excellent!"
    return f"{SHONA['mistake']} But now you've got it — {SHONA['good']} Keep going."


def intervention_log(concept, interests):
    """Build the AI intervention record shown in the teacher's weakness report:
    the analogy used, whether Shona was blended in, and a transcript snippet."""
    analogy = personalized_explain(concept, interests)
    ik = _interest_key(interests)
    language_note = ("Pivoted to Shona expressions to aid understanding "
                     f"({ik} analogy used).") if ik else "Used a general analogy; Shona expressions blended in."
    transcript = (
        f"Student failed knowledge check on '{concept}'. AI responded: "
        f"\"{SHONA['try_again']} {SHONA['motivate']}\" then re-explained using {analogy}"
    )
    return {"analogy": analogy, "language_note": language_note, "transcript": transcript}


# ---------------------------------------------------------------------------
# Note ingestion: chunking
# ---------------------------------------------------------------------------
def split_sentences(text):
    # rough sentence splitter
    raw = re.split(r'(?<=[.!?])\s+', text.replace("\n", " "))
    return [s.strip() for s in raw if s.strip()]


def chunk_content(content):
    """Break long notes into small digestible concept chunks."""
    # normalize whitespace
    content = re.sub(r"[ \t]+", " ", content)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", content) if p.strip()]
    if not paragraphs:
        paragraphs = [content]
    chunks = []
    current = ""
    for p in paragraphs:
        if current and len(current) + len(p) > 500:
            chunks.append(current)
            current = p
        else:
            current = (current + " " + p) if current else p
    if current:
        chunks.append(current)
    if not chunks:
        chunks = [content]

    result = []
    for i, ch in enumerate(chunks):
        title = _chunk_title(ch, i)
        result.append({"title": title, "content": ch})
    return result


def _chunk_title(chunk, idx):
    sentences = split_sentences(chunk)
    if sentences:
        base = sentences[0]
        if len(base) > 60:
            base = base[:60].rsplit(" ", 1)[0] + "..."
        return f"Concept {idx+1}: {base}"
    return f"Concept {idx+1}"


# ---------------------------------------------------------------------------
# Question generation from notes
# ---------------------------------------------------------------------------
def _vocab(chunks):
    words = []
    for ch in chunks:
        content = ch["content"] if isinstance(ch, dict) else ch
        for m in re.findall(r"[A-Za-z]{5,}", content.lower()):
            words.append(m)
    # most common meaningful words
    from collections import Counter
    common = [w for w, c in Counter(words).most_common(40) if not _stop(w)]
    return common


def _stop(w):
    return w in {"which", "there", "their", "about", "would", "these", "other",
                 "could", "after", "first", "those", "where", "every", "under",
                 "because", "between", "through", "during", "before", "really",
                 "also", "then", "from", "with", "than", "they", "this", "that",
                 "have", "been", "will", "into", "your", "what", "when"}


def generate_questions(chunk_content, all_chunks=None, seed=0, limit=2):
    """Turn a chunk's sentences into simple fill-in-the-blank knowledge checks
    whose answers come ONLY from the uploaded notes."""
    rng = random.Random(seed)
    all_chunks = all_chunks or [{"content": chunk_content}]
    vocab = _vocab(all_chunks)
    sentences = split_sentences(chunk_content)
    questions = []
    for sent in sentences:
        if len(questions) >= limit:
            break
        tokens = re.findall(r"\b[A-Za-z]{5,}\b", sent)
        if len(tokens) < 3:
            continue
        # Pick a meaningful mid-sentence term (skip the very first token),
        # preferring medium-length topic words over generic connector words.
        pool = [w for w in tokens[1:]]
        pool = [w for w in pool if not _stop(w)]
        scored = sorted(pool, key=lambda w: (-(6 <= len(w) <= 9), -len(w)))
        # still allow a top-of-sentence word if nothing else
        cand = scored or tokens[1:]
        answer = cand[0]
        # build question with blank
        qtext = sent.replace(answer, "_____", 1)
        options = [answer]
        distractors = [w for w in vocab if w.lower() != answer.lower() and w not in options]
        rng.shuffle(distractors)
        options += distractors[:3]
        if len(options) < 2:
            continue
        rng.shuffle(options)
        ai = options.index(answer)
        questions.append({
            "question": qtext,
            "options": options,
            "answer_index": ai,
        })
    if not questions:
        # fallback: simple comprehension true/false style
        s = sentences[0] if sentences else "This concept is about the notes you uploaded."
        qtext = f"Which of these best matches what the notes say? " + s[:80] + "..."
        questions.append({"question": qtext,
                          "options": ["It is true according to the notes", "It is not true"],
                          "answer_index": 0})
    return questions


# ---------------------------------------------------------------------------
# Timetable gatekeeper
# ---------------------------------------------------------------------------
def study_window_message(start_hour, end_hour):
    """Return a friendly countdown-style message when outside study hours."""
    # For a demo, show which hours study time applies.
    if start_hour <= end_hour:
        return (f"{SHONA['not_study']} Your scheduled study window is {start_hour:02d}:00 – "
                f"{end_hour:02d}:00. {SHONA['come_back']} This helps you build a healthy routine.")
    return (f"{SHONA['not_study']} Your scheduled study window is overnight "
            f"({start_hour:02d}:00 → {end_hour:02d}:00). {SHONA['come_back']}")


def is_study_time(hour, start_hour, end_hour):
    if start_hour <= end_hour:
        return start_hour <= hour <= end_hour
    # overnight window, e.g. 22 -> 6
    return hour >= start_hour or hour <= end_hour


def countdown_to_study(hour, start_hour, end_hour):
    """Hours/min until next study window starts."""
    if start_hour <= end_hour:
        if hour < start_hour:
            return start_hour - hour, 0
        if hour > end_hour:
            return (24 - hour) + start_hour, 0
        return 0, 0  # inside window
    else:
        # overnight
        if hour < end_hour or hour >= start_hour:
            return 0, 0
        if hour < start_hour:
            return start_hour - hour, 0
        return (24 - hour) + start_hour, 0


# ---------------------------------------------------------------------------
# Study-session timer
# ---------------------------------------------------------------------------
def session_countdown(start_hour, end_hour, now):
    """Remaining minutes in the current study block + total block minutes."""
    start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    total_min = (end - start).seconds // 60
    if total_min <= 0:
        total_min = 24 * 60
    in_window = is_study_time(now.hour, start_hour, end_hour)
    if in_window:
        rem = max(0, (end - now).seconds // 60)
    else:
        rem = 0
    return {"remaining_min": rem, "total_min": total_min, "in_window": in_window,
            "end_hour": end_hour, "start_hour": start_hour}


# ---------------------------------------------------------------------------
# Weekly-schedule gatekeeper (independent learners)
# ---------------------------------------------------------------------------
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def schedule_state(schedule, now):
    """Given a user's weekly schedule (list of rows with day/start_hour/end_hour)
    and a datetime, return whether now is inside a study block, the next block
    start (day/hour), and the current block info."""
    wd = now.weekday()  # 0=Monday
    hour = now.hour
    current_block = None
    # in-block check for today
    for b in schedule:
        if b["day"] == wd and b["start_hour"] <= hour < b["end_hour"]:
            current_block = b
            break
    if current_block:
        return {"in_block": True, "block": current_block, "next": None}

    # find next block start (walk forward day by day)
    for offset in range(7):
        d = (wd + offset) % 7
        for b in sorted([x for x in schedule if x["day"] == d], key=lambda x: x["start_hour"]):
            if offset == 0 and b["start_hour"] <= hour:
                continue  # already passed today
            days_ahead = offset
            return {"in_block": False, "block": None,
                    "next": {"day": WEEKDAYS[d], "day_offset": days_ahead, "hour": b["start_hour"],
                             "end_hour": b["end_hour"], "subject": b["subject"]}}
    return {"in_block": False, "block": None, "next": None}


def schedule_hold_message(state):
    if not state or not state["next"]:
        return "No study sessions scheduled yet. Build your weekly schedule to begin."
    n = state["next"]
    ampm = f"{n['hour'] % 12 or 12}:00 {'AM' if n['hour'] < 12 else 'PM'}"
    when = "today" if n["day_offset"] == 0 else (
        "tomorrow" if n["day_offset"] == 1 else f"on {n['day']}")
    subj = f" for {n['subject']}" if n.get("subject") else ""
    return (f"Next session starts at {ampm} {when}{subj}. Rest up or come back then! "
            f"{SHONA['come_back']}")


# ---------------------------------------------------------------------------
# Rich media embeds (subject -> supporting video)
# ---------------------------------------------------------------------------
# We use a YouTube search-driven embed so a relevant supporting clip is pulled
# automatically for each subject. In the sandboxed preview the iframe won't load
# (no network), but it plays in a real browser; a fallback link is shown too.
VIDEOS = {
    "Mathematics": "Introduction to Linear Equations",
    "Biology": "Photosynthesis Explained",
    "English": "Poetic Devices: Simile, Metaphor and Personification",
    "Chemistry": "Chemical Kinetics and Reaction Rates",
    "Geography": "Map Reading and Contour Lines",
    "Physics": "Introduction to Physics Concepts",
    "History": "Introduction to World History",
    "Combined Science": "Science Basics and Chemical Reactions",
}


def video_for(subject):
    title = VIDEOS.get(subject, "Study this concept")
    query = title.replace(" ", "+") + "+lesson"
    # single-video search embed (plays the first matching educational video, not a playlist)
    url = f"https://www.youtube.com/embed?listType=search&list={query}&index=1&rel=0"
    watch = f"https://www.youtube.com/results?search_query={query}"
    return {"title": title, "url": url, "watch_url": watch, "query": title}
