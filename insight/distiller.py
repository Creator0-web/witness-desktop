"""The distiller. Turns raw_stats (pure numbers) into short, readable
'colored documents': a plain-language summary plus a short list of
pattern hypotheses. Numbers always come from raw_stats, never from the
AI -- the AI's only job is describing them and, at the weekly level,
pointing out repeats across days. Every hypothesis below must name the
specific days that support it, so nothing in a colored document is a
claim without a receipt.

Works with or without an API key. Offline, it falls back to a plain
template built directly from the numbers -- still useful, just less
readable.
"""
import json

import config
import data
import raw_stats
import store
import ai as shared_ai


def _goal_line() -> str:
    """The single goal, read fresh every call so an edited mission
    always shows up immediately. This is threaded into every prompt
    below so the AI frames findings and suggestions against this
    specific goal, not generic productivity advice."""
    try:
        mission = data.load().get("mission", "")
    except Exception:
        mission = ""
    return f"GOAL (the one thing being optimized for): {mission}\n\n" if mission else ""


def build_daily(day: str) -> dict:
    stats = raw_stats.day_stats(day)

    # If Stripe sync is configured, it's authoritative for revenue --
    # skip note-based extraction entirely so nothing can double-count
    # a payment that's already synced from Stripe. Notes still get
    # read for the summary text above; they just stop being a source
    # of dollar figures once a real payment processor is connected.
    import stripe_sync
    if stripe_sync.is_configured():
        revenue_events = []
    else:
        revenue_events = _extract_revenue(stats["notes"])

    import db
    db.replace_revenue_events_for_day(day, revenue_events)
    doc = {
        "date": day,
        "type": "daily",
        "stats": stats,
        "summary": _daily_summary(stats),
        "revenue_events": [{"amount": a, "note": n} for a, n in revenue_events],
    }
    store.save_daily(doc)
    return doc


def _extract_revenue(notes: list) -> list:
    """Scans a day's notes for dollar amounts tied to actual income --
    sales, payments, closed deals. Conservative on purpose: only pulls
    a number when the note clearly states money that came IN, never
    expenses, hopes, or hypotheticals. Returns [(amount, excerpt), ...].
    """
    if not notes:
        return []

    prompt = (
        "Notes a person wrote today:\n" +
        "\n".join(f"- {n}" for n in notes) + "\n\n"
        "Find any dollar amounts that represent money actually received "
        "-- a sale, a payment, a closed deal. Do NOT include expenses, "
        "goals, hopes, prices mentioned in passing, or anything "
        "hypothetical. If a note doesn't clearly state income received, "
        "skip it.\n"
        "Output STRICT JSON array of objects with keys \"amount\" (number, "
        "no $ or commas) and \"note\" (the relevant note text, verbatim). "
        "If nothing qualifies, output an empty array []. Output only the "
        "JSON array.")
    out = shared_ai._ask(config.FAST_MODEL, prompt, 200)

    if out:
        try:
            clean = out.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)
            results = []
            for item in parsed:
                amt = item.get("amount")
                if isinstance(amt, (int, float)) and amt > 0:
                    results.append((float(amt), str(item.get("note", ""))[:200]))
            return results
        except Exception:
            pass

    # Offline fallback: rough regex for "$123" patterns. Approximate on
    # purpose -- better than nothing when there's no API key, but this
    # is the one place in the pipeline that can't fully ground itself
    # without the AI reading intent, so it may over- or under-catch.
    import re
    results = []
    for n in notes:
        for m in re.findall(r"\$([\d,]+(?:\.\d+)?)", n):
            try:
                amt = float(m.replace(",", ""))
                if amt > 0:
                    results.append((amt, n[:200]))
            except ValueError:
                pass
    return results


