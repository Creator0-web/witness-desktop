"""Decides whether a daily or weekly distillation is due, and runs it.
Meant to be called once at app startup, in a background thread -- it's
cheap and safe to call every time; it's a no-op if nothing is due, and
it can never raise out to the caller (every real step is wrapped).
"""
from datetime import date, timedelta

import store


def run_if_due():
    _maybe_daily()
    _maybe_weekly()
    _maybe_suggestions()


def _maybe_suggestions():
    today = date.today().isoformat()
    if store.load_suggestions(today) is not None:
        return
    try:
        import distiller
        distiller.build_suggestions(today)
    except Exception:
        pass


def _maybe_daily():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if store.load_daily(yesterday) is not None:
        return
    try:
        import distiller
        distiller.build_daily(yesterday)
    except Exception:
        pass


def _maybe_weekly():
    today = date.today()
    if today.weekday() != 0:  # only check Mondays
        return
    last_week_start = (today - timedelta(days=7)).isoformat()
    if store.load_weekly(last_week_start) is not None:
        return
    try:
        import distiller
        distiller.build_weekly(last_week_start)
    except Exception:
        pass
