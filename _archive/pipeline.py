"""Revenue pipeline. Tracks leads from first contact through payment.
Manual input for now — Stripe/GHL API integration is the next step.

Stages: Lead → Contacted → Quote Sent → Booked → Completed → Paid
"""
import json
from datetime import date

import data


def get_pipeline():
    d = data.load()
    if "pipeline" not in d:
        d["pipeline"] = {
            "leads": [],
            "stats": {
                "total_leads": 0,
                "contacted": 0,
                "quoted": 0,
                "booked": 0,
                "completed": 0,
                "paid": 0,
            },
            "weekly": {}
        }
        data.save(d)
    return d["pipeline"]


def update_stats(stage, count):
    """Update a pipeline stage count. stage: leads/contacted/quoted/booked/completed/paid"""
    d = data.load()
    p = get_pipeline()
    p["stats"][stage] = count

    # track weekly
    week = date.today().isocalendar()
    week_key = f"{week[0]}-W{week[1]}"
    if week_key not in p["weekly"]:
        p["weekly"][week_key] = {}
    p["weekly"][week_key][stage] = count

    d["pipeline"] = p
    data.save(d)


def get_conversion_rates():
    p = get_pipeline()
    s = p["stats"]
    rates = {}
    if s["total_leads"] > 0:
        rates["contact_rate"] = round(s["contacted"] / s["total_leads"] * 100)
    if s["contacted"] > 0:
        rates["quote_rate"] = round(s["quoted"] / s["contacted"] * 100)
    if s["quoted"] > 0:
        rates["close_rate"] = round(s["booked"] / s["quoted"] * 100)
    return rates


def summary_for_brain():
    p = get_pipeline()
    s = p["stats"]
    rates = get_conversion_rates()
    line = (f"Pipeline: {s['total_leads']} leads → {s['contacted']} contacted → "
            f"{s['quoted']} quoted → {s['booked']} booked → "
            f"{s['completed']} completed → {s['paid']} paid.")
    if rates:
        rate_str = ", ".join(f"{k}: {v}%" for k, v in rates.items())
        line += f" Rates: {rate_str}."
    return line
