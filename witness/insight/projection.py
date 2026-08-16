"""Goal-pace projection. Pure Python only, no AI -- this takes the
existing daily efficiency signal (daily_scores, already computed by
shared/score.py from task completion weighted by drift/redline
behavior) and describes the trend and, where a real deadline exists,
the runway against it.

Deliberately does NOT fabricate a "you'll hit your goal on this exact
date" prediction from behavioral consistency alone -- that would be
false precision. What it does do: show the trend honestly, and if the
primary goal (data.load()["goals"][0]) has a target_date set, frame
how much runway is left against that real deadline and whether the
trend is moving the right direction.
"""
from datetime import date, datetime, timedelta

import data
import db


def efficiency_trend(days=30):
    """Reads db.recent_scores() -- the same daily efficiency number
    already shown as 'focus_score' in the colored documents. Returns
    None if there's no history yet."""
    rows = db.recent_scores(days)
    if not rows:
        return None
    ordered = sorted(rows)
    scores = [s for _, s in ordered]

    avg_all = round(sum(scores) / len(scores), 1)
    recent = scores[-7:]
    avg7 = round(sum(recent) / len(recent), 1)

    prior = scores[-14:-7] if len(scores) >= 14 else None
    avg_prior7 = round(sum(prior) / len(prior), 1) if prior else None

    if avg_prior7 is not None:
        if avg7 > avg_prior7 + 3:
            trend = "improving"
        elif avg7 < avg_prior7 - 3:
            trend = "declining"
        else:
            trend = "flat"
    else:
        trend = "not enough history yet"

    return {
        "days_of_history": len(scores),
        "avg_all_time": avg_all,
        "avg_last_7": avg7,
        "avg_prior_7": avg_prior7,
        "trend": trend,
    }


def goal_projection():
    """Honest framing of pace toward the stated goal. Never invents a
    completion date -- only uses a real target_date if the person set
    one on their primary goal (data.load()['goals'][0])."""
    d = data.load()
    mission = d.get("mission", "")
    goals = d.get("goals", [])
    primary = goals[0] if goals else None
    trend = efficiency_trend()

    result = {
        "goal": mission,
        "primary_goal_title": primary.get("title") if primary else None,
        "target_date": primary.get("target_date") if primary else None,
        "trend": trend,
    }

    if trend is None:
        result["note"] = ("No efficiency history yet -- this fills in "
                           "automatically as daily_scores accumulate "
                           "(usually within a few days of normal use).")
        return result

    target_date = result["target_date"]
    if not target_date:
        result["note"] = (
            f"Trend: {trend['trend']}, averaging {trend['avg_last_7']}% "
            f"over the last 7 days (all-time avg {trend['avg_all_time']}%). "
            "No target_date is set on the primary goal, so there's no "
            "deadline to project against -- add one via the Goals panel "
            "for a runway estimate.")
        return result

    try:
        td = datetime.strptime(target_date, "%Y-%m-%d").date()
        days_left = (td - date.today()).days
    except Exception:
        days_left = None

    if days_left is None:
        result["note"] = f"target_date '{target_date}' isn't in YYYY-MM-DD format."
    elif days_left < 0:
        result["note"] = (f"Target date {target_date} has passed "
                           f"({-days_left} days ago). Trend was "
                           f"{trend['trend']} at {trend['avg_last_7']}% "
                           "over the last 7 days.")
    else:
        result["days_left"] = days_left
        result["note"] = (
            f"{days_left} days left until {target_date}. Last 7 days "
            f"averaging {trend['avg_last_7']}% efficiency, trend is "
            f"{trend['trend']} (all-time avg {trend['avg_all_time']}%). "
            "This describes pace, not a guarantee -- efficiency measures "
            "task completion and drift behavior, not the business outcome "
            "itself.")

    return result


# ── Revenue-based goal completion projection ─────────────────────────────
#
# Two-speed design, per the person's explicit request: accuracy alone
# is "robotic and hard to connect to" -- but telling people only what
# they want to hear isn't honest either. So: two independently computed
# lanes, shown side by side, plus their average.
#
#   HARSH  -- realistic, slow to trust. Requires a full 30-day window
#             compared against the 30-60-days-ago window before it will
#             compute anything -- won't move at all until ~2 months of
#             spread-out sales exist. Full trust at 10 logged sales.
#   LIGHT  -- responsive, warms up fast. Splits WHATEVER history exists
#             (even just 2 sales) into an earlier half and a later half
#             and compares those -- can produce a real number within
#             days. Full trust at just 3 logged sales. This is
#             deliberately more optimistic-leaning and can be noisy
#             with very few sales -- that's an accepted, intentional
#             tradeoff, not an oversight.
#   BLENDED -- the average of the two, in days-out terms. Shown as the
#             headline number; harsh and light stay one click away in
#             the Goal Progress panel for anyone who wants the full
#             picture.
#
# Both lanes still blend toward the same 5-year cold-start placeholder
# when they don't have enough evidence yet -- neither one ever invents
# a real-looking date from nothing.

