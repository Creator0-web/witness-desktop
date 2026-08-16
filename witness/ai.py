"""All AI generation. Works offline with built-in fallbacks; comes alive
with ANTHROPIC_API_KEY set. Escalation targets stakes and identity — never shame.
"""
import json
import os
import random

import config
import memory
import difficulty
import data

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
        from datetime import datetime
        return datetime.now(ZoneInfo("America/New_York")).strftime(
            "%A %Y-%m-%d %I:%M %p EST")
    except Exception:
        from datetime import datetime
        return datetime.now().strftime("%A %Y-%m-%d %I:%M %p")


def _ask(model, prompt, max_tokens=300):
    client = _get_client()
    if client is None:
        return None
    prompt = f"Current date/time: {_est_now()}\n" + prompt
    try:
        r = client.messages.create(model=model, max_tokens=max_tokens,
                                   messages=[{"role": "user", "content": prompt}])
        return r.content[0].text.strip()
    except Exception:
        return None


def _persona():
    try:
        diff = difficulty.difficulty_context()
    except Exception:
        diff = ""
    return (
        "You are WITNESS: the user's accountability partner during a 90-day "
        "transformation. Voice: direct, human, brief — a coach who believes in "
        "them, not a drill sergeant, not a therapist. Use their stakes and goals. "
        "NEVER shame them about the past; point forward. "
        "Use identity-based reinforcement — 'that's what a business owner does' "
        "not just 'good job'. When they doubt, pull identity evidence. "
        "Escalation intensity "
        f"setting: {config.ESCALATION_INTENSITY} of 3. "
        f"{diff}"
    )

_PERSONA = _persona()


# ── Escalation lines (spoken on drift) ──────────────────────────────────
_FALLBACK_ESCALATION = {
    0: ["That tab.", "Hey — this isn't the block for that.",
        "Noticed. Back to it."],
    1: ["You really think this gets you to the goal?",
        "The gap doesn't close itself. Back in.",
        "This is the fork in the road. Pick the right one."],
    2: ["This is the moment that decides it. Close it.",
        "Future you is watching this exact minute. Close the tab.",
        "You know where this path goes. Not today."],
}


def escalation_line(stage: int, app: str, title: str) -> str:
    ctx = data.goal_context()
    out = _ask(config.FAST_MODEL, memory.enrich_prompt(
        f"{_PERSONA}\nUser context:\n{ctx}\n\n"
        f"They've been drifting on: {app} — '{title[:70]}'. "
        f"Escalation stage {stage} of 3 (0=first nudge, 2=final warning before "
        "intervention). Write ONE spoken line, max 15 words, using their real "
        "stakes (city, deadline, money gap) when it fits. No quotes, no emoji. "
        "Output only the line."), 60)
    return out or random.choice(_FALLBACK_ESCALATION[min(stage, 2)])


def redline_line() -> str:
    out = _ask(config.FAST_MODEL, memory.enrich_prompt(
        f"{_PERSONA}\nUser context:\n{data.goal_context()}\n\n"
        "They just opened a site they explicitly banned for themselves (a red "
        "line tied to a compulsive pattern they're breaking). ONE spoken line, "
        "max 14 words: firm, tell them to close it now, zero shame, zero "
        "detail about the site. Output only the line."), 60)
    return out or ("Stop. Close it now. This isn't who you're becoming. "
                   "Hit SOS if you need to.")


# ── Check-ins ───────────────────────────────────────────────────────────
_FALLBACK_Q = {
    "routine": ["What are you working on right now, one sentence?",
                "Is this moving the mission forward?",
                "What did you just finish? What's next?"],
    "drift": ["What were you supposed to be doing right now?",
              "What are you avoiding? Name it."],
    "redline": ["What's actually going on right now — tired, stressed, "
                "avoiding something? Name it honestly."],
    "offtask": ["That's not on today's list. Why the detour?",
                "Off the plan. What pulled you?"],
}


def checkin_question(kind, context):
    out = _ask(config.FAST_MODEL, memory.enrich_prompt(
        f"{_PERSONA}\nUser context:\n{data.goal_context()}\n"
        f"Situation: {json.dumps(context)}\nCheck-in type: {kind}.\n"
        "ONE short check-in, max 2 sentences, ending in a question they must "
        "answer. Output only the text."), 120)
    return out or random.choice(_FALLBACK_Q[kind])


