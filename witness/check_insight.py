"""Standalone check: builds and prints TODAY's colored document right
now, using whatever activity is already logged today -- no need to
wait for tomorrow's automatic startup trigger.

Run from the project root (same folder as main.py):
    python check_insight.py

Safe to run any time, as many times as you want. It only reads
witness.db and writes into insight_data/ -- it never touches core/,
never touches your live session, and re-running it just overwrites
today's colored document with a fresher one.
"""
import sys
import os

_base = os.path.dirname(os.path.abspath(__file__))
for _sub in ("core", "character", "shared", "_archive", "insight"):
    sys.path.insert(0, os.path.join(_base, _sub))

import db
db.init()

import raw_stats
import distiller
from datetime import date

today = date.today().isoformat()

print(f"LAYER 2 -- raw stats for {today} (pure numbers, no AI):")
stats = raw_stats.day_stats(today)
for k, v in stats.items():
    if k != "hourly_focus":
        print(f"  {k}: {v}")
if not stats["hourly_focus"]:
    print("  hourly_focus: (not enough samples yet in any single hour)")

if stats["samples"] < 10:
    print(f"\nOnly {stats['samples']} activity samples logged today so far.")
    print("Leave WITNESS running a bit longer (it logs roughly every "
          "5 seconds while you're present), then run this again.")
else:
    print(f"\nLAYER 3 -- building colored document for {today}...")
    doc = distiller.build_daily(today)
    print(f"Saved to: insight_data/daily/{today}.json")
    print(f"\nSummary: {doc['summary']}")

print("\nDone. Open the file above in any text editor to see the full JSON.")
