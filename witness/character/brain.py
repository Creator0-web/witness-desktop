"""Unified brain. ONE AI entity that sees the full conversation + all
system events and responds as a single coherent personality.

Every event (arrival, drift, check-in, SOS, pattern detection, user chat)
flows through here. The brain decides what to say, when to stay quiet,
and how to respond based on the full context of the day.

Actions: if the user reports something (relapse, win, mood), the brain
includes ACTION tags that the caller parses to update the system.
"""
import json
import os
import time
from datetime import datetime

import config
import data
import memory
import game_engine
import game_analytics
# Trimmed: lifedata, strategist, finance, pipeline, stats_engine, journal
# were removed from the brain's context — their UI panels are disabled
# (see main.py show_menu) so this data was going stale/empty anyway.
# The real analysis layer going forward is insight/ (raw_stats.py +
# distiller.py) — not yet wired in here; see DEVLOG.md.

_client = None


def _get_client():
    global _client
    if _client is None and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            _client = anthropic.Anthropic()
        except Exception:
            _client = False
    return _client or None


def _est_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime(
            "%A %Y-%m-%d %I:%M %p EST")
    except Exception:
        return datetime.now().strftime("%A %Y-%m-%d %I:%M %p")


# ── The personality ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You're Witness. You're like a sharp friend sitting next to this person all day. You can see their screen and camera. You know their scoring rules, current battle, and history.

Rules:
1. Keep it short. 1-2 sentences usually. 3 max.
2. Plain text only. No asterisks, no bold, no emoji, no bullet points, no markdown. Ever.
3. You know the current time (given below as CURRENT TIME). Use it. Never ask what time it is.
4. Don't repeat yourself. Don't say "I understand" or "I hear you."
5. Be real. Be direct. Be human. Like texting a friend you respect.
6. Events show up as [EVENT: ...] - just react naturally to what happened.
7. When there's nothing worth saying, respond with just the word SKIP.

If the user tells you something that should update the system, put one action tag on its own line at the very end. Never mention these in your spoken text:
ACTION:LOG_REDLINE - they reported a relapse
ACTION:LOG_WIN:description - they shared a win  
ACTION:LOG_SOS:trigger - urge moment
ACTION:LIFE:field:value - life data like sleep_hours:7 or mood:8
ACTION:CLEAN_RESET:days_ago - relapse N days ago
"""


def respond(conversation_history, event=None, context=None):
    """Generate a response from the unified brain.

    conversation_history: list of {"role": "user"|"assistant"|"system", "content": str}
    event: optional event string like "User arrived at desk" or "Drift detected..."
    context: optional dict with current state info

    Returns: {"text": str, "actions": list[str]}
    """
    client = _get_client()
    if client is None:
        return _offline_response(event)

    # Build context from the canonical self-competition engine. Legacy goal
    # projections/task percentages are intentionally no longer the brain's
    # definition of success; the person's manual Activity XP is.
    mem = memory.build_context()

    try:
        snap = game_engine.dashboard_snapshot()
        daily = snap["daily_battle"]
        weekly = snap["weekly_campaign"]
        lvl = snap["level"]
        game_ctx = (
            f"Daily fight: YOU {daily['you']} XP vs Ghost {daily['ghost']} XP "
            f"(gap {daily['gap']:+d}, {daily['status']}). Ghost final: {daily['ghost_final']} XP.\n"
            f"Weekly campaign: YOU {weekly['you']} XP vs prior-week Ghost {weekly['ghost']} XP "
            f"(gap {weekly['gap']:+d}, {weekly['status']}).\n"
            f"Rolling level: Lv.{lvl['current_level']} {lvl['name']}, rating {lvl['rating']}, "
            f"peak Lv.{lvl['peak_level']}, comeback={lvl['comeback_active']}, at_risk={lvl['at_risk']}."
        )
        acts = []
        for a in snap.get("activities", []):
            st = a.get("today", {})
            acts.append(f"  {a['name']}: {st.get('units', 0):g} units, {st.get('score_xp', 0)} XP today; rule={a['xp_value']} XP ({a['kind']})")
        activity_ctx = "Scoring Activities today:\n" + ("\n".join(acts) if acts else "  none configured")
    except Exception:
        game_ctx = "Game backend unavailable for this response."
        activity_ctx = ""

    try:
        insight = game_analytics.correlations(days=60)
        if insight.get("ready") and insight.get("correlations"):
            r = insight["correlations"][0]
            insight_ctx = (f"Top observed association ({r['sample_days']} days): "
                           f"{r['label']} — {r['association']} ({r['strength']}, r={r['spearman_r']:+.2f}). "
                           "Association is not proof of causation.")
        else:
            insight_ctx = f"Behavior analytics not ready yet ({insight.get('tracked_days', 0)} tracked/scored days)."
    except Exception:
        insight_ctx = "Behavior analytics unavailable."

    try:
        import difficulty
        diff = difficulty.difficulty_context()
    except Exception:
        diff = ""

    now = _est_now()
    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CURRENT TIME: {now} (USE THIS — never say you don't know the time)\n"
        f"CURRENT GAME STATE:\n{game_ctx}\n\n"
        f"{activity_ctx}\n\n"
        f"BEHAVIOR INSIGHT:\n{insight_ctx}\n"
        f"DIFFICULTY / PROTECTION STATE: {diff}\n\n"
        f"MEMORY (recent days):\n{mem}\n"
    )

    # add event as a system message if provided
    messages = []
    for msg in conversation_history[-30:]:  # last 30 messages
        role = msg.get("role", "user")
        if role == "system":
            role = "user"  # API doesn't support system in messages
            content = f"[EVENT: {msg['content']}]"
        else:
            content = msg["content"]
        messages.append({"role": role, "content": content})

    if event:
        messages.append({"role": "user", "content": f"[EVENT: {event}]"})

    if not messages:
        messages.append({"role": "user", "content": "[EVENT: Session started]"})

    # ensure alternating roles
    cleaned = []
    last_role = None
    for msg in messages:
        if msg["role"] == last_role:
            # merge with previous
            cleaned[-1]["content"] += "\n" + msg["content"]
        else:
            cleaned.append(msg)
            last_role = msg["role"]

    # ensure first message is user
    if cleaned and cleaned[0]["role"] == "assistant":
        cleaned.insert(0, {"role": "user", "content": "[EVENT: Context loaded]"})

    try:
        resp = client.messages.create(
            model=config.SMART_MODEL,
            max_tokens=300,
            system=system,
            messages=cleaned,
        )
        text = resp.content[0].text.strip()

        # parse actions
        actions = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("ACTION:"):
                actions.append(line)

        # remove action lines from spoken text
        spoken = "\n".join(l for l in text.split("\n")
                           if not l.strip().startswith("ACTION:")).strip()

        # skip empty or "..." responses
        if spoken in ("", "...", "…"):
            return {"text": "", "actions": actions}

        return {"text": spoken, "actions": actions}

    except Exception as e:
        return _offline_response(event)


def _offline_response(event=None):
    """Fallback when no API key is set."""
    import random
    if event and "arrived" in str(event).lower():
        return {"text": "Morning. API key not set — running in offline mode. "
                        "Set it up and I'll actually be here.", "actions": []}
    if event and "drift" in str(event).lower():
        return {"text": "You're drifting. Get back to work.", "actions": []}
    if event and "red" in str(event).lower():
        return {"text": "Red line. Close it. Now.", "actions": []}
    return {"text": "", "actions": []}


def reset_conversation():
    """Clear conversation history to start fresh with new personality."""
    try:
        with open("conversation.json", "w") as f:
            json.dump([], f)
    except Exception:
        pass
