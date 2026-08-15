"""Daily hourly breakdown -- 'what was I mostly doing, hour by hour'.
A different lens than insight/'s colored documents: per-hour category
and app percentages instead of a written summary, for the calendar's
day-detail view.

Two ways this data gets produced:
  - synth_seed_day() -- fake, deterministic preview data, for days
    the app never tracked (before install, or before you ran it that
    day) or when you just want to look at the UI shape.
  - build_day_from_activity() / refresh_today() -- REAL data, read
    from shared/db.py's `activity` table (already logging every ~5s:
    process name, window title, timestamp, drift-flagged or not).
    This is what actually runs continuously now -- see
    refresh_today(), called on a timer from main.py.

Categorization is plain keyword matching against process name +
window title (CATEGORY_KEYWORDS below), not AI -- deliberately, so it
stays free and instant to run every few minutes all day, and so it's
fully deterministic and easy to tune by hand. It will misclassify
things sometimes (an app used for two different purposes, like Gmail
for both sales and general email, can't be told apart by app name
alone) -- edit CATEGORY_KEYWORDS directly to improve it as you notice
misses. Flagged/drift samples (already-computed by core/tracker.py)
are counted as "Break" directly, reusing that existing, tested signal
rather than re-guessing it.

Storage format is identical whether a day's data is synthetic or
real -- check the "synthetic" key in a loaded doc to tell which.
"""
import json
import os
import random

BASE_DIR = "day_breakdown_data"

CATEGORY_COLORS = {
    "Focus Work": "#5b8a72",
    "Break": "#44444e",
    "Sales": "#c9a86a",
    "Hiring": "#b98ce0",
    "Design": "#5fd0c0",
    "Comms": "#6fa8dc",
    "Other": "#666670",
}

# Categories worth showing as a small tag chip on an hour row when they
# dominate it -- "Focus Work", "Break", and "Other" are background
# states, not worth flagging on their own.
TAG_WORTHY = {"Sales", "Hiring", "Design", "Comms"}

# Plain keyword matching against "process_name window_title" (lower-
# cased). First category whose keyword list matches wins -- order
# matters. Edit freely; this is the one part of the pipeline meant to
# be hand-tuned rather than computed.
CATEGORY_KEYWORDS = {
    "Sales": ["quote", "invoice", "estimate", "booking", "thumbtack",
              "yelp", "cleaning job", "client"],
    "Hiring": ["recruiter", "indeed", "ziprecruiter", "candidate",
               "applicant", "hiring"],
    "Design": ["figma", "canva", "photoshop", "illustrator", "sketch",
               "indesign"],
    "Comms": ["gmail", "outlook", "slack", "zoom", "teams", "mail"],
    "Focus Work": ["code", "vscode", "docs.google", "sheets", "excel",
                   "word", "terminal", "notion"],
}


def _path(day: str) -> str:
    return os.path.join(BASE_DIR, f"{day}.json")


def has_breakdown(day: str) -> bool:
    return os.path.exists(_path(day))


