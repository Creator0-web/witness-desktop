"""Financial projection. Connects productivity data to financial outcomes.
Shows: at current trajectory when do you hit your target? What changes
would accelerate it? The math behind the motivation.
"""
import json
from datetime import date, timedelta

import data
import db


def project():
    """Generate financial projection based on current data."""
    d = data.load()
    m = d["money"]

    target = m["target_monthly"]
    current = m["current_monthly"]
    gap = target - current

    # get recent scores for productivity trend
    scores = db.recent_scores(30)
    if not scores:
        return {
            "current": current,
            "target": target,
            "gap": gap,
            "message": "Need more data — keep tracking.",
            "scenarios": [],
        }

    score_vals = [s for _, s in scores]
    avg_score = int(sum(score_vals) / len(score_vals))
    recent_7 = score_vals[-7:] if len(score_vals) >= 7 else score_vals
    avg_7 = int(sum(recent_7) / len(recent_7))

    # estimate productive hours per month
    def monthly_hours(pct):
        return round(6 * (pct / 100) * 22)  # 6 trackable hrs/day, 22 work days

    current_hours = monthly_hours(avg_7)

    # revenue per productive hour (if we have revenue data)
    rev_per_hour = None
    if current > 0 and current_hours > 0:
        rev_per_hour = round(current / current_hours, 2)

    # build scenarios
    scenarios = []

    # current trajectory
    if rev_per_hour and rev_per_hour > 0:
        months_at_current = None
        if current < target:
            # assume revenue grows proportionally with focus
            # rough model: each 10% focus increase = proportional revenue increase
            growth_rate = 0.15  # 15% monthly growth estimate
            projected = current
            months = 0
            while projected < target and months < 24:
                projected *= (1 + growth_rate)
                months += 1
            months_at_current = months
        scenarios.append({
            "name": "Current pace",
            "focus_pct": avg_7,
            "hours_mo": current_hours,
            "rev_per_hour": rev_per_hour,
            "projected_monthly": current,
            "months_to_target": months_at_current,
            "note": f"At {avg_7}% focus = {current_hours} hrs/mo "
                    f"× ${rev_per_hour}/hr = ${current}/mo"
        })

    # improved scenario
    improved_pct = min(avg_7 + 15, 90)
    improved_hours = monthly_hours(improved_pct)
    if rev_per_hour:
        improved_rev = round(improved_hours * rev_per_hour)
        scenarios.append({
            "name": f"At {improved_pct}% focus",
            "focus_pct": improved_pct,
            "hours_mo": improved_hours,
            "projected_monthly": improved_rev,
            "note": f"+{improved_hours - current_hours} hrs/mo = "
                    f"+${improved_rev - current}/mo potential"
        })

    # target scenario — what focus level is needed
    if rev_per_hour and rev_per_hour > 0:
        needed_hours = target / rev_per_hour
        needed_pct = min(100, int((needed_hours / (6 * 22)) * 100))
        scenarios.append({
            "name": f"To hit ${target}/mo",
            "focus_pct": needed_pct,
            "hours_mo": int(needed_hours),
            "note": f"Need {int(needed_hours)} hrs/mo = {needed_pct}% focus "
                    f"(or increase $/hr from ${rev_per_hour} to "
                    f"${round(target / current_hours, 2)})"
        })
    else:
        scenarios.append({
            "name": "Revenue tracking",
            "note": "Update your Money panel with current monthly revenue "
                    "to unlock projections."
        })

    # trend direction
    if len(score_vals) >= 14:
        first_half = score_vals[:len(score_vals)//2]
        second_half = score_vals[len(score_vals)//2:]
        trend = int(sum(second_half)/len(second_half)) - \
                int(sum(first_half)/len(first_half))
        trend_word = "improving" if trend > 3 else \
                     "declining" if trend < -3 else "steady"
    else:
        trend = 0
        trend_word = "too early to tell"

    return {
        "current": current,
        "target": target,
        "gap": gap,
        "avg_score": avg_score,
        "avg_7day": avg_7,
        "productive_hours_mo": current_hours,
        "rev_per_hour": rev_per_hour,
        "trend": trend_word,
        "scenarios": scenarios,
        "deadline": m.get("deadline_note", ""),
    }


def summary_for_brain():
    """Compact projection summary for brain context."""
    p = project()
    lines = [f"Financial: ${p['current']}/mo → ${p['target']}/mo "
             f"(gap: ${p['gap']}). Trend: {p.get('trend', '?')}."]
    for s in p.get("scenarios", [])[:2]:
        lines.append(f"  {s['name']}: {s.get('note', '')}")
    return "\n".join(lines)
