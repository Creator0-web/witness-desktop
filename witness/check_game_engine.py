"""Manual backend verification for the new WITNESS V1 game engine.

Run from the project root:

    python check_game_engine.py

It does not add XP or modify Activity history. It initializes additive DB
schema/migrations if needed, then prints the exact backend snapshot the future
polished dashboard will read.
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
for sub in ("core", "character", "shared", "_archive", "insight"):
    p = os.path.join(BASE, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

import db
import game_engine
import game_analytics


def main():
    db.init()
    game_engine.initialize()
    snap = game_engine.dashboard_snapshot()
    print("WITNESS V1 GAME ENGINE")
    print("=" * 70)
    print(json.dumps(snap, indent=2))
    print("\nANALYTICS READINESS")
    print("=" * 70)
    print(json.dumps(game_analytics.correlations(days=60), indent=2))


if __name__ == "__main__":
    main()