def _daily_summary(stats: dict) -> str:
    if stats["samples"] < 10 and not stats["notes"]:
        return "Not enough tracked activity today for a summary."

    notes_block = ""
    if stats["notes"]:
        notes_block = ("The person's own notes from today, in their own "
                        f"words:\n" + "\n".join(f"- {n}" for n in stats["notes"]) + "\n\n")

    prompt = (
        f"{_goal_line()}"
        "Here is one day of behavioral tracking data from a focus app, as "
        f"plain numbers:\n{json.dumps({k: v for k, v in stats.items() if k != 'notes'})}\n\n"
        f"{notes_block}"
        "Write 1-2 plain, direct sentences describing what the data (and "
        "notes, if present) show about progress toward the stated goal "
        "today. If notes are present, let them carry real weight -- "
        "they're the person's own account, more informative than the "
        "numbers alone. No advice, no encouragement, no speculation "
        "beyond what's given. Output only the sentences.")
    out = shared_ai._ask(config.FAST_MODEL, prompt, 150)
    if out:
        return out.strip()

    parts = []
    if stats["focus_score"] is not None:
        parts.append(f"Focus score {stats['focus_score']}%.")
    if stats["peak_hour"] is not None:
        parts.append(f"Best focus around {stats['peak_hour']}:00, "
                      f"weakest around {stats['worst_hour']}:00.")
    if stats["redline_events"]:
        parts.append(f"{stats['redline_events']} red-line event(s).")
    if stats["sos_events"]:
        parts.append(f"{stats['sos_events']} SOS event(s).")
    if stats["notes"]:
        parts.append(f"{len(stats['notes'])} note(s) logged: " +
                      " / ".join(stats["notes"][:3]))
    return " ".join(parts) or "Logged, no notable pattern yet."


def build_suggestions(for_day: str) -> dict:
    """3 suggestions for `for_day` (normally today), grounded in the most
    recent evidence available: yesterday's colored document and the
    latest weekly correlations, if any exist yet. Not a task list --
    these are meant to sit above tasks as a small, evidence-based nudge,
    regenerated fresh each day.
    """
    from datetime import date, timedelta
    yesterday = (datetime_strptime(for_day) - timedelta(days=1)).isoformat()
    y_doc = store.load_daily(yesterday)

    latest_weekly = None
    for wk in reversed(store.list_weekly()):
        latest_weekly = store.load_weekly(wk)
        break

    if not y_doc and not latest_weekly:
        doc = {"date": for_day, "type": "suggestions",
               "suggestions": ["Not enough data yet -- suggestions start "
                               "once a full day has been tracked."]}
        store.save_suggestions(doc)
        return doc

    evidence = {
        "yesterday_summary": y_doc.get("summary") if y_doc else None,
        "yesterday_stats": {k: v for k, v in y_doc.get("stats", {}).items()
                             if k not in ("hourly_focus", "notes")} if y_doc else None,
        "yesterday_notes": y_doc.get("stats", {}).get("notes", []) if y_doc else [],
        "weekly_correlations": latest_weekly.get("correlations", [])
        if latest_weekly else [],
    }

    prompt = (
        f"{_goal_line()}"
        f"Evidence about this person, most recent first:\n{json.dumps(evidence)}\n\n"
        "Write exactly 3 short, specific suggestions for TODAY that would "
        "move the person toward the stated goal above. Each must be "
        "traceable to something in the evidence -- a stat, a correlation, "
        "or something they wrote in their own notes -- AND connect to the "
        "goal, not just to feeling more productive in general. Do not "
        "invent advice that isn't grounded in the evidence. If the "
        "evidence is thin, say so in the suggestion rather than padding "
        "it with generic advice.\n"
        "Output STRICT JSON array of exactly 3 short strings (each one "
        "sentence). Output only the JSON array.")
    out = shared_ai._ask(config.SMART_MODEL, prompt, 300)

    suggestions = None
    if out:
        try:
            clean = out.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)
            if isinstance(parsed, list) and parsed:
                suggestions = [str(s) for s in parsed[:3]]
        except Exception:
            suggestions = None

    if not suggestions:
        suggestions = _offline_suggestions(evidence)

    doc = {"date": for_day, "type": "suggestions", "suggestions": suggestions}
    store.save_suggestions(doc)
    return doc


