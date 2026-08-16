"""Focus score (0-100) based primarily on task completion,
with drift/redline as a secondary modifier."""
from datetime import date, datetime

import db
import data


def today_score() -> int:
    """Score = task_completion (0-100) modified by drift behavior."""
    tasks = data.get_tasks()
    now = datetime.now().strftime("%H:%M")

    if not tasks:
        return 0  # no plan = 0%, not 100%

    # task completion: tasks due by now should be done
    due_count = 0
    done_count = 0
    future_count = 0
    for t in tasks:
        by_time = t.get("by", "23:59")
        if by_time <= now:
            due_count += 1
            if t.get("done"):
                done_count += 1
        else:
            future_count += 1
            if t.get("done"):
                done_count += 1

    total = len(tasks)
    if total == 0:
        return 0

    # base: percentage of all tasks done, weighted toward overdue ones
    task_pct = (done_count / total) * 100

    # drift/redline modifier (can subtract up to 15 points)
    raw = db.today_raw()
    if raw["samples"] > 0:
        drift_frac = raw["flagged"] / raw["samples"]
        drift_penalty = drift_frac * 10
        redline_penalty = raw["redlines"] * 5
    else:
        drift_penalty = 0
        redline_penalty = 0

    score = task_pct - drift_penalty - redline_penalty
    return max(0, min(100, int(score)))


def streak_info():
    """Returns (days_above_70, is_record_today, avg7)."""
    rows = db.recent_scores(30)
    scores = {d: s for d, s in rows}
    today = date.today().isoformat()
    scores[today] = today_score()

    ordered = sorted(scores.items())
    streak = 0
    for d, s in reversed(ordered):
        if s >= 70:
            streak += 1
        else:
            break

    past = [s for d, s in ordered if d != today]
    is_record = bool(past) and scores[today] > max(past)

    last7 = [s for d, s in ordered[-7:]]
    avg7 = int(sum(last7) / len(last7)) if last7 else scores[today]
    return streak, is_record, avg7


def projection_line(money: dict, avg7: int) -> str:
    cur_hours = round(6 * (avg7 / 100) * 30)
    better = min(avg7 + 15, 95)
    better_hours = round(6 * (better / 100) * 30)
    gap = money["target_monthly"] - money["current_monthly"]
    line = (f"7-day focus avg {avg7}% = {cur_hours} focused hrs/mo. "
            f"At {better}%: {better_hours} hrs (+{better_hours - cur_hours}).")
    if gap > 0:
        line += f" Gap to target: ${gap}/mo."
    return line


def momentum(today_s=None):
    """Compare today's score to yesterday at this time. Returns arrow str."""
    rows = db.recent_scores(2)
    if len(rows) < 1:
        return ""
    yesterday_final = rows[-1][1] if rows else 0
    cur = today_s if today_s is not None else today_score()
    if cur > yesterday_final + 5:
        return " ↑"
    elif cur < yesterday_final - 5:
        return " ↓"
    return " →"