# ── Morning ─────────────────────────────────────────────────────────────
def morning_message(answers: dict, streak: int, avg7: int) -> str:
    d = data.load()
    out = _ask(config.SMART_MODEL, memory.enrich_prompt(
        f"{_PERSONA}\nUser context:\n{data.goal_context(d)}\n"
        f"Their morning answers: {json.dumps(answers)}\n"
        f"Streak: {streak} days ≥70% focus. 7-day avg: {avg7}%.\n"
        f"Today's schedule: {json.dumps(d['schedule'])}\n\n"
        "Write a spoken morning send-off, 3-5 sentences: acknowledge how they "
        "slept/last night in one clause, name today's ONE thing, connect it to "
        "the mission stakes, end with momentum. No emoji. Output only the text."),
        300)
    return out or (
        f"Morning. {streak}-day streak alive. One thing today: what you named. "
        "Every focused block closes the gap. Let's go.")


# ── SOS ─────────────────────────────────────────────────────────────────
def sos_line(stage: str) -> str:
    """stage: 'open' | 'after_video' | 'talk'"""
    d = data.load()
    wins = "; ".join(w["text"] for w in d["wins"][-5:]) or "none logged yet"
    prompts = {
        "open": "They just hit the SOS button — an urge or pull toward an old "
                "pattern. First spoken response, 2 sentences: steady, on their "
                "side, tell them the video queued up is from their own past "
                "self and to actually watch it.",
        "after_video": "They closed the SOS video early. 2 sentences: firm, "
                       "remind them THEY chose these videos for exactly this "
                       "moment; one more is starting.",
        "talk": f"Videos are done; now it's a conversation. Their recent wins: "
                f"{wins}. 3 sentences max: ground them, reflect one real win "
                "back, then ask what triggered this moment.",
    }
    out = _ask(config.SMART_MODEL, memory.enrich_prompt(
               f"{_PERSONA}\nUser context:\n{data.goal_context(d)}\n\n"
               f"{prompts[stage]} Output only the spoken text."), 200)
    fallbacks = {
        "open": "Good — you pressed it. That's the win already. Now watch "
                "the video. You picked it for exactly this moment.",
        "after_video": "You chose these videos for this exact moment. "
                       "One more. Watch it through.",
        "talk": "Still here. You've beaten this pull before — it's logged. "
                "What triggered it just now?",
    }
    return out or fallbacks[stage]


# ── Nightly recap + schedule rewrite ────────────────────────────────────
def recap_and_new_schedule(summary, today_score, streak, avg7):
    d = data.load()
    out = _ask(config.SMART_MODEL, memory.enrich_prompt(
        f"{_PERSONA}\nUser context:\n{data.goal_context(d)}\n"
        f"Planned schedule today: {json.dumps(d['schedule'])}\n"
        f"Actual day data: {json.dumps(summary)}\n"
        f"Focus score: {today_score}%. Streak: {streak}d. 7-day avg: {avg7}%.\n\n"
        "Output STRICT JSON, nothing else, keys:\n"
        '  "recap": string — the daily recap: 3-5 sentence honest narrative, '
        "then Wins, then Patterns noticed, then one hard question for "
        "tomorrow. Use \\n for line breaks. Under 280 words.\n"
        '  "schedule": array of {"start":"HH:MM","end":"HH:MM","label":str} — '
        "tomorrow's schedule, adjusted for what the data shows actually works "
        "for them (keep 4-6 blocks).\n"
        '  "spoken": string — 2 sentences to say out loud: score, streak/'
        "record if notable, one forward-looking line."), 900)
    if out:
        try:
            clean = out.replace("```json", "").replace("```", "").strip()
            j = json.loads(clean)
            if j.get("recap") and isinstance(j.get("schedule"), list):
                return j
        except Exception:
            pass
    # offline fallback
    lines = [f"DAILY RECAP — {summary['day']}",
             f"Focus score: {today_score}% | Streak: {streak}d | "
             f"Tracked {summary['minutes_tracked']} min, "
             f"drifted {summary['minutes_flagged']} min, "
             f"red lines: {summary['redline_events']}", "", "Time per app:"]
    for app, m in summary["per_app_minutes"].items():
        lines.append(f"  {app}: {m} min")
    lines += ["", "Check-ins:"]
    for c in summary["checkins"]:
        lines.append(f"  [{c['time']}] {c['question']} -> {c['answer']}")
    return {"recap": "\n".join(lines), "schedule": d["schedule"],
            "spoken": f"Day closed at {today_score} percent. "
                      f"Streak: {streak} days. Tomorrow we go again."}


