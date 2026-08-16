"""Habit stacking. Morning and evening routines as specific sequences.
Tracked daily, correlated with performance over time.
"""
import json
from datetime import date

import data

DEFAULT_HABITS = {
    "morning": [
        {"name": "No phone first 30 min", "done": False},
        {"name": "Exercise / movement", "done": False},
        {"name": "Plan tasks for the day", "done": False},
        {"name": "Hydrate (2 glasses water)", "done": False},
    ],
    "evening": [
        {"name": "Daily recap", "done": False},
        {"name": "Plan tomorrow", "done": False},
        {"name": "Voice journal", "done": False},
        {"name": "No screens 30 min before bed", "done": False},
    ]
}


def get_today():
    d = data.load()
    if "habits" not in d:
        d["habits"] = {"date": "", "stacks": {}}
    if d["habits"].get("date") != date.today().isoformat():
        d["habits"] = {
            "date": date.today().isoformat(),
            "stacks": json.loads(json.dumps(DEFAULT_HABITS))
        }
        data.save(d)
    return d["habits"]["stacks"]


def toggle(stack_name, idx):
    d = data.load()
    stacks = get_today()
    if stack_name in stacks and 0 <= idx < len(stacks[stack_name]):
        stacks[stack_name][idx]["done"] = not stacks[stack_name][idx]["done"]
        d["habits"]["stacks"] = stacks
        data.save(d)
    return stacks


def completion_rate():
    stacks = get_today()
    total = sum(len(s) for s in stacks.values())
    done = sum(1 for s in stacks.values() for h in s if h.get("done"))
    return (done / total * 100) if total > 0 else 0


def get_custom():
    """Get custom habit definitions (user can modify these)."""
    d = data.load()
    return d.get("habit_definitions", DEFAULT_HABITS)


def set_custom(habits):
    d = data.load()
    d["habit_definitions"] = habits
    data.save(d)
