"""Strategic advisor. Runs deep analysis on ALL accumulated data and
produces specific, actionable life design recommendations.

This is the difference between "you drifted today" and "based on 3 weeks
of data, here's exactly how to structure your life for maximum output."
"""
import json
import os
import glob
from datetime import date, timedelta

import config
import db
import data
import correlations
import lifedata
import energy


def generate_strategy():
    """Generate a comprehensive strategic analysis and life design plan.
    Returns dict with strategy text, optimized schedule, milestones, and
    specific habit recommendations.
    """
    d = data.load()
    scores = db.recent_scores(60)
    life_patterns = lifedata.analyze_patterns()
    corr = correlations.analyze()
    e = energy.calculate()

    # gather all recaps
    recap_text = ""
    recaps = sorted(glob.glob(os.path.join(config.RECAP_DIR, "*.txt")))
    for rp in recaps[-14:]:
        try:
            day_str = os.path.basename(rp).replace(".txt", "")
            content = open(rp, encoding="utf-8").read()[:300]
            recap_text += f"[{day_str}] {content}\n"
        except Exception:
            pass

    # gather life data
    life_ctx = lifedata.build_context()

    # milestone progress
    milestones = d.get("milestones", [])
    milestone_ctx = json.dumps(milestones) if milestones else "No milestones set yet"

    # SOS patterns
    sos_count = 0
    try:
        sos_count = db._conn.execute(
            "SELECT COUNT(*) FROM sos").fetchone()[0]
    except Exception:
        pass

    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception:
        return _offline_strategy(scores, e, corr)

    prompt = (
        f"You are a strategic life designer analyzing a user's complete "
        f"data to create an optimized life plan.\n\n"
        f"USER CONTEXT:\n{data.goal_context(d)}\n\n"
        f"ENERGY: {e['total']}% ({e['level']}). {e['clean_days']} days clean.\n\n"
        f"SCORE HISTORY (last 60 days): {json.dumps(scores)}\n\n"
        f"CORRELATIONS FOUND:\n" + "\n".join(f"  - {c}" for c in corr) + "\n\n"
        f"LIFE DATA PATTERNS:\n{json.dumps(life_patterns, indent=1)}\n\n"
        f"LIFE CONTEXT:\n{life_ctx}\n\n"
        f"RECAPS:\n{recap_text}\n\n"
        f"CURRENT MILESTONES: {milestone_ctx}\n\n"
        f"SOS EVENTS TOTAL: {sos_count}\n\n"
        "Generate a STRATEGIC LIFE DESIGN in strict JSON with these keys:\n\n"
        '"analysis": 3-5 paragraphs of honest strategic analysis. What\'s '
        "actually working, what patterns predict success vs failure, what the "
        "data says they should change. Be specific — cite actual numbers and "
        "patterns. Don't be generic.\n\n"
        '"optimal_schedule": array of {"start":"HH:MM","end":"HH:MM","label":str} '
        "— the IDEAL daily schedule based on their energy data, peak hours, "
        "and what actually produces results. 5-7 blocks.\n\n"
        '"milestones": array of {"week":int,"target":str,"metric":str} — '
        "specific weekly milestones for the next 4 weeks that lead toward "
        "their goals. Concrete and measurable.\n\n"
        '"habits_to_add": array of strings — 3-5 specific daily habits the '
        "data shows would most improve their performance.\n\n"
        '"habits_to_remove": array of strings — 2-3 specific patterns to '
        "eliminate based on what the data shows hurts performance.\n\n"
        '"one_thing": string — the single highest-leverage change they could '
        "make this week based on all the data.\n\n"
        '"spoken": 3-4 sentences to speak aloud summarizing the key insight.\n\n'
        "Output only JSON."
    )

    try:
        resp = client.messages.create(
            model=config.SMART_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.content[0].text.strip()
        clean = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

        # save milestones if generated
        if result.get("milestones"):
            d = data.load()
            d["milestones"] = result["milestones"]
            data.save(d)

        # save optimal schedule
        if result.get("optimal_schedule"):
            d = data.load()
            d["schedule"] = result["optimal_schedule"]
            data.save(d)

        return result

    except Exception as e:
        return _offline_strategy(scores, e, corr)


def _offline_strategy(scores, e, corr):
    score_vals = [s for _, s in scores] if scores else [0]
    avg = int(sum(score_vals) / len(score_vals))
    return {
        "analysis": (f"Offline analysis. {len(scores)} days tracked. "
                     f"Average score: {avg}%. "
                     f"Correlations found: {len(corr)}."),
        "optimal_schedule": data.load().get("schedule", []),
        "milestones": [],
        "habits_to_add": ["Exercise before first work block",
                          "No phone first 30 minutes",
                          "Plan tasks before starting work"],
        "habits_to_remove": ["Browsing before work begins",
                             "Skipping breaks"],
        "one_thing": "Set up the API key for full strategic analysis.",
        "spoken": f"Average score {avg}% across {len(scores)} days.",
    }


def get_milestones():
    """Get current milestones."""
    d = data.load()
    return d.get("milestones", [])


def milestone_context():
    """Build milestone context for brain."""
    milestones = get_milestones()
    if not milestones:
        return ""
    lines = ["MILESTONES:"]
    for m in milestones:
        lines.append(f"  Week {m.get('week', '?')}: {m.get('target', '')} "
                     f"({m.get('metric', '')})")
    return "\n".join(lines)
