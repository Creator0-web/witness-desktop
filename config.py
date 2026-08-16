"""WITNESS v2 — configuration. Edit freely."""

# ── Timing ───────────────────────────────────────────────────────────────
ROUTINE_CHECKIN_MIN = 45      # routine check-in interval while present
WINDOW_POLL_SEC = 5
CAMERA_POLL_SEC = 3
AWAY_AFTER_SEC = 60

# Escalation ladder for drift (minutes on a distracting tab)
ESCALATE_AT_MIN = [0.5, 2.5, 4.5]   # spoken lines at these marks
CHECKIN_AT_MIN = 6.5                # full check-in window opens here
DEEP_WORK_MINUTES = 90              # deep work session length
DEEP_WORK_SPEEDUP = 0.5             # escalation times multiplied by this in deep work

# ── Voice ────────────────────────────────────────────────────────────────
VOICE_RATE = 175              # words per minute
ESCALATION_INTENSITY = 2      # 1 = gentle, 2 = firm (default), 3 = harsh

# ── Drift detection ──────────────────────────────────────────────────────
DISTRACTING_KEYWORDS = [
    "youtube", "reddit", "twitter", "x.com", "instagram", "tiktok",
    "netflix", "twitch", "9gag", "facebook",
]
RED_LINE_KEYWORDS = [
    "porn", "pornhub", "xvideos", "xnxx", "onlyfans", "hentai",
    "chaturbate", "stripchat", "xhamster", "redtube", "spankbang",
    "brazzers", "bangbros", "youporn", "tube8", "xtube",
    "cam4", "livejasmin", "bongacams", "myfreecams", "camsoda",
    "fapello", "rule34", "e-hentai", "nhentai", "hanime",
    "erome", "bunkr", "freeones", "iafd",
]

# ── AI models ────────────────────────────────────────────────────────────
# Set key once in PowerShell:  setx ANTHROPIC_API_KEY "sk-ant-..."
FAST_MODEL = "claude-haiku-4-5-20251001"   # voice lines, check-ins (many/day)
SMART_MODEL = "claude-sonnet-4-6"          # morning, recap, schedule, chat, SOS

# ── Files ────────────────────────────────────────────────────────────────
DB_PATH = "witness.db"
DATA_PATH = "witness_data.json"
RECAP_DIR = "recaps"
SOS_VIDEO_DIR = "sos_videos"

# ── Accountability Export (optional) ─────────────────────────────────────
# Set these to auto-email your daily/weekly reports to someone.
# Use a Gmail App Password (not your regular password):
# https://support.google.com/accounts/answer/185833
EXPORT_ENABLED = False
EXPORT_EMAIL_TO = ""       # coach@example.com
EXPORT_EMAIL_FROM = ""     # you@gmail.com
EXPORT_EMAIL_PASSWORD = "" # Gmail App Password
