"""
BT AI — the intelligence layer for BT LEARNING.

BT AI does the "heavy lifting": explaining notes in plain English, building
personalized study timetables, recommending videos, generating focus/break
music playlists, and tailoring explanations to a student's interests.

The app UI calls it "BT AI" regardless of the underlying model.

Backend: supports BOTH Gemini and Groq. It auto-detects whichever key is set:
  - GEMINI_API_KEY  -> uses Google Gemini
  - GROQ_API_KEY    -> uses Groq (fallback option)
If no key is set, the network is blocked, or the API returns an error, every
function falls back gracefully to the built-in rule-based engine (ai_engine.py)
so the app ALWAYS works.

  NEVER hardcode or commit the API key. Set it in Render's Environment tab.
"""
import os
import re
import json
import datetime

import ai_engine  # rule-based fallback

# Model names for each provider
GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def _load_dotenv():
    """Load API keys from a local .env file if present (dev only)."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        for name in (".env", "secrets.env"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                for line in open(p):
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


def _read_secret_files():
    """Read API keys from common 'secret file' locations.
    Supports both GROQ and GEMINI secret files."""
    for var, names in {
        "GROQ_API_KEY": ["GROQ_SECRET_FILE", "/etc/secrets/GROQ_API_KEY",
                         "/var/secrets/GROQ_API_KEY", "/run/secrets/GROQ_API_KEY",
                         "/mnt/secrets/GROQ_API_KEY"],
        "GEMINI_API_KEY": ["GEMINI_SECRET_FILE", "/etc/secrets/GEMINI_API_KEY",
                           "/var/secrets/GEMINI_API_KEY", "/run/secrets/GEMINI_API_KEY",
                           "/mnt/secrets/GEMINI_API_KEY"],
    }.items():
        if os.environ.get(var):
            continue
        for path in names:
            if not path:
                continue
            try:
                if os.path.exists(path):
                    content = open(path).read().strip()
                    if content:
                        os.environ[var] = content
                        print(f"[btai] Read {var} from secret file: {path}")
                        break
            except Exception:
                pass


_load_dotenv()
_read_secret_files()

_groq_client = None
_gemini_model = None
_provider = None  # 'gemini', 'groq', or None


def get_provider():
    """Return the active provider ('gemini' or 'groq') or None if no key set."""
    global _provider
    if _provider is not None:
        return _provider
    if os.environ.get("GEMINI_API_KEY", "").strip():
        _provider = "gemini"
    elif os.environ.get("GROQ_API_KEY", "").strip():
        _provider = "groq"
    else:
        _provider = None
    return _provider


def ai_enabled():
    """True if a real AI model (Gemini or Groq) is configured and usable."""
    return get_provider() is not None


def _get_client():
    """Return the active provider's client/model, or None if unusable."""
    provider = get_provider()
    if provider == "groq":
        global _groq_client
        if _groq_client is not None:
            return _groq_client
        try:
            import groq
            _groq_client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception:
            _groq_client = False
        return _groq_client if _groq_client else None
    elif provider == "gemini":
        global _gemini_model
        if _gemini_model is not None:
            return _gemini_model
        try:
            from google import genai as _genai
            _gemini_model = _genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        except Exception:
            _gemini_model = False
        return _gemini_model if _gemini_model else None
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _call(prompt, temperature=0.7, max_tokens=None):
    """Call the active AI provider and return text. Returns None on any failure."""
    provider = get_provider()
    client = _get_client()
    if not client:
        return None
    try:
        if provider == "groq":
            kwargs = {"temperature": temperature}
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return resp.choices[0].message.content
        elif provider == "gemini":
            gen_kwargs = {"temperature": temperature}
            if max_tokens:
                gen_kwargs["max_output_tokens"] = max_tokens
            resp = client.models.generate_content(model=GEMINI_MODEL,
                                                  contents=prompt,
                                                  config=gen_kwargs)
            return resp.text
    except Exception as e:
        print(f"[btai] {provider} call failed ({type(e).__name__}): {str(e)[:120]}")
        return None
    return None


def _extract_json(text):
    """Pull a JSON object/array out of model text (handles code fences)."""
    if not text:
        return None
    text = text.strip()
    # remove markdown fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    # find first { ... } or [ ... ]
    for opener, closer in (("[", "]"), ("{", "}")):
        s = text.find(opener)
        e = text.rfind(closer)
        if s != -1 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except Exception:
                pass
    return None


def _safe_json(prompt, fallback, temperature=0.4):
    """Call Gemini for JSON, returning fallback on any failure."""
    out = _call(prompt, temperature=temperature)
    parsed = _extract_json(out)
    return parsed if parsed is not None else fallback