COLD_START_YEARS = 5
HARSH_FULL_TRUST_EVENT_COUNT = 10
LIGHT_WINDOW_DAYS = 10  # only fit Light's trend through the most
                        # recent N days -- see light_completion_projection()


def revenue_rate(days=30, end_days_ago=0):
    """Monthly-equivalent rate from revenue events in a trailing
    window, that window ending `end_days_ago` days before today.
    Returns None if there are no events in that window."""
    rows = db.revenue_events_all()
    if not rows:
        return None
    end = time_module_now() - end_days_ago * 86400
    start = end - days * 86400
    total = sum(amount for ts, _, amount, _ in rows if start <= ts <= end)
    if total <= 0:
        return None
    return round(total / (days / 30.44), 2)


def time_module_now():
    import time
    return time.time()


def _base_result(target, evidence):
    today = date.today()
    cold_start_date = today + timedelta(days=COLD_START_YEARS * 365)
    return today, cold_start_date


def _no_target_result(evidence):
    return {
        "target": 0, "evidence_count": evidence, "completion_date": None,
        "note": "No target_monthly set -- click the goal line at the "
                "top to set one.",
    }


def _already_met_result(target, current_rate, evidence, today):
    return {
        "target": target, "current_rate": current_rate,
        "evidence_count": evidence, "completion_date": today.isoformat(),
        "note": "Current rate already meets or exceeds the target.",
    }


def _current_pace(sequence=None):
    """The ONE definition of 'current rate' used for display and for
    the already-met check in both lanes -- matches exactly what the
    graph's most recent point shows (daily_average_sequence()'s last
    value: total $ received since the first-ever payment, divided by
    days actually elapsed, not a fixed 30-day window).

    Fixes a real inconsistency found directly from the person's own
    screenshot: current_rate used to be revenue_rate(30, 0) -- a FIXED
    30-day-equivalent divisor, applied even when real history is much
    shorter than 30 days. With ~10 days of real history, that made
    current_rate come out roughly 3x LOWER than what the graph's own
    last data point showed (confirmed with the person's exact numbers:
    revenue_rate gave ~$2,019/mo while the graph's last point showed
    ~$6,055/mo, for the same $1,989 total received) -- so the graph
    could visually sit above the target line while the lane logic
    still said the goal hadn't been reached. Now both use the same
    number, computed the same way."""
    seq = sequence if sequence is not None else daily_average_sequence()
    return seq[-1][1] if seq else 0


def harsh_completion_projection():
    """Realistic lane -- see module docstring above. Always returns a
    date, never refuses to answer, but stays anchored near the
    cold-start placeholder until real month-over-month evidence exists."""
    d = data.load()
    target = d.get("money", {}).get("target_monthly", 0)
    all_events = db.revenue_events_all()
    evidence = len(all_events)
    today, cold_start_date = _base_result(target, evidence)

    if target <= 0:
        return _no_target_result(evidence)

    current_rate = _current_pace()
    if current_rate >= target:
        return _already_met_result(target, current_rate, evidence, today)

    # growth = how much the monthly rate itself grew over the last
    # month (rate now vs. rate a month ago) -- "sell xyz more this
    # month, you're at xyz/mo in N months," on a full monthly cadence.
    # This is deliberately a DIFFERENT metric from current_rate above:
    # a fixed 30-day trailing window is the right tool specifically
    # for a fair apples-to-apples comparison between two time periods
    # (this month's window vs. last month's window), even though it's
    # the wrong tool for "what's my rate right now" display purposes.
    rate_now = revenue_rate(days=30, end_days_ago=0)
    rate_prior = revenue_rate(days=30, end_days_ago=30)

    computed_days = None
    if rate_now is not None and rate_prior is not None:
        growth_per_month = rate_now - rate_prior
        if growth_per_month > 0:
            months_needed = (target - rate_now) / growth_per_month
            computed_days = max(0, months_needed * 30.44)

    if computed_days is None:
        projected_date = cold_start_date
        confidence = "none yet"
    else:
        weight = min(evidence / HARSH_FULL_TRUST_EVENT_COUNT, 1.0)
        blended_days = (COLD_START_YEARS * 365) * (1 - weight) + computed_days * weight
        projected_date = today + timedelta(days=blended_days)
        confidence = ("low" if weight < 0.4 else
                       "medium" if weight < 0.8 else "high")

    return {
        "target": target, "current_rate": current_rate,
        "evidence_count": evidence, "confidence": confidence,
        "completion_date": projected_date.isoformat(),
        "note": format_countdown(today, projected_date),
    }


