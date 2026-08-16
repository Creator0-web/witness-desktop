"""Weekly review. Generates a comprehensive coaching session from
7 days of data — scores, patterns, wins, SOS events, metrics,
correlations. Designed to run Sunday evening.
"""
import os
import glob
import json
from datetime import date, timedelta

import config
import db
import data
import ai
import correlations
import difficulty


def generate():
    """Generate the full weekly review. Returns dict with keys:
    review (text), spoken (short spoken summary), schedule (next week template).
    """
    today = date.today()
    week_start = (today - timedelta(days=6)).isoformat()

    # gather data
    scores = db.recent_scores(7)
    d = data.load()
    metrics = data.get_metrics()
    corr = correlations.analyze()
    target, phase, days_active = difficulty.get_target()

    # recaps from the week
    recap_text = ""
    recaps = sorted(glob.glob(os.path.join(config.RECAP_DIR, "*.txt")))
    for rp in recaps[-7:]:
        try:
            day_str = os.path.basename(rp).replace(".txt", "")
            content = open(rp, encoding="utf-8").read()[:400]
            recap_text += f"[{day_str}] {content}\n"
        except Exception:
            pass

    # SOS events this week
    sos_count = 0
    try:
        sos_count = db._conn.execute(
            "SELECT COUNT(*) FROM sos WHERE day >= ?",
            (week_start,)).fetchone()[0]
    except Exception:
        pass

    # wins this week
    weekly_wins = [w for w in d["wins"]
                   if w.get("date", "") >= week_start]

    # task completion (from recaps/scores)
    score_vals = [s for _, s in scores]
    avg = int(sum(score_vals) / len(score_vals)) if score_vals else 0
    best_day = max(scores, key=lambda x: x[1]) if scores else ("?", 0)
    worst_day = min(scores, key=lambda x: x[1]) if scores else ("?", 0)

    prompt = (
        f"{ai._PERSONA}\n"
        f"User context:\n{data.goal_context(d)}\n\n"
        f"WEEKLY REVIEW DATA:\n"
        f"Week: {week_start} to {today.isoformat()}\n"
        f"Daily scores: {json.dumps(scores)}\n"
        f"Average: {avg}% | Best: {best_day[0]} ({best_day[1]}%) | "
        f"Worst: {worst_day[0]} ({worst_day[1]}%)\n"
        f"Target: {target}% ({phase})\n"
        f"SOS events: {sos_count}\n"
        f"Wins: {json.dumps([w['text'] for w in weekly_wins])}\n"
        f"Business metrics: {json.dumps(metrics.get('business', {}))}\n"
        f"Correlations found:\n" + "\n".join(f"  - {c}" for c in corr) + "\n"
        f"Daily recaps:\n{recap_text}\n\n"
        "Generate a WEEKLY REVIEW in strict JSON with keys:\n"
        '"review": Full written review (use \\n for breaks). Sections:\n'
        "  1. The Week in One Paragraph (honest narrative)\n"
        "  2. Wins (specific, from actual data)\n"
        "  3. Patterns & Correlations (cite the correlation findings)\n"
        "  4. What's Working (keep doing)\n"
        "  5. What's Not (change this)\n"
        "  6. The Hard Question (one thing they're avoiding)\n"
        "  7. Next Week's Focus (one strategic shift)\n"
        "Under 500 words total.\n"
        '"spoken": 3-4 sentences for voice — week score, key pattern, '
        "one forward push.\n"
        '"schedule": suggested weekly schedule template as array of '
        '{"start":"HH:MM","end":"HH:MM","label":str} — adjusted based on '
        "what the data shows actually works.\n"
        "Output only JSON."
    )

    out = ai._ask(config.SMART_MODEL, prompt, 1200)
    if out:
        try:
            clean = out.replace("```json", "").replace("```", "").strip()
            j = json.loads(clean)
            if j.get("review"):
                return j
        except Exception:
            pass

    # offline fallback
    return {
        "review": (
            f"WEEKLY REVIEW — {week_start} to {today.isoformat()}\n\n"
            f"Average score: {avg}% (target: {target}%)\n"
            f"Best day: {best_day[0]} at {best_day[1]}%\n"
            f"Worst day: {worst_day[0]} at {worst_day[1]}%\n"
            f"SOS events: {sos_count}\n"
            f"Wins: {len(weekly_wins)}\n\n"
            "Correlations:\n" + "\n".join(f"  {c}" for c in corr)
        ),
        "spoken": (f"Week closed at {avg} percent average. "
                   f"Target was {target}. "
                   f"{len(weekly_wins)} wins logged, {sos_count} SOS events. "
                   "Review is saved."),
        "schedule": d["schedule"],
    }


def save_review(review_data):
    """Save weekly review to file."""
    os.makedirs(config.RECAP_DIR, exist_ok=True)
    today = date.today().isoformat()
    path = os.path.join(config.RECAP_DIR, f"weekly_{today}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(review_data.get("review", ""))
    return path