# ── Chat with Witness ───────────────────────────────────────────────────
def chat(history):
    """history: list of {'role': 'user'|'assistant', 'content': str}"""
    client = _get_client()
    if client is None:
        return ("(Chat needs the API key set up — see README step 5. "
                "You can still edit goals directly with the Goals button.)")
    d = data.load()
    mem = memory.build_context()
    sys = (f"{_PERSONA}\nUser context:\n{data.goal_context(d)}\n"
           f"MEMORY:\n{mem}\n"
           "You're in a chat window inside the WITNESS app. Help them think "
           "through goals, schedule, doubts. Keep replies under 120 words. "
           "If they decide to change lifestyle/mission/goals, end your reply "
           "with a line: UPDATE: {json with any of keys lifestyle, mission, "
           "goals} — only when they've clearly decided.")
    try:
        r = client.messages.create(model=config.SMART_MODEL, max_tokens=500,
                                   system=sys, messages=history)
        return r.content[0].text.strip()
    except Exception as e:
        return f"(Chat error: {e})"


# ── Greetings (camera sees you sit down) ────────────────────────────────
def greeting_line(kind: str) -> str:
    """kind: 'first' (first sit-down of the day) | 'return' (back after away)"""
    from datetime import datetime
    hour = datetime.now().hour
    prompts = {
        "first": "The camera just saw them sit down for the first time today "
                 f"(hour: {hour}). Greet them by presence, 1-2 sentences: "
                 "warm, brief, point them at the current block or the ONE "
                 "thing. No emoji.",
        "return": "They just came back to the desk after being away a while. "
                  "1 short sentence: acknowledge the return, re-anchor them "
                  "to what they were doing. No emoji.",
    }
    out = _ask(config.FAST_MODEL,
               f"{_PERSONA}\nUser context:\n{data.goal_context()}\n\n"
               f"{prompts[kind]} Output only the spoken text.", 80)
    fallbacks = {
        "first": "There you are. Day's open — you know the one thing. "
                 "Let's put points on it.",
        "return": "Back in the chair. Pick up where you left off.",
    }
    return out or fallbacks[kind]


# ── Task planning ───────────────────────────────────────────────────────
def suggest_tasks() -> list:
    """Returns list of {text, by} dicts with deadlines."""
    d = data.load()
    # gather recent recaps for learning
    recap_context = ""
    import os, glob
    recaps = sorted(glob.glob(os.path.join(config.RECAP_DIR, "*.txt")))[-5:]
    for rp in recaps:
        try:
            recap_context += open(rp, encoding="utf-8").read()[:500] + "\n"
        except Exception:
            pass
    out = _ask(config.SMART_MODEL, (
        f"{_PERSONA}\nUser context:\n{data.goal_context(d)}\n"
        f"Schedule: {json.dumps(d['schedule'])}\n"
        f"Recent recaps (for learning patterns):\n{recap_context}\n\n"
        "Generate 4-6 concrete tasks for TODAY. Each must have a deadline. "
        "Base them on what has been working (check recaps) and what most "
        "moves the mission forward. Adjust based on patterns — if afternoons "
        "are always low, front-load important work.\n"
        "Output STRICT JSON array of objects: "
        '[{"text": "task description", "by": "HH:MM"}]. '
        "Order by deadline. Nothing else."), 400)
    if out:
        try:
            j = json.loads(out.replace("```json", "").replace("```", "").strip())
            if isinstance(j, list) and all(isinstance(x, dict) for x in j):
                return [{"text": str(x.get("text","")),
                         "by": str(x.get("by","23:59"))} for x in j][:6]
        except Exception:
            pass
    return [{"text": "Set clear goals for the day", "by": "09:00"},
            {"text": "Contact 5 warm leads", "by": "12:00"},
            {"text": "Follow up all open quotes", "by": "14:00"},
            {"text": "Work on systems/operations", "by": "16:00"},
            {"text": "Daily recap + plan tomorrow", "by": "20:00"}]


def is_on_task(window_title: str, app: str, tasks: list):
    """Return True/False/None (None = can't judge / offline)."""
    open_tasks = [t["text"] for t in tasks if not t.get("done")]
    if not open_tasks:
        return None
    out = _ask(config.FAST_MODEL, (
        f"User's declared tasks for right now: {json.dumps(open_tasks)}\n"
        f"Their active window: app={app}, title='{window_title[:90]}'\n"
        "Could this window plausibly be part of working on those tasks? "
        "Browsers/email/docs/anything work-adjacent counts as yes. Only a "
        "clear mismatch is no. Answer with exactly one word: yes or no."), 5)
    if out is None:
        return None
    return not out.strip().lower().startswith("no")