def daily_raw_amounts():
    """[(day_index, raw $ actually received that day), ...] -- a
    companion to daily_average_sequence(), for display/debug clarity
    only. daily_average_sequence()'s values are monthly-EQUIVALENT
    figures (today's pace projected out to a full month) -- which is
    correct for comparing against a monthly target, but easy to
    mistake for an actual payment amount when looking at it alone
    (confirmed directly: a $873 real payment on day 0 shows as
    $26,574 in the monthly-equivalent sequence, since $873/day * 30.44
    days = $26,574/mo if that pace continued). This function returns
    the real, un-annualized dollar amount instead, so a debug/display
    view can show both side by side and make which-is-which obvious."""
    all_events = db.revenue_events_all()
    if not all_events:
        return []
    first_day = datetime.fromtimestamp(all_events[0][0]).date()
    today = date.today()
    total_days = max((today - first_day).days + 1, 1)
    daily_totals = {}
    for ts, _, amount, _ in all_events:
        d = (datetime.fromtimestamp(ts).date() - first_day).days
        daily_totals[d] = daily_totals.get(d, 0) + amount
    return [(d, daily_totals.get(d, 0)) for d in range(total_days)]


def daily_average_sequence():
    """[(day_index, monthly_equivalent_rate), ...] -- one point per
    calendar day since the first-ever revenue event through today.
    Each point is the CUMULATIVE average $/day up to that day
    (including zero-revenue days, which pull it down), converted to a
    monthly-equivalent figure. This is what the light lane fits a
    trend through, and what the goal-projection graph plots as
    history. Exposed as its own function so main.py's graph can reuse
    the exact same data the projection is based on."""
    all_events = db.revenue_events_all()  # (ts, day, amount, note), ordered
    if not all_events:
        return []

    first_day = datetime.fromtimestamp(all_events[0][0]).date()
    today = date.today()
    total_days = max((today - first_day).days + 1, 1)

    daily_totals = {}
    for ts, _, amount, _ in all_events:
        d = (datetime.fromtimestamp(ts).date() - first_day).days
        daily_totals[d] = daily_totals.get(d, 0) + amount

    sequence = []
    running = 0.0
    for d in range(total_days):
        running += daily_totals.get(d, 0)
        avg_daily = running / (d + 1)
        sequence.append((d, avg_daily * 30.44))
    return sequence


def _linear_fit(points):
    """Simple least-squares fit. points: [(x, y), ...]. Returns
    (slope, intercept) or None if there's no meaningful spread in x."""
    n = len(points)
    if n < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return None
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def light_completion_projection():
    """Responsive lane. Fits a straight-line trend through the
    cumulative daily-average sequence (daily_average_sequence()) --
    including every zero-revenue day since the first payment, which
    is what naturally pulls the trend back down when growth stalls --
    and extends that line forward to where it crosses the target.
    Updates every single day, even with no new payment, because the
    average itself moves. Unlike Harsh, there's no artificial "wait
    for more evidence" dampening once 2+ days of history exist -- the
    smoothing comes from the cumulative-average construction itself,
    not from blending toward a fake placeholder. Deliberately more
    reactive than Harsh -- see the module docstring."""
    d = data.load()
    target = d.get("money", {}).get("target_monthly", 0)
    all_events = db.revenue_events_all()
    evidence = len(all_events)
    today, cold_start_date = _base_result(target, evidence)

    if target <= 0:
        return _no_target_result(evidence)

    sequence = daily_average_sequence()
    current_rate = _current_pace(sequence)
    if current_rate >= target:
        return _already_met_result(target, current_rate, evidence, today)

    # Only fit the trend through the most recent LIGHT_WINDOW_DAYS of
    # the sequence, not the entire all-time history. Found this by
    # working through a real account's data: a decent early payment
    # followed by a long quiet stretch produces a long decay phase in
    # the cumulative-average sequence (the earlier payment gets more
    # diluted every day with no new revenue) -- fitting ALL of that
    # history in one straight line lets the long decay dominate the
    # slope even when the last week or two shows a genuine, real
    # uptick. Tested several window sizes against that exact shape
    # plus a clean-growth case and a genuinely-flat case: 10 days was
    # the shortest window that still correctly caught real growth in
    # both growth scenarios while staying at zero slope (no false
    # positive) for flat data.
    recent = sequence[-LIGHT_WINDOW_DAYS:] if len(sequence) > LIGHT_WINDOW_DAYS else sequence

    # Within that window, still exclude its first point when there's
    # enough left to spare it -- same single-undiluted-payment-at-the-
    # edge leverage problem (see below) can recur locally even inside
    # a short window if a big payment happens to fall right at its start.
    fit_points = recent[1:] if len(recent) > 2 else recent
    fit = _linear_fit(fit_points)

    computed_days = None
    if fit is not None:
        slope, intercept = fit
        if slope > 0:
            x_cross = (target - intercept) / slope
            last_x = sequence[-1][0]  # extrapolate from the true latest day
            days_from_now = x_cross - last_x
            computed_days = max(0, days_from_now)

    if computed_days is None:
        projected_date = cold_start_date
        confidence = "none yet"
    else:
        projected_date = today + timedelta(days=computed_days)
        confidence = "trend-based"

    return {
        "target": target, "current_rate": current_rate,
        "evidence_count": evidence, "confidence": confidence,
        "completion_date": projected_date.isoformat(),
        "note": format_countdown(today, projected_date),
    }


