"""Statistical engine. Pure math — no LLM, no hallucination.
Runs real correlation analysis, regression models, and conversion
rate calculations on accumulated data.

The AI layer reads THIS engine's output and communicates it.
This is the ground truth the system trusts over human opinion.
"""
import os
import json
import sqlite3
from datetime import date, datetime, timedelta
from collections import defaultdict

import config
import db


class StatsEngine:
    """Builds and maintains a statistical model of the user's
    productivity, business, and behavior patterns."""

    def __init__(self):
        self.model_file = "stats_model.json"
        self.model = self._load_model()

    def _load_model(self):
        try:
            with open(self.model_file, "r") as f:
                return json.load(f)
        except Exception:
            return {
                "activity_outcomes": [],   # {date, activities, outcomes}
                "conversion_rates": {},    # stage -> rate
                "hourly_focus": {},        # hour -> clean_pct
                "day_of_week": {},         # day -> avg_score
                "correlations": [],        # proven correlations
                "task_effectiveness": {},  # task_keyword -> avg_outcome
                "energy_predictors": {},   # factor -> impact_score
                "last_updated": "",
            }

    def _save_model(self):
        self.model["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.model_file, "w") as f:
                json.dump(self.model, f, indent=1)
        except Exception:
            pass

    def full_analysis(self):
        """Run complete statistical analysis on all available data.
        Returns dict of findings with confidence levels."""
        findings = {}

        findings["hourly_focus"] = self._hourly_focus_analysis()
        findings["day_of_week"] = self._day_of_week_analysis()
        findings["conversion_funnel"] = self._funnel_analysis()
        findings["task_value"] = self._task_value_analysis()
        findings["behavior_correlations"] = self._behavior_correlations()
        findings["predictors"] = self._predictor_analysis()
        findings["efficiency"] = self._efficiency_score()

        self.model["correlations"] = [
            f for f in self._flatten_findings(findings)
            if f.get("confidence", 0) >= 0.6
        ]
        self._save_model()

        return findings

    def _hourly_focus_analysis(self):
        """Which hours produce the cleanest focus?"""
        try:
            rows = db._conn.execute(
                "SELECT ts, flagged FROM activity WHERE ts > ?",
                (self._cutoff(30),)).fetchall()
            if len(rows) < 200:
                return {"status": "insufficient_data", "needed": 200,
                        "have": len(rows)}

            hours = defaultdict(lambda: {"total": 0, "clean": 0})
            for ts, flagged in rows:
                h = datetime.fromtimestamp(ts).hour
                hours[h]["total"] += 1
                if not flagged:
                    hours[h]["clean"] += 1

            result = {}
            for h, d in hours.items():
                if d["total"] >= 20:
                    pct = round(d["clean"] / d["total"] * 100, 1)
                    result[h] = pct

            if result:
                peak = max(result, key=result.get)
                valley = min(result, key=result.get)
                return {
                    "status": "ok",
                    "by_hour": result,
                    "peak_hour": peak,
                    "peak_pct": result[peak],
                    "valley_hour": valley,
                    "valley_pct": result[valley],
                    "spread": round(result[peak] - result[valley], 1),
                    "confidence": min(1.0, len(rows) / 1000),
                }
            return {"status": "insufficient_data"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _day_of_week_analysis(self):
        """Which days of the week are strongest?"""
        try:
            scores = db.recent_scores(60)
            if len(scores) < 14:
                return {"status": "insufficient_data"}

            dow = defaultdict(list)
            for d, s in scores:
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    dow[dt.strftime("%A")].append(s)
                except Exception:
                    pass

            result = {}
            for day, ss in dow.items():
                if len(ss) >= 2:
                    avg = round(sum(ss) / len(ss), 1)
                    result[day] = {"avg": avg, "samples": len(ss)}

            if result:
                best = max(result, key=lambda k: result[k]["avg"])
                worst = min(result, key=lambda k: result[k]["avg"])
                return {
                    "status": "ok",
                    "by_day": result,
                    "best": best,
                    "best_avg": result[best]["avg"],
                    "worst": worst,
                    "worst_avg": result[worst]["avg"],
                    "confidence": min(1.0, len(scores) / 30),
                }
            return {"status": "insufficient_data"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _funnel_analysis(self):
        """Analyze the business conversion funnel from pipeline data."""
        try:
            import data
            d = data.load()
            if "pipeline" not in d:
                return {"status": "no_pipeline"}

            stats = d["pipeline"]["stats"]
            funnel = {}

            stages = [
                ("total_leads", "contacted", "contact_rate"),
                ("contacted", "quoted", "quote_rate"),
                ("quoted", "booked", "close_rate"),
                ("booked", "completed", "completion_rate"),
                ("completed", "paid", "payment_rate"),
            ]

            for from_stage, to_stage, name in stages:
                from_val = stats.get(from_stage, 0)
                to_val = stats.get(to_stage, 0)
                if from_val > 0:
                    rate = round(to_val / from_val * 100, 1)
                    funnel[name] = {
                        "rate": rate,
                        "from": from_val,
                        "to": to_val,
                    }

            # bottleneck = lowest conversion rate
            if funnel:
                bottleneck = min(funnel, key=lambda k: funnel[k]["rate"])
                return {
                    "status": "ok",
                    "rates": funnel,
                    "bottleneck": bottleneck,
                    "bottleneck_rate": funnel[bottleneck]["rate"],
                    "confidence": 0.7 if stats.get("total_leads", 0) >= 20 else 0.4,
                }
            return {"status": "insufficient_data"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _task_value_analysis(self):
        """Which types of tasks actually correlate with revenue/good days?"""
        try:
            # get task descriptions from check-ins
            rows = db._conn.execute(
                "SELECT day, answer FROM checkins WHERE kind='routine' "
                "AND answer != '(no answer)'"
            ).fetchall()

            scores = dict(db.recent_scores(60))
            if len(rows) < 20:
                return {"status": "insufficient_data"}

            # keyword extraction — simple but effective
            keywords = ["call", "outreach", "lead", "quote", "follow",
                        "email", "clean", "book", "price", "thumbtack",
                        "vonage", "invoice", "system", "organize",
                        "learn", "research", "social", "reddit",
                        "youtube", "break"]

            keyword_scores = defaultdict(list)
            for day, answer in rows:
                if day not in scores:
                    continue
                answer_lower = answer.lower()
                for kw in keywords:
                    if kw in answer_lower:
                        keyword_scores[kw].append(scores[day])

            result = {}
            for kw, ss in keyword_scores.items():
                if len(ss) >= 3:
                    avg = round(sum(ss) / len(ss), 1)
                    result[kw] = {"avg_score": avg, "samples": len(ss)}

            if result:
                best = max(result, key=lambda k: result[k]["avg_score"])
                worst = min(result, key=lambda k: result[k]["avg_score"])
                return {
                    "status": "ok",
                    "by_keyword": result,
                    "highest_value": best,
                    "lowest_value": worst,
                    "confidence": min(1.0, len(rows) / 50),
                }
            return {"status": "insufficient_data"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _behavior_correlations(self):
        """Find correlations between behaviors and outcomes."""
        try:
            import lifedata
            life = lifedata.get_recent(30)
            scores = dict(db.recent_scores(30))

            correlations = []

            # exercise vs score
            ex_days = {"yes": [], "no": []}
            for day, info in life.items():
                if day in scores:
                    has_ex = bool(info.get("exercise"))
                    ex_days["yes" if has_ex else "no"].append(scores[day])

            if len(ex_days["yes"]) >= 3 and len(ex_days["no"]) >= 3:
                avg_yes = round(sum(ex_days["yes"]) / len(ex_days["yes"]), 1)
                avg_no = round(sum(ex_days["no"]) / len(ex_days["no"]), 1)
                impact = round(avg_yes - avg_no, 1)
                correlations.append({
                    "factor": "exercise",
                    "with": avg_yes,
                    "without": avg_no,
                    "impact": impact,
                    "confidence": min(1.0, (len(ex_days["yes"]) +
                                           len(ex_days["no"])) / 20),
                    "direction": "positive" if impact > 0 else "negative",
                })

            # sleep vs score
            sleep_data = {"good": [], "bad": []}
            for day, info in life.items():
                if day in scores and "sleep_hours" in info:
                    h = info["sleep_hours"]
                    if isinstance(h, (int, float)):
                        key = "good" if h >= 7 else "bad"
                        sleep_data[key].append(scores[day])

            if len(sleep_data["good"]) >= 3 and len(sleep_data["bad"]) >= 3:
                avg_g = round(sum(sleep_data["good"]) / len(sleep_data["good"]), 1)
                avg_b = round(sum(sleep_data["bad"]) / len(sleep_data["bad"]), 1)
                correlations.append({
                    "factor": "sleep_7plus",
                    "with": avg_g,
                    "without": avg_b,
                    "impact": round(avg_g - avg_b, 1),
                    "confidence": min(1.0, (len(sleep_data["good"]) +
                                           len(sleep_data["bad"])) / 15),
                })

            # morning start time vs score
            try:
                morning_rows = db._conn.execute(
                    "SELECT day, MIN(ts) FROM presence WHERE event='arrived' "
                    "GROUP BY day").fetchall()
                early, late = [], []
                for day, ts in morning_rows:
                    if day in scores:
                        hour = datetime.fromtimestamp(ts).hour
                        if hour < 9:
                            early.append(scores[day])
                        elif hour >= 10:
                            late.append(scores[day])

                if len(early) >= 3 and len(late) >= 3:
                    avg_e = round(sum(early) / len(early), 1)
                    avg_l = round(sum(late) / len(late), 1)
                    correlations.append({
                        "factor": "start_before_9am",
                        "with": avg_e,
                        "without": avg_l,
                        "impact": round(avg_e - avg_l, 1),
                        "confidence": min(1.0, (len(early) + len(late)) / 15),
                    })
            except Exception:
                pass

            return {
                "status": "ok" if correlations else "insufficient_data",
                "correlations": sorted(correlations,
                                       key=lambda x: abs(x["impact"]),
                                       reverse=True),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _predictor_analysis(self):
        """Rank all factors by their predictive power for good days."""
        findings = {
            "hourly": self._hourly_focus_analysis(),
            "daily": self._day_of_week_analysis(),
            "behavior": self._behavior_correlations(),
            "tasks": self._task_value_analysis(),
        }

        predictors = []
        bc = findings["behavior"]
        if bc.get("status") == "ok":
            for c in bc["correlations"]:
                predictors.append({
                    "factor": c["factor"],
                    "impact": c["impact"],
                    "confidence": c["confidence"],
                    "actionable": True,
                })

        if findings["hourly"].get("status") == "ok":
            spread = findings["hourly"]["spread"]
            predictors.append({
                "factor": f"work_during_peak_hour_{findings['hourly']['peak_hour']}",
                "impact": spread,
                "confidence": findings["hourly"]["confidence"],
                "actionable": True,
            })

        return {
            "status": "ok" if predictors else "insufficient_data",
            "ranked": sorted(predictors, key=lambda x: abs(x["impact"]),
                             reverse=True),
        }

    def _efficiency_score(self):
        """What percentage of tracked time produces measurable results?"""
        try:
            import data
            d = data.load()
            scores = db.recent_scores(30)
            if len(scores) < 7:
                return {"status": "insufficient_data"}

            avg_score = sum(s for _, s in scores) / len(scores)
            revenue = d["money"]["current_monthly"]
            target = d["money"]["target_monthly"]

            # hours tracked
            total_samples = db._conn.execute(
                "SELECT COUNT(*) FROM activity WHERE ts > ?",
                (self._cutoff(30),)).fetchone()[0]
            hours_tracked = round(total_samples * config.WINDOW_POLL_SEC / 3600)

            clean_samples = db._conn.execute(
                "SELECT COUNT(*) FROM activity WHERE ts > ? AND flagged=0",
                (self._cutoff(30),)).fetchone()[0]
            clean_hours = round(clean_samples * config.WINDOW_POLL_SEC / 3600)

            efficiency = round(clean_hours / max(1, hours_tracked) * 100, 1)

            rev_per_hour = round(revenue / max(1, clean_hours), 2) \
                if revenue > 0 else None

            return {
                "status": "ok",
                "hours_tracked_30d": hours_tracked,
                "clean_hours_30d": clean_hours,
                "efficiency_pct": efficiency,
                "avg_score": round(avg_score, 1),
                "rev_per_clean_hour": rev_per_hour,
                "target_gap_pct": round((1 - revenue / max(1, target)) * 100, 1)
                if target > 0 else None,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_task_xp_value(self, task_description):
        """Calculate XP value for a task based on historical data.
        Returns int XP value and reasoning string."""
        task_lower = task_description.lower()

        # high-value keywords (based on what correlates with revenue)
        high_value = {"call": 80, "quote": 100, "follow up": 90,
                      "book": 120, "lead": 70, "outreach": 80,
                      "close": 150, "invoice": 60, "price": 70,
                      "sell": 100, "client": 80, "customer": 80}
        medium_value = {"email": 30, "clean": 40, "system": 25,
                        "organize": 15, "plan": 20, "schedule": 20}
        low_value = {"learn": 10, "read": 10, "research": 10,
                     "browse": 5, "organize inbox": 5}

        xp = 15  # base
        reason = "standard task"

        for kw, val in high_value.items():
            if kw in task_lower:
                xp = val
                reason = f"revenue-generating ({kw})"
                break

        if xp == 15:
            for kw, val in medium_value.items():
                if kw in task_lower:
                    xp = val
                    reason = f"operational ({kw})"
                    break

        if xp == 15:
            for kw, val in low_value.items():
                if kw in task_lower:
                    xp = val
                    reason = f"low direct impact ({kw})"
                    break

        # adjust based on learned task effectiveness if available
        tv = self.model.get("task_effectiveness", {})
        for kw, info in tv.items():
            if kw in task_lower and isinstance(info, dict):
                score_impact = info.get("avg_score", 50) - 50
                xp = max(5, int(xp + score_impact * 0.5))

        return xp, reason

    def generate_optimal_tasks(self):
        """Generate today's task list purely from data analysis.
        Returns list of {text, xp, reasoning} sorted by expected value."""
        findings = self.full_analysis()
        tasks = []

        # funnel bottleneck tasks
        funnel = findings.get("conversion_funnel", {})
        if funnel.get("status") == "ok":
            bn = funnel["bottleneck"]
            rate = funnel["bottleneck_rate"]
            if bn == "contact_rate":
                tasks.append({
                    "text": "Contact 5 new leads (your bottleneck is first contact)",
                    "xp": 100,
                    "reasoning": f"Contact rate is {rate}% — lowest in funnel",
                    "by": "10:00"
                })
            elif bn == "quote_rate":
                tasks.append({
                    "text": "Send quotes to all contacted leads without one",
                    "xp": 120,
                    "reasoning": f"Quote rate is {rate}% — biggest drop-off",
                    "by": "11:00"
                })
            elif bn == "close_rate":
                tasks.append({
                    "text": "Follow up every open quote with a call",
                    "xp": 130,
                    "reasoning": f"Close rate is {rate}% — follow-ups move this",
                    "by": "12:00"
                })

        # high-value keyword tasks
        tv = findings.get("task_value", {})
        if tv.get("status") == "ok":
            best = tv["highest_value"]
            tasks.append({
                "text": f"Focus on {best}-related work (your highest-value activity)",
                "xp": 80,
                "reasoning": f"Days with '{best}' average {tv['by_keyword'][best]['avg_score']}%",
                "by": "14:00"
            })

        # behavior-based tasks
        bc = findings.get("behavior_correlations", {})
        if bc.get("status") == "ok":
            for corr in bc["correlations"][:2]:
                if corr["factor"] == "exercise" and corr["impact"] > 5:
                    tasks.append({
                        "text": "Exercise (proven +{:.0f} points to your day)".format(
                            corr["impact"]),
                        "xp": 60,
                        "reasoning": f"Exercise days: {corr['with']}% vs {corr['without']}%",
                        "by": "08:00"
                    })

        # schedule optimization tasks
        hourly = findings.get("hourly_focus", {})
        if hourly.get("status") == "ok":
            peak = hourly["peak_hour"]
            tasks.append({
                "text": f"Do your hardest revenue task at {peak}:00 (your peak hour)",
                "xp": 90,
                "reasoning": f"Focus at hour {peak}: {hourly['peak_pct']}% clean",
                "by": f"{peak:02d}:00"
            })

        # always include a revenue-generating task
        if not any("call" in t["text"].lower() or "quote" in t["text"].lower()
                   for t in tasks):
            tasks.append({
                "text": "Make 5 calls or send 3 quotes (direct revenue activity)",
                "xp": 100,
                "reasoning": "Every day needs at least one direct revenue action",
                "by": "11:00"
            })

        # daily recap
        tasks.append({
            "text": "End-of-day recap + log revenue + plan tomorrow",
            "xp": 30,
            "reasoning": "Data capture accelerates learning",
            "by": "20:00"
        })

        # sort by time
        tasks.sort(key=lambda t: t.get("by", "23:59"))

        return tasks

    def summary_for_brain(self):
        """Compact summary of statistical findings for the AI brain."""
        findings = self.full_analysis()
        lines = ["STATISTICAL MODEL (pure math, not AI opinion):"]

        h = findings.get("hourly_focus", {})
        if h.get("status") == "ok":
            lines.append(f"  Peak focus: {h['peak_hour']}:00 ({h['peak_pct']}%). "
                         f"Valley: {h['valley_hour']}:00 ({h['valley_pct']}%).")

        d = findings.get("day_of_week", {})
        if d.get("status") == "ok":
            lines.append(f"  Best day: {d['best']} ({d['best_avg']}%). "
                         f"Worst: {d['worst']} ({d['worst_avg']}%).")

        bc = findings.get("behavior_correlations", {})
        if bc.get("status") == "ok":
            for c in bc["correlations"][:3]:
                lines.append(f"  {c['factor']}: +{c['impact']} points "
                             f"(confidence: {c['confidence']:.0%})")

        f = findings.get("conversion_funnel", {})
        if f.get("status") == "ok":
            lines.append(f"  Funnel bottleneck: {f['bottleneck']} "
                         f"at {f['bottleneck_rate']}%")

        e = findings.get("efficiency", {})
        if e.get("status") == "ok":
            lines.append(f"  Efficiency: {e['efficiency_pct']}% of tracked "
                         f"time is clean. {e['clean_hours_30d']} clean hrs/30d.")
            if e.get("rev_per_clean_hour"):
                lines.append(f"  Revenue/clean hour: ${e['rev_per_clean_hour']}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _cutoff(self, days):
        """Timestamp N days ago."""
        return (datetime.now() - timedelta(days=days)).timestamp()

    def _flatten_findings(self, findings):
        """Extract individual findings for storage."""
        flat = []
        for section, data in findings.items():
            if isinstance(data, dict) and data.get("status") == "ok":
                flat.append({"section": section, **data})
        return flat


# singleton
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = StatsEngine()
    return _engine
