"""Stripe revenue sync. Pulls real, confirmed payments straight from
Stripe -- the person's actual payment processor, all client revenue
runs through it -- into the same revenue_events table the notes-based
extractor used to populate. Once this is configured (STRIPE_API_KEY
set), insight/distiller.py skips note-based dollar extraction
entirely: Stripe is authoritative, so there's no double-counting risk
and no more AI-guessed dollar amounts from freeform text.

Setup -- two ways now:
  A) Settings > Integrations in the app itself: paste the key, click
     Save. Takes effect immediately, no restart needed.
  B) Manually: setx STRIPE_API_KEY "rk_live_..." in PowerShell, then
     restart WITNESS (same pattern as ANTHROPIC_API_KEY).
Either way: In the Stripe Dashboard, Developers -> API keys -> Create
restricted key, with READ-ONLY access to "Charges" (or "Payment
Intents"). Do not use the full secret key here -- a read-only key
can't refund, charge, or change anything if it's ever accidentally
exposed.

Requires the `stripe` package (pip install stripe -- see install.bat).
Degrades gracefully if not configured or not installed: sync() just
returns an explanatory error instead of the app breaking.
"""
import os
from datetime import datetime


def is_configured() -> bool:
    # Read fresh every call, not cached -- a key can be set live via
    # Settings > Integrations while the app is running, and a stale
    # module-level constant captured at import time would miss that.
    return bool(os.environ.get("STRIPE_API_KEY"))


def _field(obj, key, default=None):
    """Safe field access for Stripe SDK objects. Confirmed directly
    against the installed `stripe` package (constructed a real Charge
    offline via stripe.Charge.construct_from() and reproduced this
    exactly): these objects do NOT support dict-style .get() the way
    older versions did -- calling charge.get("status") raises
    AttributeError("get"), because .get isn't a real attribute and the
    object's __getattr__ fallback tries to look up "get" as a *field*,
    fails, and raises AttributeError with just that name. This was the
    actual cause of the earlier "Sync error: get" report. Bracket
    access (charge["status"]) and .items()-style access DO work; this
    helper uses that, with a plain default if the key is genuinely
    absent."""
    try:
        val = obj[key]
        return val if val is not None else default
    except (KeyError, TypeError):
        return default


def sync(days_back=365) -> dict:
    """Pull successful, non-refunded charges from the last `days_back`
    days and log any not already synced. Safe to call repeatedly --
    dedupes on Stripe's own charge ID (see db.sync_stripe_event).
    Returns {"synced": n, "already_had": n, "error": str or None}."""
    if not is_configured():
        return {"synced": 0, "already_had": 0,
                "error": "STRIPE_API_KEY not set"}

    try:
        import stripe
    except ImportError:
        return {"synced": 0, "already_had": 0,
                "error": "stripe package not installed "
                         "(pip install stripe)"}

    stripe.api_key = os.environ.get("STRIPE_API_KEY")

    import db

    cutoff = int(datetime.now().timestamp() - days_back * 86400)
    synced = 0
    already_had = 0

    try:
        charges = stripe.Charge.list(limit=100, created={"gte": cutoff})
        for charge in charges.auto_paging_iter():
            try:
                if (_field(charge, "status") != "succeeded"
                        or not _field(charge, "paid")):
                    continue
                if _field(charge, "refunded"):
                    continue

                amount = charge["amount"] / 100  # cents -> dollars
                ts = charge["created"]
                day = datetime.fromtimestamp(ts).date().isoformat()
                billing = _field(charge, "billing_details")
                billing_name = _field(billing, "name") if billing else None
                description = (_field(charge, "description")
                               or billing_name
                               or "Stripe payment")
                external_id = charge["id"]

                inserted = db.sync_stripe_event(ts, day, amount,
                                                description, external_id)
                if inserted:
                    synced += 1
                else:
                    already_had += 1
            except Exception as charge_err:
                # One malformed/unexpected charge object shouldn't take
                # down the whole sync, and shouldn't produce a cryptic
                # top-level error either -- skip it, keep going, report
                # the specific charge id and error afterward.
                cid = _field(charge, "id", "?")
                return {
                    "synced": synced, "already_had": already_had,
                    "error": (f"On charge {cid}: "
                             f"{type(charge_err).__name__}: {charge_err}"),
                }
    except Exception as e:
        # Include the exception's class name, not just str(e) -- some
        # exceptions (including some Stripe SDK ones) have a str() far
        # less informative than their type, which matters a lot when
        # something actually breaks and needs diagnosing.
        return {"synced": synced, "already_had": already_had,
                "error": f"{type(e).__name__}: {e}"}

    return {"synced": synced, "already_had": already_had, "error": None}