def blended_completion_projection():
    """Average of the harsh and light lanes, in days-out terms. This
    is the headline number -- motivating but anchored, never as slow
    as harsh alone or as swingy as light alone."""
    h = harsh_completion_projection()
    l = light_completion_projection()
    today = date.today()

    if h.get("completion_date") is None or l.get("completion_date") is None:
        # no target set -- same message either lane would give
        return h

    h_date = datetime.strptime(h["completion_date"], "%Y-%m-%d").date()
    l_date = datetime.strptime(l["completion_date"], "%Y-%m-%d").date()
    avg_days = ((h_date - today).days + (l_date - today).days) / 2
    blended_date = today + timedelta(days=max(0, avg_days))

    return {
        "target": h["target"],
        "current_rate": h.get("current_rate", 0),
        "evidence_count": h["evidence_count"],
        "harsh_date": h["completion_date"],
        "light_date": l["completion_date"],
        "completion_date": blended_date.isoformat(),
        "note": format_countdown(today, blended_date),
    }


def revenue_completion_projection():
    """Backward-compatible alias -- the harsh lane, which is what this
    function used to compute before the three-lane split."""
    return harsh_completion_projection()

    return {
        "target": target,
        "current_rate": current_rate,
        "evidence_count": evidence,
        "confidence": confidence,
        "completion_date": projected_date.isoformat(),
        "note": format_countdown(today, projected_date),
    }


def format_countdown(today: date, completion: date) -> str:
    """'2026-08-04 -- 1.6 years -- 2028-01-30' style string, per the
    person's requested format -- readable at a glance in months or
    years depending on how far out it is."""
    days = (completion - today).days
    months = days / 30.44
    if months < 1:
        span = f"{days} days"
    elif months < 12:
        span = f"{months:.1f} months"
    else:
        span = f"{months / 12:.1f} years"
    return f"{today.isoformat()} -- {span} -- {completion.isoformat()}"


def light_debug_info() -> dict:
    """Exposes exactly what light_completion_projection() is seeing --
    not used by the projection itself, purely so a real result that
    looks wrong can be diagnosed from actual numbers instead of
    guessing. Shown via main.py's 'Debug Light Calc' button."""
    sequence = daily_average_sequence()
    if not sequence:
        return {"sequence_len": 0, "note": "No revenue_events at all."}

    recent = (sequence[-LIGHT_WINDOW_DAYS:]
              if len(sequence) > LIGHT_WINDOW_DAYS else sequence)
    fit_points = recent[1:] if len(recent) > 2 else recent
    fit = _linear_fit(fit_points)
    raw = dict(daily_raw_amounts())

    return {
        "sequence_len": len(sequence),
        "window_days_used": len(recent),
        "fit_points_count": len(fit_points),
        "fit_points": [(d, round(v, 2)) for d, v in fit_points],
        "slope": round(fit[0], 4) if fit else None,
        "intercept": round(fit[1], 2) if fit else None,
        "slope_positive": (fit[0] > 0) if fit else None,
        "sequence_tail": [(d, round(v, 2)) for d, v in sequence[-15:]],
        "raw_amounts_tail": [(d, round(raw.get(d, 0), 2))
                             for d, _ in sequence[-15:]],
    }
