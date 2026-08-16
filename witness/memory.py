"""Memory system. Builds a rolling context window from recent history
so every AI call knows what happened yesterday, last week, and what
patterns have emerged. This is what makes it feel alive.
"""
import os
import glob
from datetime import date, timedelta

import config
import db
import data


def build_context(days_back=7) -> str:
    """Build a memory block for AI prompts. Includes:
    - Recent daily recaps (last 3-5 days)
    - Recent check-in answers (last 2 days)
    - SOS events and outcomes
    - Pattern observations
    - Win history
    - Score trajectory
    """
    sections = []

    # 1. Recent recaps (the richest source)
    recaps = sorted(glob.glob(os.path.join(config.RECAP_DIR, "*.txt")))
    recent_recaps = recaps[-5:]  # last 5 days
    if recent_recaps:
        recap_text = []
        for rp in recent_recaps:
            day_str = os.path.basename(rp).replace(".txt", "")
            try:
                content = open(rp, encoding="utf-8").read()[:600]
                recap_text.append(f"[{day_str}] {content}")
            except Exception:
                pass
        if recap_text:
            sections.append("RECENT DAILY RECAPS:\n" + "\n".join(recap_text))

    # 2. Recent check-in answers (what they said, what they were feeling)
    since = (date.today() - timedelta(days=2)).isoformat()
    try:
        rows = db._conn.execute(
            "SELECT day, kind, question, answer FROM checkins "
            "WHERE day>=? ORDER BY ts DESC LIMIT 15",
            (since,)).fetchall()
        if rows:
            checkin_text = []
            for day, kind, q, a in rows:
                checkin_text.append(f"[{day} {kind}] Q: {q} A: {a}")
            sections.append("RECENT CHECK-IN ANSWERS:\n" +
                            "\n".join(checkin_text))
    except Exception:
        pass

    # 3. SOS history (patterns in urges)
    try:
        sos_rows = db._conn.execute(
            "SELECT day, trigger, outcome FROM sos ORDER BY ts DESC LIMIT 8"
        ).fetchall()
        if sos_rows:
            sos_text = [f"[{d}] trigger: {t} | outcome: {o}"
                        for d, t, o in sos_rows]
            sections.append("SOS HISTORY (urge patterns):\n" +
                            "\n".join(sos_text))
    except Exception:
        pass

    # 4. Score trajectory
    scores = db.recent_scores(14)
    if scores:
        score_line = ", ".join(f"{d}: {s}%" for d, s in scores)
        sections.append(f"DAILY SCORES (last 14 days): {score_line}")

    # 5. Recent wins
    d = data.load()
    recent_wins = d["wins"][-10:]
    if recent_wins:
        win_text = "; ".join(f"[{w['date']}] {w['text']}"
                             for w in recent_wins)
        sections.append(f"WINS: {win_text}")

    # 6. Learned patterns (what apps are normal per block)
    try:
        profiles = db._conn.execute(
            "SELECT block_label, app, avg_pct FROM learned_profiles "
            "WHERE avg_pct >= 10 ORDER BY block_label, avg_pct DESC"
        ).fetchall()
        if profiles:
            from collections import defaultdict
            by_block = defaultdict(list)
            for block, app, pct in profiles:
                by_block[block].append(f"{app} {pct:.0f}%")
            pattern_text = "; ".join(
                f"{b}: {', '.join(apps)}" for b, apps in by_block.items())
            sections.append(f"LEARNED APP PATTERNS: {pattern_text}")
    except Exception:
        pass

    if not sections:
        return "(No history yet — this is early in the journey.)"

    return "\n\n".join(sections)


def enrich_prompt(base_prompt: str) -> str:
    """Add memory context to any AI prompt."""
    mem = build_context()
    # keep memory under ~2000 chars to leave room for the actual prompt
    if len(mem) > 2000:
        mem = mem[:2000] + "...(truncated)"
    return (f"MEMORY — what you know from recent days:\n{mem}\n\n"
            f"Use this memory naturally. Reference specific things they said, "
            f"patterns you've noticed, wins they've had, and score trends "
            f"when relevant. Don't list everything — pick what fits the "
            f"moment. If you notice a recurring pattern (same struggle on "
            f"same day, SOS at similar times, consistent drift after lunch), "
            f"name it.\n\n{base_prompt}")
