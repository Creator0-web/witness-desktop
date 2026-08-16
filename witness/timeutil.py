"""Time formatting utilities. All display uses 12-hour AM/PM."""

def to12(t24: str) -> str:
    """Convert 'HH:MM' 24h to 'h:MM AM/PM'."""
    try:
        h, m = t24.split(":")
        h = int(h)
        suffix = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m} {suffix}"
    except Exception:
        return t24


def now12() -> str:
    from datetime import datetime
    return datetime.now().strftime("%I:%M %p").lstrip("0")


def now24() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M")
