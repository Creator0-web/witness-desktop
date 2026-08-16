"""Correlation engine. Analyzes 2+ weeks of data to find what actually
predicts good vs bad days for THIS specific user.

Looks for: morning check-in timing, exercise, sleep quality, schedule
adherence, day-of-week patterns, SOS timing patterns, app usage correlations.
"""
import os
import glob
from datetime import date, timedelta, datetime
from collections import defaultdict

import config
import db
import data


def analyze():
    """Run full correlation analysis. Returns list of insight strings."""
    scores = dict(db.recent_scores(60))
    if len(scores) < 7:
        return ["Need at least 7 days of data for correlation analysis."]

    insights = []

    # 1. Day-of-week patterns
    dow_scores = defaultdict(list)
    for d, s in scores.items():
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            dow_scores[dt.strftime("%A")].append(s)
        except Exception:
            pass

    if dow_scores:
        avgs = {day: int(sum(ss)/len(ss)) for day, ss in dow_scores.items()
                if len(ss) >= 2}
        if avgs:
            best = max(avgs, key=avgs.get)
            worst = min(avgs, key=avgs.get)
            if avgs[best] - avgs[worst] >= 10:
                insights.append(
                    f"Day pattern: {best}s average {avgs[best]}% vs "
                    f"{worst}s at {avgs[worst]}%. Spread: "
                    f"{avgs[best] - avgs[worst]} points.")

    # 2. Morning check-in timing vs score
    try:
        rows = db._conn.execute(
            "SELECT day, MIN(ts) FROM checkins WHERE kind='morning' "
            "GROUP BY day").fetchall()
        early, late = [], []
        for d, ts in rows:
            if d in scores:
                hour = datetime.fromtimestamp(ts).hour
                if hour < 9:
                    early.append(scores[d])
                else:
                    late.append(scores[d])
        if len(early) >= 3 and len(late) >= 3:
            ea, la = int(sum(early)/len(early)), int(sum(late)/len(late))
            if abs(ea - la) >= 8:
                insights.append(
                    f"Morning timing: check-in before 9 AM → {ea}% avg. "
                    f"After 9 AM → {la}% avg. "
                    f"Difference: {ea - la} points.")
    except Exception:
        pass

    # 3. SOS day-of-week and time patterns
    try:
        sos_rows = db._conn.execute(
            "SELECT day, ts FROM sos ORDER BY ts").fetchall()
        if len(sos_rows) >= 3:
            sos_days = defaultdict(int)
            sos_hours = defaultdict(int)
            for d, ts in sos_rows:
                try:
                    dt = datetime.fromtimestamp(ts)
                    sos_days[dt.strftime("%A")] += 1
                    sos_hours[dt.hour] += 1
                except Exception:
                    pass
            if sos_days:
                peak_day = max(sos_days, key=sos_days.get)
                if sos_days[peak_day] >= 2:
                    insights.append(
                        f"SOS pattern: {peak_day}s have the most urge events "
                        f"({sos_days[peak_day]} total).")
            if sos_hours:
                peak_hour = max(sos_hours, key=sos_hours.get)
                h12 = peak_hour % 12 or 12
                sfx = "AM" if peak_hour < 12 else "PM"
                insights.append(
                    f"SOS timing: most urges hit around "
                    f"{h12} {sfx} ({sos_hours[peak_hour]} events).")
    except Exception:
        pass

    # 4. Streak momentum — do good days predict good days?
    ordered = sorted(scores.items())
    if len(ordered) >= 10:
        after_good, after_bad = [], []
        for i in range(1, len(ordered)):
            prev_s = ordered[i-1][1]
            cur_s = ordered[i][1]
            if prev_s >= 70:
                after_good.append(cur_s)
            elif prev_s < 50:
                after_bad.append(cur_s)
        if len(after_good) >= 3 and len(after_bad) >= 3:
            ag = int(sum(after_good)/len(after_good))
            ab = int(sum(after_bad)/len(after_bad))
            insights.append(
                f"Momentum: day after a 70%+ day averages {ag}%. "
                f"Day after a sub-50% day averages {ab}%. "
                f"Good days breed good days by {ag - ab} points.")

    # 5. Red-line events vs daily score
    try:
        rl_days = db._conn.execute(
            "SELECT day, COUNT(*) FROM redlines GROUP BY day"
        ).fetchall()
        if rl_days:
            rl_scores = [scores.get(d, None) for d, _ in rl_days
                         if scores.get(d) is not None]
            no_rl = [s for d, s in scores.items()
                     if d not in {dd for dd, _ in rl_days}]
            if rl_scores and no_rl:
                avg_rl = int(sum(rl_scores)/len(rl_scores))
                avg_clean = int(sum(no_rl)/len(no_rl))
                if avg_clean - avg_rl >= 10:
                    insights.append(
                        f"Red-line impact: days with red-line events "
                        f"average {avg_rl}%. Clean days: {avg_clean}%. "
                        f"Cost: {avg_clean - avg_rl} points per incident.")
    except Exception:
        pass

    # 6. Task completion rate trend
    try:
        recap_files = sorted(glob.glob(os.path.join(config.RECAP_DIR, "*.txt")))
        if len(recap_files) >= 10:
            first_half = recap_files[:len(recap_files)//2]
            second_half = recap_files[len(recap_files)//2:]
            fh_dates = [os.path.basename(f).replace(".txt","") for f in first_half]
            sh_dates = [os.path.basename(f).replace(".txt","") for f in second_half]
            fh_scores = [scores.get(d, 0) for d in fh_dates if d in scores]
            sh_scores = [scores.get(d, 0) for d in sh_dates if d in scores]
            if fh_scores and sh_scores:
                fh_avg = int(sum(fh_scores)/len(fh_scores))
                sh_avg = int(sum(sh_scores)/len(sh_scores))
                direction = "improving" if sh_avg > fh_avg else "declining"
                insights.append(
                    f"Trajectory: first half average {fh_avg}%, "
                    f"recent half {sh_avg}%. You are {direction} "
                    f"by {abs(sh_avg - fh_avg)} points.")
    except Exception:
        pass

    # 7. Hourly focus pattern
    try:
        rows = db._conn.execute(
            "SELECT ts, flagged FROM activity WHERE day >= ? "
            "ORDER BY ts",
            ((date.today() - timedelta(days=14)).isoformat(),)
        ).fetchall()
        if len(rows) >= 200:
            hour_data = defaultdict(lambda: {"total": 0, "clean": 0})
            for ts, flagged in rows:
                h = datetime.fromtimestamp(ts).hour
                hour_data[h]["total"] += 1
                if not flagged:
                    hour_data[h]["clean"] += 1
            focus_by_hour = {}
            for h, d in hour_data.items():
                if d["total"] >= 20:
                    focus_by_hour[h] = int(d["clean"] / d["total"] * 100)
            if len(focus_by_hour) >= 6:
                peak = max(focus_by_hour, key=focus_by_hour.get)
                valley = min(focus_by_hour, key=focus_by_hour.get)
                p12 = peak % 12 or 12
                v12 = valley % 12 or 12
                insights.append(
                    f"Energy curve: peak focus at "
                    f"{p12} {'AM' if peak < 12 else 'PM'} "
                    f"({focus_by_hour[peak]}% clean). Lowest at "
                    f"{v12} {'AM' if valley < 12 else 'PM'} "
                    f"({focus_by_hour[valley]}% clean).")
    except Exception:
        pass

    return insights if insights else ["Not enough data yet — keep going."]