# ---------------------------------------------------------------------------
# 1) Timetable generation (AI restructures the student's schedule)
# ---------------------------------------------------------------------------
def generate_timetable(subjects, total_hours=10, preferences=""):
    """Return a weekly timetable dict {day: [ {subject, start, end} ]}."""
    days = ai_engine.WEEKDAYS
    # --- Fallback: balanced rule-based timetable (always works) ---
    fallback = {}
    if subjects:
        per_day = max(1, round(total_hours / 7))
        idx = 0
        for d in days:
            block = []
            for _ in range(max(1, per_day // max(1, len(subjects)))):
                subj = subjects[idx % len(subjects)]
                idx += 1
                block.append({"subject": subj, "start": 9, "end": 10})
            fallback[d] = block

    prompt = f"""You are BT AI, a study coach. Build a balanced weekly study timetable.
Subjects: {json.dumps(subjects)}
Total study hours per week: {total_hours}
Student preferences/constraints: {preferences or 'none'}

Return STRICT JSON (no prose, no markdown) with this exact shape:
{{"timetable": {{"Monday":[{{"subject":"...","start":9,"end":10}}], ... all 7 days }}}}
Use 24h hour integers. Spread subjects evenly. Keep each session 30-120 min."""

    parsed = _safe_json(prompt, fallback={"timetable": fallback})
    data = parsed.get("timetable", parsed) if isinstance(parsed, dict) else parsed
    if isinstance(data, dict) and data:
        # normalise keys to full day names
        normal = {}
        for k, v in data.items():
            # accept abbreviations
            key = next((d for d in days if d.lower().startswith(k.lower()[:3])), k)
            normal[key] = v if isinstance(v, list) else []
        if len(normal) >= 7:
            return normal
    return fallback


# ---------------------------------------------------------------------------
# 2) Explain notes in plain, easy English (personalised)
# ---------------------------------------------------------------------------
def explain_notes(content, interests="", academic_level=""):
    """Return a plain-English, interest-aware explanation of uploaded notes."""
    content = (content or "")[:4000]
    interest_hint = ""
    if interests:
        interest_hint = (f"\nPersonalise the examples using the student's interests: {interests}. "
                         "Use analogies from these where possible.")
    prompt = f"""You are BT AI, a friendly tutor. Explain the following notes in VERY SIMPLE,
easy-to-understand English for a {academic_level or 'school'} student. Structure your answer
with Markdown so it's easy to read:
- Start with a one-line summary as a bold statement.
- Use a "## Key points" heading followed by bullet points.
- Use a "## Example" heading with a short, clear example (use an analogy from the student's
  interests if relevant).
- Use bold for important terms.
Do NOT repeat the notes word-for-word — make them make sense. Keep it under 350 words.
{interest_hint}

NOTES:
{content}"""
    out = _call(prompt)
    if out:
        return out.strip()
    # Fallback: rule-based summary formatted as Markdown
    return _fallback_explain(content, interests)


def _fallback_explain(content, interests):
    sentences = ai_engine.split_sentences(content)
    intro = ai_engine.personalized_explain(sentences[0][:60] if sentences else "this topic", interests)
    points = "\n".join(f"- {s}" for s in sentences[:5])
    return f"**In a nutshell:** {intro}\n\n## Key points\n{points}"


# ---------------------------------------------------------------------------
# 3) Video recommendation
# ---------------------------------------------------------------------------
def recommend_video(subject, topic="", interests=""):
    """Return {title, url, watch_url} of a good supporting lesson video.
    Uses the YouTube Data API (if YOUTUBE_API_KEY is set) to find a real,
    targeted lesson video with a valid embed ID. Falls back to a search embed
    if no API key is available or the API fails."""
    # ---- Try the real YouTube Data API first (needs YOUTUBE_API_KEY) ----
    api_video = _youtube_search(subject, topic)
    if api_video:
        return api_video

    # ---- Fallback: single-video search embed (no API key needed) ----
    base = ai_engine.video_for(subject)
    prompt = f"""Pick ONE great YouTube search phrase for a student learning '{subject}'
{topic and 'on "' + topic + '"' or ''}. Interests: {interests or 'none'}.
It must be an EDUCATIONAL lesson video (not music). Append a lesson-style keyword like
'lesson', 'tutorial', or 'explained'.
Return STRICT JSON: {{"query": "concise search phrase (5-10 words)"}}"""
    parsed = _safe_json(prompt, fallback={"query": base["title"]})
    query = parsed.get("query", base["title"]) if isinstance(parsed, dict) else base["title"]
    query = query.replace("+", " ")[:80]
    q = query.replace(" ", "+")
    # embed URL (plays in-app where embeds work) + a watch URL (opens YouTube in a new tab)
    embed = f"https://www.youtube.com/embed?listType=search&list={q}&index=1"
    watch = f"https://www.youtube.com/results?search_query={q}"
    return {"title": query, "url": embed, "watch_url": watch, "query": query}


# Words that clearly indicate a NON-educational search (music/games/entertainment/social)
NON_EDU_WORDS = [
    "music", "song", "album", "lyrics", "video official", "mv ", "movie", "film",
    "game", "gaming", "playstation", "xbox", "fifa", "gta", "fortnite", "minecraft",
    "tiktok", "instagram", "facebook", "twitter", "celeb", "celebrity", "gossip",
    "match", "highlights", "goal", "dance", "party", "club", "drama", "series",
]


def is_educational_query(query):
    """Return (bool_is_educational, reason). Detects clearly non-educational searches."""
    q = (query or "").lower()
    # educational markers override
    edu_markers = ["lesson", "tutorial", "explain", "what is", "how to solve", "class",
                   "biology", "math", "chemistry", "physics", "geography", "history",
                   "english", "science", "learn", "study", "definition", "formula",
                   "algebra", "photosynthesis", "equations", "exam"]
    if any(m in q for m in edu_markers):
        return True, None
    # if it clearly mentions non-educational content, flag it
    hits = [w for w in NON_EDU_WORDS if w in q]
    if hits:
        return False, f"'{query}' looks like it's about {', '.join(hits)} rather than studying."
    # short one-word queries that aren't obviously educational -> warn gently
    if len(q.split()) <= 2 and not any(m in q for m in edu_markers):
        return False, f"'{query}' may not be an educational topic. Please search for lessons, subjects or concepts."
    return True, None


def search_videos(query, max_results=12):
    """Search YouTube for videos matching a query. Returns list of
    {title, url, watch_url, thumbnail, channel}. Falls back to search embed."""
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    videos = []
    if key:
        try:
            import urllib.parse
            import urllib.request
            url = ("https://www.googleapis.com/youtube/v3/search?"
                   "part=snippet&type=video&videoEmbeddable=true&maxResults=%d"
                   "&q=%s&key=%s" % (max_results, urllib.parse.quote(query), key))
            with urllib.request.urlopen(url, timeout=12) as resp:
                data = json.loads(resp.read().decode())
            for it in data.get("items") or []:
                vid = it.get("id", {}).get("videoId")
                sn = it.get("snippet", {})
                if vid:
                    videos.append({"title": sn.get("title", ""),
                                   "url": f"https://www.youtube.com/embed/{vid}",
                                   "watch_url": f"https://www.youtube.com/watch?v={vid}",
                                   "thumbnail": (sn.get("thumbnails") or {}).get("medium", {}).get("url", ""),
                                   "channel": sn.get("channelTitle", "")})
        except Exception as e:
            print(f"[btai] video search failed ({type(e).__name__}): {str(e)[:80]}")
    if not videos:
        # fallback search embed
        q = query.replace(" ", "+")
        videos = [{"title": query, "url": f"https://www.youtube.com/embed?listType=search&list={q}&index=1",
                   "watch_url": f"https://www.youtube.com/results?search_query={q}",
                   "thumbnail": "", "channel": ""}]
    return videos


def _youtube_search(subject, topic=""):
    """Use the YouTube Data API to fetch a real embeddable lesson video.
    Returns None on any failure (no key, network, API error)."""
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return None
    query = f"{topic or subject} lesson tutorial"
    try:
        import urllib.parse
        import urllib.request
        url = ("https://www.googleapis.com/youtube/v3/search?"
               "part=snippet&type=video&videoEmbeddable=true&maxResults=5"
               f"&q={urllib.parse.quote(query)}&key={key}")
        with urllib.request.urlopen(url, timeout=12) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or []
        for it in items:
            vid = it.get("id", {}).get("videoId")
            title = it.get("snippet", {}).get("title", "")
            if vid and title:
                return {"title": title,
                        "url": f"https://www.youtube.com/embed/{vid}",
                        "watch_url": f"https://www.youtube.com/watch?v={vid}",
                        "video_id": vid}
    except Exception as e:
        print(f"[btai] YouTube API failed ({type(e).__name__}): {str(e)[:100]}")
        return None
    return None


# ---------------------------------------------------------------------------
# 4) Music playlist (focus / study vs break)
# ---------------------------------------------------------------------------
def recommend_playlist(interests="", mode="focus"):
    """Return a list of songs {title, artist, url}. mode: 'focus' or 'break'."""
    interest_hint = interests or "generic calm"
    prompt = f"""You are BT AI. The student likes: {interest_hint}.
Generate a '{mode}' playlist of 8 songs — for study/focus, pick calm, low-distraction,
instrumental or soft tracks; for break, pick upbeat, energising tracks they'd enjoy.
Return STRICT JSON (no markdown): an array of objects:
[{{"title":"...","artist":"..."}}, ...]"""
    parsed = _safe_json(prompt, fallback=_fallback_playlist(interests, mode), temperature=0.6)
    if isinstance(parsed, list):
        songs = parsed
    elif isinstance(parsed, dict) and "songs" in parsed:
        songs = parsed["songs"]
    else:
        songs = _fallback_playlist(interests, mode)
    out = []
    for s in songs[:8]:
        if isinstance(s, dict):
            title = str(s.get("title", "")).strip()
            artist = str(s.get("artist", "")).strip()
            if title:
                # try to get a real video ID from YouTube API
                real = _youtube_song(title, artist)
                if real:
                    out.append(real)
                else:
                    q = f"{title} {artist}".strip().replace(" ", "+")
                    out.append({"title": title, "artist": artist,
                                "url": f"https://www.youtube.com/embed?listType=search&list={q}&index=1",
                                "watch_url": f"https://www.youtube.com/results?search_query={q}"})
    return out or _fallback_playlist(interests, mode)


def _youtube_song(title, artist=""):
    """Use the YouTube Data API to find a real music video. Returns None on failure."""
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return None
    query = f"{title} {artist}".strip() or title
    try:
        import urllib.parse
        import urllib.request
        url = ("https://www.googleapis.com/youtube/v3/search?"
               "part=snippet&type=video&videoEmbeddable=true&maxResults=1"
               f"&q={urllib.parse.quote(query)}&key={key}")
        with urllib.request.urlopen(url, timeout=12) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or []
        if not items:
            return None
        vid = items[0].get("id", {}).get("videoId")
        song_title = items[0].get("snippet", {}).get("title", title)
        if vid:
            return {"title": song_title, "artist": artist,
                    "url": f"https://www.youtube.com/embed/{vid}",
                    "watch_url": f"https://www.youtube.com/watch?v={vid}",
                    "video_id": vid}
    except Exception as e:
        print(f"[btai] YouTube song API failed ({type(e).__name__}): {str(e)[:100]}")
        return None
    return None


# Common music genres (worldwide + regional) for one-click genre playlists
MUSIC_GENRES = [
    "Amapiano", "Afrobeats", "Gqom", "House", "Hip Hop", "R&B", "Reggae",
    "Dancehall", "Gospel", "Jazz", "Classical", "Lofi", "Pop", "Rock",
    "Dance", "Electronic", "Soul", "Country", "Bongo Flava", "Highlife",
    "Sungura", "Rhumba", "Techno", "Afro Pop",
]


def genre_playlist(genre, location="", num=12):
    """Build a playlist for a one-click genre. If location is set, mix in
    'new songs in <location>' for the 'new in your country' feature.
    Returns list of {title, artist, url, watch_url}."""
    import random
    query = genre
    if location:
        query = f"{genre} {location}"
    songs = []
    seen = set()
    for i in range(num):
        extra = random.choice(["", "mix", "2024", "latest", "best of"])
        q = f"{query} {extra}".strip()
        song = _youtube_song(q, "")
        if song and song["url"] not in seen:
            seen.add(song["url"])
            songs.append(song)
    return songs or recommend_playlist(location or genre, "break")


def new_songs_playlist(location):
    """Playlist of the newest trending songs in the user's country/location."""
    query = f"new songs {location} 2024 latest" if location else "new songs latest playlist"
    songs = []
    seen = set()
    for i in range(12):
        song = _youtube_song(query, "")
        if song and song["url"] not in seen:
            seen.add(song["url"])
            songs.append(song)
    return songs or recommend_playlist(location or "pop", "break")


def _fallback_playlist(interests, mode):
    low = interests.lower()
    genre = "lofi"
    if any(k in low for k in ("rock", "hip", "rap", "dance", "electronic", "afrobeat")):
        genre = "afrobeats" if "afro" in low else "electronic"
    elif any(k in low for k in ("gospel", "rnb", "soul", "jazz")):
        genre = "r&b"
    elif any(k in low for k in ("classical", "piano", "instrumental")):
        genre = "classical"
    word = "focus" if mode == "focus" else "energizing"
    return [{"title": f"{genre.title()} {word} mix {i+1}", "artist": genre.title(),
             "url": f"https://www.youtube.com/embed?listType=search&list={genre}+{word}+mix&index=1",
             "watch_url": f"https://www.youtube.com/results?search_query={genre}+{word}+mix"}
            for i in range(6)]


# ---------------------------------------------------------------------------
# 4b) Break playlist from user's favorite artists/songs with length estimation
# ---------------------------------------------------------------------------
def break_playlist(favorites, break_minutes=10, interests=""):
    """Build a break playlist from the user's favorite artists/songs.
    Returns {songs:[{title,artist,url,watch_url,duration_sec}], total_minutes, estimated}."""
    favs = [f for f in favorites if f.get("name")]
    songs = []
    # Shuffle favorites and pick enough to fill the break
    import random
    favs = sorted(favs, key=lambda x: random.random())
    seen = set()
    for fav in favs:
        if len(songs) >= 12:
            break
        song = _youtube_song(fav["name"], "")  # search for the favorite
        if song and fav["name"] not in seen:
            seen.add(fav["name"])
            # estimate duration via API if possible; else assume ~3.5 min
            dur = _video_duration(song.get("video_id")) or 210
            song["duration_sec"] = dur
            songs.append(song)
    # If we couldn't get enough from favorites, add interest-based filler
    if not songs:
        songs = recommend_playlist(interests, "break")
        for s in songs:
            s["duration_sec"] = 210
    # trim to fit the break window
    total = 0
    fit = []
    for s in songs:
        d = s.get("duration_sec", 210)
        if total + d <= break_minutes * 60:
            fit.append(s)
            total += d
        if not fit or len(fit) < 2:
            if not fit:
                fit.append(s); total += d
    return {"songs": fit, "total_minutes": round(total / 60, 1),
            "estimated": True, "break_minutes": break_minutes}


def _video_duration(video_id):
    """Use YouTube API to get a video's duration in seconds. Returns None on failure."""
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key or not video_id:
        return None
    try:
        import urllib.request
        url = (f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails"
               f"&id={video_id}&key={key}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        items = data.get("items") or []
        if not items:
            return None
        duration = items[0].get("contentDetails", {}).get("duration", "")
        # ISO 8601 duration PT#M#S -> seconds
        import re
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if m:
            h = int(m.group(1) or 0); mm = int(m.group(2) or 0); s = int(m.group(3) or 0)
            return h * 3600 + mm * 60 + s
    except Exception as e:
        print(f"[btai] video duration failed ({type(e).__name__}): {str(e)[:80]}")
        return None
    return None


# ---------------------------------------------------------------------------
# 5) Persistent AI chat tutor (idea 1)
# ---------------------------------------------------------------------------
def chat(notes_context, message, interests="", academic_level="", history=None):
    """Answer a student's question using ONLY the uploaded notes context.
    history: optional list of {role:'user'|'ai', text:...} for continuity."""
    context = (notes_context or "")[:5000]
    interest_hint = f"Tailor examples to these interests: {interests}." if interests else ""
    hist_txt = ""
    if history:
        lines = []
        for h in history[-6:]:
            who = "Student" if h.get("role") == "user" else "BT AI"
            lines.append(f"{who}: {h.get('text','')}")
        hist_txt = "\n".join(lines) + "\n"

    notes_hint = (f"Use these notes as your main source if they cover the topic:\n{context}\n"
                  if context else "There are no notes uploaded for this yet — answer from your own knowledge in a helpful, simple way.")
    prompt = f"""You are BT AI, a friendly, knowledgeable tutor. Answer the student's question
clearly and helpfully. {notes_hint}
Use Markdown so the answer looks clean:
- Start with a short direct answer in bold.
- Use bullet points for the main explanation.
- Use a short "## Example" with an analogy if helpful.
Keep it clear and brief (under 220 words). {interest_hint}
Academic level: {academic_level or 'school'}

PREVIOUS CHAT:
{hist_txt}
Student's question: {message}"""
    out = _call(prompt, temperature=0.5)
    if out:
        return out.strip()
    return _fallback_chat(context, message, interests)


def _fallback_chat(context, message, interests):
    m = (message or "").lower().strip()
    # greetings and casual messages should always get a friendly reply
    if not m or len(m) < 2:
        return "**Hey! 👋** I'm BT AI, your study buddy. Ask me anything — explain a topic, solve a problem, or just say hi."
    if any(g in m for g in ["hi", "hello", "hey", "how are", "morning", "afternoon", "evening", "yo ", "good day"]):
        return "**Hey there! 👋** Great to see you. I can help you learn anything — what subject are you working on today?"
    if any(g in m for g in ["thanks", "thank you", "thankyou"]):
        return "**You're welcome! 😊** I'm always here when you need me. Keep up the great work!"
    if any(g in m for g in ["who are you", "what are you", "your name"]):
        return "**I'm BT AI** — your personal study tutor from BT LEARNING. I make learning simple, and I tailor everything to how you learn best."
    if "?" not in m and len(m) < 30:
        # short non-question -> keep conversation going
        return f"**Interesting!** Tell me more, {interests.split(',')[0].title() if interests else 'friend'} — or let's dive into a topic together."
    # otherwise try to answer from notes if available
    sentences = ai_engine.split_sentences(context)
    if sentences:
        qwords = set(re.findall(r"\b[a-z]{4,}\b", m))
        hits = [s for s in sentences if any(w in s.lower() for w in qwords)]
        source = hits[:2] or sentences[:2]
        intro = ai_engine.personalized_explain(message[:50], interests)
        return (f"**{intro}**\n\nBased on your notes:\n" + "\n".join(f"- {s}" for s in source))
    # General question, no notes: answer from general knowledge templates
    return _general_knowledge_answer(message, interests)


def _general_knowledge_answer(message, interests):
    """Answer general questions even with no notes, using light built-in knowledge.
    The real AI (Gemini/Groq) handles the deep answers; this is only the offline fallback."""
    m = message.lower()
    topic = message.strip()
    if any(w in m for w in ["what is ", "define ", "meaning of ", "what are ", "who is "]):
        return (f"**Let's break that down.**\n\n- **{topic}** is a topic you can explore in your "
                f"lessons or by searching the **Visual** tab for a video.\n- Add study notes and I "
                f"can explain it in your own words.\n\n💡 For a full, detailed answer right now, "
                f"make sure the AI is connected (you'll see **'Connected'** in the chat header). "
                f"Then I can answer anything — like ChatGPT or Gemini.")
    return (f"Great question! I'd love to explain **{topic}** properly.\n\n"
            f"- When **BT AI is connected** (check the header — it shows **'Connected'**), I can "
            f"answer anything, just like ChatGPT or Gemini.\n"
            f"- Right now I'm on my **offline engine**, which works best with your notes.\n"
            f"- Tip: use the **Visual** tab to find a video on **{topic}**, or add notes and I'll "
            f"explain it from those.")


# ---------------------------------------------------------------------------
# 5b) Friendly interactive AI chat with behaviour-based gating
# ---------------------------------------------------------------------------
def chat_interactive(message, subject, notes_context, user, ai_state):
    """A friendly, human-sounding tutor chat that:
      - Always answers educational questions.
      - Allows short casual talk, but if the user keeps chatting casually for too
        long, nudges them back to studying / the exam.
      - Applies an 8-hour 'cooldown' on casual mode if they ignore the nudge.
    Returns (reply_text, action) where action is 'none'|'exam'|'study'|'cooldown'."""
    import datetime as _dt
    now = _dt.datetime.now()
    is_edu = _is_educational(message)
    casual = (ai_state or {}).get("casual_count", 0) or 0

    # Check cooldown (8 hours)
    cooldown = ai_state.get("cooldown_until") if ai_state else None
    if cooldown:
        try:
            cd = _dt.datetime.fromisoformat(cooldown)
            if now < cd:
                hours = max(1, int((cd - now).total_seconds() // 3600))
                # If it's an educational question, answer it even during cooldown
                if is_edu:
                    base = chat(notes_context, message, user.get("interests", ""),
                                user.get("academic_level", ""))
                    return (f"{base}\n\n_(Note: casual chat unlocks in ~{hours}h, "
                            f"but I'll always help with your studies!)_"), "study"
                return (f"Hey {user.get('name','').split()[0] or 'friend'} 👋 — I'd love to chat, "
                        f"but we agreed to keep it focused. Casual talk unlocks in about **{hours}h**. "
                        f"Right now, let's get back to {subject} — I can help you ace it! "
                        f"Want a quick quiz?"), "cooldown"
        except Exception:
            pass

    if is_edu:
        # educational: always answer, reward the student
        if casual > 0:
            db_state = dict(ai_state) if ai_state else {}
            db_state["casual_count"] = 0
        reply = chat(notes_context, message, user.get("interests", ""),
                     user.get("academic_level", ""))
        return reply, "none"

    # Casual message
    casual += 1
    # friendly casual reply
    friendly = _casual_reply(message, user, subject)
    # track + decide
    if casual >= 4:
        # Too much casual talk -> send them to exam
        return (f"{friendly}\n\n😊 I really enjoy chatting with you! But I can see you've been "
                f"hanging out here a while. **Let's make it count** — finish and pass the exam for "
                f"**{subject}**, then we can chat freely again. Tap **Take the exam** to go now! "
                f"Otherwise casual chat unlocks again in 8 hours."), "exam"
    return (f"{friendly}\n\n*(You've been chatting casually a bit — that's fine! Just remember "
            f"your study time. When you're ready, let's do a quick check on **{subject}**!)*"), "none"


def _is_educational(message):
    """Heuristic: does this message look like a study/exam question?"""
    edu_words = ["what", "how", "why", "define", "explain", "solve", "calculate", "formula",
                 "difference", "example", "question", "exam", "test", "concept", "learn",
                 "understand", "meaning", "subject", "answer", "works", "mean", "equation",
                 "note", "revision", "help me with", "explain"]
    m = message.lower()
    if any(w in m for w in edu_words):
        return True
    # question mark with a '?' suggests a real question
    return "?" in message and len(message) > 12


def _casual_reply(message, user, subject):
    name = user.get("name", "").split()[0] or "friend"
    m = message.lower()
    if any(g in m for g in ["hi", "hello", "hey", "how are", "morning", "afternoon", "evening"]):
        return (f"Hey {name}! 👋 I'm doing great, thanks for asking — and I'm really glad you're "
                f"here. How are you feeling about **{subject}** today?")
    if any(g in m for g in ["music", "song", "artist", "listen", "play"]):
        return (f"Love that you like music, {name}! 🎵 Did you know I can build a focus playlist "
                f"for you so the tunes help you concentrate instead of distract? Check the 🎵 Music tab!")
    if any(g in m for g in ["tired", "bored", "sad", "stressed", "hard"]):
        return (f"I hear you, {name}. 💛 Studying can be tough, but you're doing the right thing "
                f"by showing up. Take a short breath, and let's tackle **{subject}** together — "
                f"I'll keep it simple.")
    if any(g in m for g in ["bye", "later", "see you", "goodnight"]):
        return (f"See you soon, {name}! 👋 Don't forget — your **{subject}** lesson is waiting. "
                f"I'll be right here when you're back.")
    return (f"Hey {name}, that's interesting! 😊 I'm here as your study buddy, so whenever you're "
            f"ready, let's dive into **{subject}** — or I can set you a quick quiz to see how "
            f"you're doing.")


# ---------------------------------------------------------------------------
# 5c) Cross-subject example generation
# ---------------------------------------------------------------------------
def cross_subject_explain(topic, subject, strong_subject, strong_content):
    """Explain a topic in the current subject using an analogy/example from another
    subject the student is good at."""
    strong = (strong_content or "")[:1500]
    prompt = f"""You are BT AI. The student understands '{strong_subject}' well. Help them
understand '{topic}' in '{subject}' by drawing a clear analogy/example FROM '{strong_subject}'.
Use Markdown: a bold explanation, then a "## Example from {strong_subject}" with a concrete example.
Keep under 160 words. Example context: {strong}"""
    out = _call(prompt, temperature=0.6)
    if out:
        return out.strip()
    return (f"Let me explain **{topic}** using what you already know in **{strong_subject}**. "
            f"Think of it like the ideas in {strong_subject} — the same way you connect concepts "
            f"there, you can connect these. Take it step by step, and I'll help you link them.")


# ---------------------------------------------------------------------------
# 6) AI progress coach (idea 5)
# ---------------------------------------------------------------------------
def progress_coach(subject, total_questions, correct, wrong, weak_concepts, interests=""):
    """Generate a weekly review summary + what to focus on."""
    acc = round(correct * 100 / total_questions) if total_questions else 0
    prompt = f"""You are BT AI, a study coach. For the subject '{subject}', the student answered
{total_questions} knowledge checks, got {correct} right ({acc}%) and {wrong} wrong.
Weak concepts they struggled with: {weak_concepts or 'none'}.
Interests: {interests or 'none'}.
Write a short, encouraging weekly review (under 220 words) using Markdown:
- Start with a bold "**Your progress:**" line.
- Use a "## What's going well" heading with bullets.
- Use a "## What to review" heading with bullets (the weak concepts).
- End with a "## Next step" bold suggestion.
Use a friendly, motivating tone."""
    out = _call(prompt, temperature=0.6)
    if out:
        return out.strip()
    if total_questions == 0:
        return ("**You haven't attempted any knowledge checks yet.** Head to a lesson and take "
                "your first check so BT AI can coach you.")
    tip = (f"Focus on reviewing: {', '.join(weak_concepts[:3])}." if weak_concepts
           else "You're on track — keep your streak going!")
    return (f"**Your progress:** {total_questions} checks, {acc}% accuracy in {subject}.\n\n"
            f"## What to review\n- {tip}\n\n**Next step:** keep your streak going!")


# ---------------------------------------------------------------------------
# 7) AI explanation of a failed answer (idea 6)
# ---------------------------------------------------------------------------
def explain_answer(question, correct_answer, chosen, interests=""):
    """Explain why the correct answer is right, in the student's preferred style."""
    interest_hint = f"Use an analogy from these interests: {interests}." if interests else ""
    prompt = f"""You are BT AI. The student answered a knowledge-check question WRONG.
Question: {question}
The correct answer was: {correct_answer}
They chose: {chosen}
Explain, kindly and simply, why '{correct_answer}' is correct and why the other answer was a
mistake. Use Markdown: a bold answer, a bullet for the key reason, and a short "## Example"
analogy. Under 150 words. {interest_hint}"""
    out = _call(prompt, temperature=0.5)
    if out:
        return out.strip()
    return (f"**The correct answer is '{correct_answer}'.**\n\n"
            f"## Why\n- Go back to the notes and re-read the part about this topic.\n\n"
            f"{ai_engine.SHONA['try_again']}")


# ---------------------------------------------------------------------------
# 8) AI-generated quiz from notes (idea: AI quizzes)
# ---------------------------------------------------------------------------
def generate_quiz(subject, notes_content, interests="", num=5, language="en"):
    """Return a list of quiz questions {question, options, answer_index} based on notes."""
    content = (notes_content or "")[:5000]
    lang_note = "Answer in " + ("Shona" if language == "sn" else "Ndebele" if language == "nd" else "English")
    prompt = f"""{lang_note}. You are BT AI. Create {num} multiple-choice quiz questions
about this study material. Each question must be answerable ONLY from the notes.
Return STRICT JSON (no markdown): an array of
[{{"question":"...","options":["a","b","c","d"],"answer":2}}] where 'answer' is the 0-based
index of the correct option. Make options plausible and varied.

NOTES:
{content}"""
    fallback = _fallback_quiz(subject, content, num)
    parsed = _safe_json(prompt, fallback=fallback, temperature=0.5)
    if isinstance(parsed, dict) and "questions" in parsed:
        parsed = parsed["questions"]
    out = []
    if isinstance(parsed, list):
        for q in parsed[:num]:
            if not isinstance(q, dict):
                continue
            options = q.get("options") or []
            if len(options) < 2:
                continue
            try:
                ai = int(q.get("answer", 0)) % len(options)
            except Exception:
                ai = 0
            out.append({"question": str(q.get("question", "")), "options": list(options),
                        "answer_index": ai})
    return out or fallback


def _fallback_quiz(subject, content, num):
    chunks = ai_engine.chunk_content(content)
    qs = []
    for i, ch in enumerate(chunks):
        qs += ai_engine.generate_questions(ch["content"], chunks, seed=i, limit=2)
        if len(qs) >= num:
            break
    return qs[:num]


# ---------------------------------------------------------------------------
# 9) Teacher AI class insight (idea: teacher AI summary)
# ---------------------------------------------------------------------------
def class_summary(subject, health, weak_items, class_size, interests_hint="", language="en"):
    """Generate a short teacher-facing summary of class performance."""
    if not weak_items:
        return (f"The class is performing well in {subject} (health {health or 'n/a'}%). "
                "No critical weak spots right now.")
    weak_lines = "; ".join(f"{w['student_name']} on {w['concept']} ({w['fail_count']}x)"
                           for w in weak_items[:4])
    prompt = f"""You are BT AI. Summarize for a teacher: class {subject} health {health}%,
{class_size} students, top weak areas: {weak_lines}. Use Markdown:
- Start with a bold "**Class overview:**" line.
- Use a "## What's going well" heading with a short bullet or two.
- Use a "## Knowledge gaps to reteach" heading with bullets.
- End with a bold "**Suggestion:**" one-liner.
Keep it under 130 words."""
    out = _call(prompt, temperature=0.5)
    if out:
        return out.strip()
    return (f"**Class overview:** health {health or 'n/a'}% in {subject} across {class_size} students.\n\n"
            f"## Knowledge gaps to reteach\n{weak_lines}\n\n"
            f"**Suggestion:** re-teach these concepts and assign targeted practice.")


# ---------------------------------------------------------------------------
# 10) Study reminder text (idea: notifications)
# ---------------------------------------------------------------------------
def study_reminder(schedule_state, name=""):
    """Return a friendly reminder based on the next scheduled session."""
    if not schedule_state or not schedule_state.get("next"):
        return "You have no study sessions scheduled yet."
    n = schedule_state["next"]
    h12 = n["hour"] % 12 or 12
    ampm = "AM" if n["hour"] < 12 else "PM"
    when = ("today" if n["day_offset"] == 0 else
            "tomorrow" if n["day_offset"] == 1 else f"on {n['day']}")
    subj = f" for {n['subject']}" if n.get("subject") else ""
    return (f"{name + ', ' if name else ''}your next BT AI study session is at "
            f"{h12}:00 {ampm} {when}{subj}. BT AI will greet you then!")


# ---------------------------------------------------------------------------
# 11) Exam simulation scoring message (idea: exam mode)
# ---------------------------------------------------------------------------
def exam_feedback(subject, correct, total):
    pct = round(correct * 100 / total) if total else 0
    if pct >= 80:
        return f"Excellent! You scored {correct}/{total} ({pct}%) in {subject}. You've mastered this material."
    if pct >= 60:
        return f"Good effort — {correct}/{total} ({pct}%). Review the questions you missed and try again."
    if pct >= 40:
        return f"{correct}/{total} ({pct}%). You need more review in {subject}. BT AI recommends revisiting the notes."
    return f"{correct}/{total} ({pct}%). Don't give up! Go back through the notes and retake the exam."