def _offline_suggestions(evidence: dict) -> list:
    """Plain fallback when there's no API key -- built straight from the
    numbers, no fabricated advice."""
    out = []
    stats = evidence.get("yesterday_stats")
    if stats:
        if stats.get("worst_hour") is not None:
            out.append(f"Yesterday's weakest hour was {stats['worst_hour']}:00 "
                        "-- worth a shorter block or a break there today.")
        if stats.get("redline_events"):
            out.append(f"{stats['redline_events']} red-line event(s) "
                        "yesterday -- notice what preceded them today.")
    for corr in evidence.get("weekly_correlations", [])[:2]:
        out.append(corr.get("pattern", ""))
    if not out:
        out.append("Not enough evidence yet for a specific suggestion -- "
                    "keep tracking and this will sharpen up.")
    return out[:3]


def datetime_strptime(day_str: str):
    from datetime import datetime
    return datetime.strptime(day_str, "%Y-%m-%d").date()


def build_weekly(week_start: str) -> dict:
    wstats = raw_stats.week_stats(week_start)
    daily_docs = [store.load_daily(d["day"]) or build_daily(d["day"])
                  for d in wstats["days"]]

    doc = {
        "week_start": week_start,
        "week_end": wstats["week_end"],
        "type": "weekly",
        "stats": {k: v for k, v in wstats.items() if k != "days"},
        "summary": _weekly_summary(wstats, daily_docs),
        "correlations": _weekly_correlations(wstats),
    }
    store.save_weekly(doc)
    return doc


def _weekly_summary(wstats: dict, daily_docs: list) -> str:
    if wstats["days_logged"] < 3:
        return "Not enough days logged this week for a summary."

    prompt = (
        f"{_goal_line()}"
        "One week of a focus app's stats and daily summaries:\n"
        f"Week stats: {json.dumps({k: v for k, v in wstats.items() if k != 'days'})}\n"
        f"Daily summaries: {json.dumps([d.get('summary') for d in daily_docs if d])}\n\n"
        "Write 2-3 plain sentences describing how the week went relative "
        "to the stated goal, using the actual numbers. No advice, no "
        "encouragement. Output only the sentences.")
    out = shared_ai._ask(config.SMART_MODEL, prompt, 200)
    if out:
        return out.strip()

    avg = wstats.get("avg_score")
    if avg is None:
        return "Not enough data yet."
    return (f"Week average {avg}%. Best day: {wstats.get('best_day')}. "
            f"Worst day: {wstats.get('worst_day')}. "
            f"{wstats.get('total_sos')} SOS event(s), "
            f"{wstats.get('total_redlines')} red-line event(s).")


def _weekly_correlations(wstats: dict) -> list:
    """Returns up to 3 {pattern, days_supporting, evidence_count,
    confidence}. confidence is categorical (low/medium/high), never a
    made-up decimal -- and evidence_count is counted in Python from
    the days the AI actually cited, not asserted by the AI itself."""
    if wstats["days_logged"] < 4:
        return []

    compact_days = [{
        "day": d["day"], "focus_score": d["focus_score"],
        "peak_hour": d["peak_hour"], "worst_hour": d["worst_hour"],
        "redline_events": d["redline_events"], "sos_events": d["sos_events"],
    } for d in wstats["days"]]

    prompt = (
        f"{_goal_line()}"
        f"One week of daily focus-app data, per day:\n{json.dumps(compact_days)}\n\n"
        "Find at most 3 real patterns across these days (e.g. a specific "
        "hour that's consistently weak, redline/SOS events clustering on "
        "certain days). Only report a pattern if at least 2 specific days "
        "support it. If nothing repeats, return an empty list.\n"
        "Output STRICT JSON array of objects with keys:\n"
        '  "pattern": one plain sentence\n'
        '  "days_supporting": array of the exact day strings from the data\n'
        '  "confidence": exactly one of "low", "medium", "high" '
        "(high only if 4+ days support it)\n"
        "Output only the JSON array.")
    out = shared_ai._ask(config.SMART_MODEL, prompt, 400)
    if not out:
        return []

    try:
        clean = out.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        results = []
        for item in parsed:
            days = item.get("days_supporting", [])
            if isinstance(days, list) and len(days) >= 2:
                conf = item.get("confidence")
                results.append({
                    "pattern": str(item.get("pattern", "")),
                    "days_supporting": days,
                    "evidence_count": len(days),
                    "confidence": conf if conf in ("low", "medium", "high")
                    else "low",
                })
        return results[:3]
    except Exception:
        return []