def load_day(day: str):
    path = _path(day)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_day(doc: dict):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(_path(doc["date"]), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def has_real_activity(day: str) -> bool:
    """Whether shared/db.py has any tracked activity at all for this
    day -- used to decide whether a day can get a real breakdown or
    only a synthetic preview (e.g. a day before the app was ever run)."""
    import db
    rows = db.query("SELECT COUNT(*) FROM activity WHERE day=?", (day,))
    return bool(rows and rows[0][0] > 0)


def categorize(proc: str, title: str, flagged) -> str:
    """One activity row -> one category. Flagged (drift) rows are
    always "Break" -- reuses core/tracker.py's existing, already-
    tested drift detection instead of re-deciding it here. Otherwise,
    plain keyword match against process+title, first match wins,
    "Other" if nothing matches."""
    if flagged:
        return "Break"
    text = f"{proc or ''} {title or ''}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Other"


def build_hour_from_activity(day: str, hour: int) -> dict:
    """Real (not synthetic) breakdown for one hour of one day, built
    straight from shared/db.py's activity table. Returns an entry in
    the same shape synth_seed_day() produces, so the UI never needs to
    know which source it came from. Empty (all zeros / no entries) if
    no activity was tracked in that hour."""
    import config
    import db

    rows = db.query(
        "SELECT process, title, flagged FROM activity WHERE day=? "
        "AND CAST(strftime('%H', ts, 'unixepoch', 'localtime') AS INTEGER)=?",
        (day, hour))

    if not rows:
        return {"hour": hour, "segments": [], "label": None,
                "summary": "No activity tracked.", "apps": []}

    poll_sec = getattr(config, "WINDOW_POLL_SEC", 5)
    total_samples = len(rows)

    # tally per-category sample counts, and per-(category, app) counts
    cat_counts = {}
    app_counts = {}
    for proc, title, flagged in rows:
        cat = categorize(proc, title, flagged)
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        app_name = "Break" if cat == "Break" else (title or proc or "Unknown")
        key = (cat, app_name)
        app_counts[key] = app_counts.get(key, 0) + 1

    segments = []
    for cat, count in sorted(cat_counts.items(), key=lambda kv: -kv[1]):
        pct = round(count / total_samples * 100)
        if pct > 0:
            segments.append({"category": cat, "pct": pct})

    apps = []
    for (cat, app_name), count in sorted(app_counts.items(),
                                          key=lambda kv: -kv[1]):
        pct = round(count / total_samples * 100)
        if pct <= 0:
            continue
        duration_min = round(count * poll_sec / 60)
        apps.append({"name": app_name, "category": cat, "pct": pct,
                     "duration_min": duration_min})

    if segments:
        majority = max(segments, key=lambda s: s["pct"])
        label = (majority["category"] if majority["category"] in TAG_WORTHY
                 and majority["pct"] >= 40 else None)
        summary = "Mostly " + ", ".join(
            f"{s['category']} ({s['pct']}%)" for s in segments[:3])
    else:
        label, summary = None, "No activity tracked."

    return {"hour": hour, "segments": segments, "label": label,
            "summary": summary, "apps": apps}


def build_day_from_activity(day: str) -> dict:
    """Real breakdown for a full day, all 24 hours, straight from the
    activity table. Idempotent -- safe to call repeatedly (e.g. every
    few minutes while the app runs), always recomputes from the raw
    log rather than patching incrementally, so it can never drift out
    of sync with what's actually in the database."""
    hours = [build_hour_from_activity(day, h) for h in range(24)]
    doc = {"date": day, "hours": hours, "synthetic": False}
    save_day(doc)
    return doc


def refresh_today():
    """Called on a timer (see main.py) so the calendar has a
    continually-updating real record of today, hour by hour, as the
    day happens -- not just once it's over."""
    from datetime import date
    build_day_from_activity(date.today().isoformat())


def synth_seed_day(day: str) -> dict:
    """Generates plausible-looking (fake) hourly data for `day`, purely
    so the person can preview the UI shape before the real activity-
    based aggregator is built. Deterministic per day (same day always
    regenerates the same preview) so re-opening it doesn't reshuffle
    what you already looked at. Overwrites any existing file for that
    day -- this is preview data, not meant to be precious."""
    random.seed(day)

    app_pool = {
        "Focus Work": ["VS Code", "Google Docs", "Terminal"],
        "Sales": ["Gmail Inbox", "Phone Dialer", "CRM"],
        "Hiring": ["LinkedIn Recruiter Search", "Indeed", "Gmail Inbox"],
        "Design": ["Figma Dashboard Design", "Figma Recruiter", "Canva"],
        "Comms": ["Slack", "Gmail Inbox", "Zoom"],
        "Break": ["Break"],
    }

    hours = []
    for h in range(24):
        if 8 <= h <= 18:
            cats = random.sample(list(app_pool.keys()),
                                 k=random.choice([1, 2]))
        else:
            cats = ["Break"] if random.random() < 0.7 else \
                   random.sample(list(app_pool.keys()), k=1)

        pcts = _random_pcts(len(cats))
        segments = [{"category": c, "pct": p} for c, p in zip(cats, pcts)]

        apps = []
        for cat, pct in zip(cats, pcts):
            app_name = random.choice(app_pool[cat])
            apps.append({
                "name": app_name, "category": cat, "pct": pct,
                "duration_min": round(pct / 100 * 60),
            })

        majority = max(segments, key=lambda s: s["pct"])
        label = (majority["category"]
                 if majority["category"] in TAG_WORTHY and majority["pct"] >= 40
                 else None)
        summary = "Mostly " + ", ".join(
            f"{s['category']} ({s['pct']}%)" for s in segments)

        hours.append({
            "hour": h, "segments": segments, "label": label,
            "summary": summary, "apps": apps,
        })

    doc = {"date": day, "hours": hours, "synthetic": True}
    save_day(doc)
    return doc


def _random_pcts(n):
    if n == 1:
        return [100]
    first = random.randint(55, 75)
    if n == 2:
        return [first, 100 - first]
    parts = [first]
    remaining = 100 - first
    for i in range(n - 2):
        p = remaining // (n - 1 - i)
        parts.append(p)
        remaining -= p
    parts.append(remaining)
    return parts
