"""
WITNESS v2 — main app.  Run: python main.py
Dashboard + voice + bubbles + manual Activities + Calendar + SOS.
"""

# ── Path bootstrap ──────────────────────────────────────────────────────
# Project code is sectioned into core/ (layer 1, frozen), character/
# (the persona/gamification layer), shared/ (utilities), and _archive/
# (quarantined layer 2/3 features, not deleted). This adds all of them
# to sys.path so every "import x" line everywhere in the codebase keeps
# working exactly as before, with zero import statements changed.
# See ARCHITECTURE.md before editing anything in core/.
import sys as _sys
import os as _os
_base = _os.path.dirname(_os.path.abspath(__file__))
from profile_runtime import activate as _activate_profile
_profile_runtime = _activate_profile(_base)
for _sub in ("core", "character", "shared", "_archive", "insight"):
    _p = _os.path.join(_base, _sub)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import os
import queue
import random
import threading
import time
import calendar as pycalendar
import tkinter as tk
from tkinter import filedialog
from datetime import date, datetime

import ai
# import chat  -- removed, unused now (the typed chat box is gone)
import timeutil
import brain
import lifedata
import strategist
import habits
import finance
import pipeline
import journal
from phone import PhoneDetector
from inputmon import InputMonitor
import config

# Bump this one line every time a fix ships to something the person
# needs to visually verify (like the goal projection math) -- shown in
# relevant window titles so "is this actually the new code?" has an
# immediate, unambiguous answer instead of a round of file-replacement
# guessing. See DEVLOG.md for the convention.
BUILD_TAG = "2026-08-14-e"
import data
import db
import game_engine  # shared/game_engine.py -- canonical V1 self-competition backend
import game_analytics  # shared/game_analytics.py -- behavior -> user-defined outcome associations
import store as insight_store  # insight/store.py -- daily suggestions
import projection as insight_projection  # insight/projection.py -- goal pace
import video_memories  # shared/video_memories.py -- calendar video archive
import day_breakdown  # shared/day_breakdown.py -- hourly history (synthetic preview for now)
import xp_triggers  # shared/xp_triggers.py -- dynamic, menu-editable XP triggers
import score as score_mod
import voice

# Optional: real OS-level drag-and-drop for the video calendar. Plain
# tkinter has no drag-and-drop support at all -- this is a separate
# package (pip install tkinterdnd2, see install.bat). The calendar
# panel works fully without it (via a file-picker "Add Video" button),
# this just upgrades it to accept actual drag-and-drop when available.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
from camera import PresenceWatcher
from tracker import WindowTracker
from patterns import PatternWatcher
from presence import PresenceEngine
from difficulty import BreakEnforcer, get_target, difficulty_context
import correlations
import weekly
import blocker
import nuclear
from vision import ScreenVision
import trail
import energy
import progression
import stats_engine
import export

state = {"present": False, "camera_ok": None, "stop": False, "muted": False,
         "current_app": "", "current_title": "", "deep_work_until": 0,
         "idle_seconds": 0, "input_active": True}
events = queue.Queue()

import json as _json

CONVO_FILE = "conversation.json"

def _load_convo():
    """Load conversation history from disk."""
    try:
        with open(CONVO_FILE, "r", encoding="utf-8") as f:
            convos = _json.load(f)
        # keep last 50 messages max
        return convos[-50:] if isinstance(convos, list) else []
    except Exception:
        return []

def _save_convo(history):
    """Save conversation history to disk (last 50 messages)."""
    try:
        with open(CONVO_FILE, "w", encoding="utf-8") as f:
            _json.dump(history[-50:], f, indent=1)
    except Exception:
        pass

BG, FG, DIM, ACCENT, RED, FIRE = ("#0e0e12", "#d4d4d8", "#6b6b76",
                                  "#6ba3be", "#c74b50", "#d4943a")
BG2 = "#141418"  # slightly lighter bg for cards/sections
BG3 = "#1a1a20"  # input fields
BORDER = "#2a2a32"  # subtle dividers


def scheduler():
    while not state["stop"]:
        time.sleep(config.ROUTINE_CHECKIN_MIN * 60)
        if state.get("present") and state["deep_work_until"] < time.time():
            events.put(("checkin", "routine", state["current_app"],
                        state["current_title"]))


def run_bg(fn, cb, root):
    """Run fn() in a thread; deliver result to cb on the UI thread."""
    def worker():
        try:
            result = fn()
        except Exception as e:
            result = f"(error: {e})"
        root.after(0, lambda: cb(result))
    threading.Thread(target=worker, daemon=True).start()


class WitnessUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(f"WITNESS — systems build {BUILD_TAG}")
        root.geometry("760x820+40+40")
        root.minsize(680, 720)
        root.attributes("-topmost", True)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.popup_open = False
        self.bubbles = []
        self.battle_mode = "daily"
        self._last_insight_refresh = 0
        self._last_chart_refresh = 0
        self._cached_insight_text = "Collecting enough history for correlations..."

        # This is intentionally a FUNCTIONAL pre-design surface. It exposes
        # the canonical game engine so every major system can be tested before
        # visual design begins. No scoring math is duplicated here.
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=18, pady=(10, 4))
        self.dot = tk.Label(header, text="●", font=("Arial", 10), fg="#555", bg=BG)
        self.dot.pack(side="left", padx=(0, 7))
        tk.Label(header, text="WITNESS", fg=FG, bg=BG,
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(header, text=f"  PRE-DESIGN / {BUILD_TAG}", fg=DIM, bg=BG,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        self.demo_badge = tk.Label(header, text="", fg="#d9b85b", bg=BG,
                                   font=("Segoe UI", 7, "bold"))
        self.demo_badge.pack(side="right")

        # ── ARENA / battle pacer ───────────────────────────────────────
        arena = tk.Frame(root, bg=BG2, highlightbackground=BORDER,
                         highlightthickness=1)
        arena.pack(fill="x", padx=16, pady=(4, 7))
        a_top = tk.Frame(arena, bg=BG2); a_top.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(a_top, text="BATTLE PACER", fg=FG, bg=BG2,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.daily_mode_btn = tk.Button(a_top, text="DAILY FIGHT",
            command=lambda: self.set_battle_mode("daily"), bg="#253a31", fg=FG,
            relief="flat", font=("Segoe UI", 7, "bold"), cursor="hand2")
        self.daily_mode_btn.pack(side="right", padx=(4, 0))
        self.weekly_mode_btn = tk.Button(a_top, text="WEEKLY CAMPAIGN",
            command=lambda: self.set_battle_mode("weekly"), bg=BG3, fg=DIM,
            relief="flat", font=("Segoe UI", 7, "bold"), cursor="hand2")
        self.weekly_mode_btn.pack(side="right")

        score_row = tk.Frame(arena, bg=BG2); score_row.pack(fill="x", padx=12)
        self.you_score_lbl = tk.Label(score_row, text="YOU  0 XP", fg=FG, bg=BG2,
                                      font=("Segoe UI", 18, "bold"))
        self.you_score_lbl.pack(side="left")
        self.ghost_score_lbl = tk.Label(score_row, text="GHOST  0 XP", fg=DIM, bg=BG2,
                                        font=("Segoe UI", 13, "bold"))
        self.ghost_score_lbl.pack(side="right")
        self.battle_canvas = tk.Canvas(arena, height=34, bg="#101014",
                                       highlightthickness=0)
        self.battle_canvas.pack(fill="x", padx=12, pady=(3, 1))
        under = tk.Frame(arena, bg=BG2); under.pack(fill="x", padx=12, pady=(0, 7))
        self.gap_lbl = tk.Label(under, text="", fg=FG, bg=BG2,
                                font=("Segoe UI", 10, "bold"))
        self.gap_lbl.pack(side="left")
        self.battle_meta_lbl = tk.Label(under, text="", fg=DIM, bg=BG2,
                                        font=("Segoe UI", 7))
        self.battle_meta_lbl.pack(side="left", padx=(10, 0))
        self.next_ghost_lbl = tk.Label(under, text="", fg=DIM, bg=BG2,
                                       font=("Segoe UI", 7))
        self.next_ghost_lbl.pack(side="right")

        # ── records + rolling level ─────────────────────────────────────
        status_row = tk.Frame(root, bg=BG); status_row.pack(fill="x", padx=16, pady=(0, 7))
        record_card = tk.Frame(status_row, bg=BG2, highlightbackground=BORDER,
                               highlightthickness=1)
        record_card.pack(side="left", fill="both", expand=True, padx=(0, 4))
        rr = tk.Frame(record_card, bg=BG2); rr.pack(fill="x", padx=10, pady=(7, 1))
        tk.Label(rr, text="HIGH SCORE / STREAKS", fg=DIM, bg=BG2,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Button(rr, text="Records", command=self.records_panel, bg=BG3, fg=DIM,
                  relief="flat", font=("Segoe UI", 7), cursor="hand2").pack(side="right")
        self.record_lbl = tk.Label(record_card, text="", fg=FG, bg=BG2,
                                   font=("Segoe UI", 9, "bold"), justify="left")
        self.record_lbl.pack(anchor="w", padx=10)
        self.streak_lbl = tk.Label(record_card, text="", fg=DIM, bg=BG2,
                                   font=("Segoe UI", 8), justify="left")
        self.streak_lbl.pack(anchor="w", padx=10, pady=(1, 8))

        level_card = tk.Frame(status_row, bg=BG2, highlightbackground=BORDER,
                              highlightthickness=1)
        level_card.pack(side="left", fill="both", expand=True, padx=(4, 0))
        lr = tk.Frame(level_card, bg=BG2); lr.pack(fill="x", padx=10, pady=(7, 1))
        tk.Label(lr, text="ROLLING LEVEL", fg=DIM, bg=BG2,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Button(lr, text="Details", command=self.level_panel, bg=BG3, fg=DIM,
                  relief="flat", font=("Segoe UI", 7), cursor="hand2").pack(side="right")
        self.level_lbl = tk.Label(level_card, text="", fg=FG, bg=BG2,
                                  font=("Segoe UI", 11, "bold"))
        self.level_lbl.pack(anchor="w", padx=10)
        self.level_detail_lbl = tk.Label(level_card, text="", fg=DIM, bg=BG2,
                                         font=("Segoe UI", 8), justify="left")
        self.level_detail_lbl.pack(anchor="w", padx=10, pady=(1, 8))

        # Compatibility containers retained but not displayed. Older methods
        # still exist below during the transition, but the Arena is canonical.
        self.sched_frame = tk.Frame(root, bg=BG)
        self.sched_labels = []
        self.tooltip = None
        self.task_vars = []
        self.appline = tk.Label(root, text="", fg=DIM, bg=BG, font=("Segoe UI", 7))

        # ── Activity Forge ──────────────────────────────────────────────
        activity_card = tk.Frame(root, bg=BG2, highlightbackground=BORDER,
                                 highlightthickness=1)
        activity_card.pack(fill="x", padx=16, pady=(0, 7))
        trow = tk.Frame(activity_card, bg=BG2); trow.pack(fill="x", padx=10, pady=(7, 2))
        tk.Label(trow, text="ACTIVITY FORGE", fg=FG, bg=BG2,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(trow, text="Scoring Setup", command=self.activities_window,
                  bg=BG3, fg=DIM, relief="flat", font=("Segoe UI", 7),
                  cursor="hand2").pack(side="right")
        self.tasks_frame = tk.Frame(activity_card, bg=BG2)
        self.tasks_frame.pack(fill="x", padx=10, pady=(0, 8))

        # ── performance + insight visibility ────────────────────────────
        lower = tk.Frame(root, bg=BG); lower.pack(fill="both", expand=True, padx=16)
        perf = tk.Frame(lower, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        perf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        pr = tk.Frame(perf, bg=BG2); pr.pack(fill="x", padx=10, pady=(7, 0))
        tk.Label(pr, text="SCORE TIMELINE", fg=DIM, bg=BG2,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Button(pr, text="Open Chart", command=self.show_chart, bg=BG3, fg=DIM,
                  relief="flat", font=("Segoe UI", 7), cursor="hand2").pack(side="right")
        self.mini_chart = tk.Canvas(perf, height=126, bg=BG2, highlightthickness=0)
        self.mini_chart.pack(fill="both", expand=True, padx=8, pady=(2, 6))

        insight = tk.Frame(lower, bg=BG2, highlightbackground=BORDER, highlightthickness=1)
        insight.pack(side="left", fill="both", expand=True, padx=(4, 0))
        ir = tk.Frame(insight, bg=BG2); ir.pack(fill="x", padx=10, pady=(7, 1))
        tk.Label(ir, text="INSIGHTS / WEEK CLOSURE", fg=DIM, bg=BG2,
                 font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Button(ir, text="Insights", command=self.insights_panel, bg=BG3, fg=DIM,
                  relief="flat", font=("Segoe UI", 7), cursor="hand2").pack(side="right")
        self.insight_teaser_lbl = tk.Label(insight, text="", fg=FG, bg=BG2,
                                           font=("Segoe UI", 8), wraplength=300,
                                           justify="left")
        self.insight_teaser_lbl.pack(anchor="w", padx=10, pady=(2, 5))
        self.week_close_lbl = tk.Label(insight, text="", fg=DIM, bg=BG2,
                                       font=("Segoe UI", 8), wraplength=300,
                                       justify="left")
        self.week_close_lbl.pack(anchor="w", padx=10)
        tk.Button(insight, text="Open Last Week", command=self.weekly_review_panel,
                  bg=BG3, fg=FG, relief="flat", font=("Segoe UI", 7),
                  cursor="hand2").pack(anchor="w", padx=10, pady=(4, 8))

        ai_live = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.ai_lbl = tk.Label(root,
            text="● AI connected" if ai_live else "○ AI offline — analytics still works",
            fg="#4a7a5c" if ai_live else DIM, bg=BG, font=("Segoe UI", 7))
        self.ai_lbl.pack(pady=(4, 0))
        self.convo_history = _load_convo()

        # ── bottom controls ─────────────────────────────────────────────
        bottom = tk.Frame(root, bg=BG); bottom.pack(fill="x", padx=12, pady=(4, 8))
        self.mute_btn = tk.Button(bottom, text="🔊", command=self.toggle_mute,
                                  bg=BG2, fg=DIM, relief="flat",
                                  font=("Segoe UI", 9), width=3, cursor="hand2")
        self.mute_btn.pack(side="left", padx=2)
        self.dw_btn = tk.Button(bottom, text="Focus", command=self.toggle_deep_work,
                                bg=BG2, fg=DIM, relief="flat",
                                font=("Segoe UI", 8), width=6, cursor="hand2")
        self.dw_btn.pack(side="left", padx=2)
        tk.Button(bottom, text="Calendar", command=self.calendar_panel,
                  bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                  width=8, cursor="hand2").pack(side="left", padx=2)
        tk.Button(bottom, text="Menu", command=self.show_menu,
                  bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                  width=6, cursor="hand2").pack(side="left", padx=2)
        tk.Button(bottom, text="SOS", command=self.sos,
                  bg="#8b2d30", fg="#e8e8e8", relief="flat",
                  font=("Segoe UI", 8, "bold"), width=5,
                  cursor="hand2").pack(side="right", padx=2)
        blocked, bmin = blocker.is_blocked()
        self.block_btn = tk.Button(bottom,
                  text=f"🔒{bmin}m" if blocked else "🔒",
                  command=self.toggle_block, bg=BG2, fg=DIM,
                  relief="flat", font=("Segoe UI", 8), width=5,
                  cursor="hand2")
        self.block_btn.pack(side="right", padx=2)

        self.refresh_static()
        self.tick()

        # Existing protective/runtime engines remain unchanged. core/ itself
        # is frozen; this build only changes their delivery surface.
        def pattern_convo(text):
            self.root.after(0, lambda: self._brain_respond(event=text))
        PatternWatcher(state, pattern_convo).start()
        PresenceEngine(state, pattern_convo).start()
        BreakEnforcer(state, pattern_convo).start()

        def vision_nuclear(proc, title):
            self.root.after(0, lambda: self.nuclear_response(proc, title))
        ScreenVision(state, vision_nuclear).start()
        trail.TrailWatcher(state, pattern_convo, lambda: None).start()
        InputMonitor(state).start()
        PhoneDetector(state, pattern_convo).start()


    # ── periodic UI update ──────────────────────────────────────────────
    def tick(self):
        if state["camera_ok"] is False:
            self.dot.config(fg="#e6a817")
        elif state.get("present"):
            self.dot.config(fg="#57cc99")
        else:
            self.dot.config(fg="#555")
        idle = int(state.get("idle_seconds", 0))
        idle_str = f" | idle {idle}s" if idle > 30 else ""
        self.appline.config(text=f"{state['current_app']}{idle_str}")

        try:
            self.refresh_arena()
        except Exception as ex:
            # The protection layer and bubbles should continue even if a
            # delivery widget hits a temporary error.
            self.insight_teaser_lbl.config(text=f"Arena refresh error: {ex}", fg=RED)

        try:
            blocked, bmin = blocker.is_blocked()
            self.block_btn.config(text=f"🔒 {bmin}m" if blocked else "🔒")
        except Exception:
            pass

        try:
            while True:
                self.show_bubble(voice.bubble_q.get_nowait())
        except queue.Empty:
            pass

        if not self.popup_open:
            try:
                ev = events.get_nowait()
                self.handle_event(ev)
            except queue.Empty:
                pass

        self.root.after(1000, self.tick)

    def set_battle_mode(self, mode):
        self.battle_mode = "weekly" if mode == "weekly" else "daily"
        daily_on = self.battle_mode == "daily"
        self.daily_mode_btn.config(bg="#253a31" if daily_on else BG3,
                                   fg=FG if daily_on else DIM)
        self.weekly_mode_btn.config(bg="#253a31" if not daily_on else BG3,
                                    fg=FG if not daily_on else DIM)
        self.refresh_arena(force=True)

    def refresh_arena(self, force=False):
        snap = game_engine.dashboard_snapshot()
        battle = snap["daily_battle"] if self.battle_mode == "daily" else snap["weekly_campaign"]
        you, ghost, gap = battle["you"], battle["ghost"], battle["gap"]
        status = battle["status"]
        fight_color = "#57cc99" if gap > 0 else (RED if gap < 0 else FIRE)
        self.you_score_lbl.config(text=f"YOU  {you:,} XP", fg=fight_color)
        self.ghost_score_lbl.config(text=f"GHOST  {ghost:,} XP")
        self.gap_lbl.config(text=f"{'+' if gap > 0 else ''}{gap:,} XP  {status.upper()}",
                            fg=fight_color)
        if self.battle_mode == "daily":
            self.battle_meta_lbl.config(
                text=f"{battle['day']} vs {battle['ghost_day']} · same clock {battle['same_clock']}")
            ng = battle.get("next_ghost_event")
            if ng:
                sign = "+" if ng["score_xp"] >= 0 else ""
                self.next_ghost_lbl.config(
                    text=f"Next ghost: {ng['clock']} {ng['activity']} {sign}{ng['score_xp']} XP")
            else:
                self.next_ghost_lbl.config(text="Ghost has no later event today")
        else:
            self.battle_meta_lbl.config(
                text=f"Week {battle['week_start']} vs {battle['ghost_week_start']} · live to now")
            player_bits = []
            for p in battle.get("players", []):
                marker = "+" if p["gap"] > 0 else ""
                player_bits.append(f"{p['weekday'][:3]} {marker}{p['gap']}")
            self.next_ghost_lbl.config(text=" | ".join(player_bits[-4:]))
        self._draw_battle_bar(battle)

        rec = snap["records"]
        if rec["daily_record_broken"]:
            record_line = f"NEW DAILY RECORD · {rec['current_daily']:,} XP"
        elif rec["daily_all_time_before"] > 0:
            record_line = (f"Daily record {rec['daily_all_time_before']:,} · "
                           f"{rec['daily_remaining']:,} XP to break")
        else:
            record_line = "First scored day sets the record"
        if rec["weekday_record_before"] > 0:
            record_line += (f"\n{rec['weekday_name']} best {rec['weekday_record_before']:,} XP")
        self.record_lbl.config(text=record_line)
        ds = snap["streaks"]["daily"]
        self.streak_lbl.config(
            text=(f"Daily win streak: {ds['completed']} completed"
                  f"{' + live win' if ds['live_ahead'] else ''}  ·  "
                  f"Weekly win streak: {snap['streaks']['weekly_completed']}"))

        lvl = snap["level"]
        level_color = FIRE if lvl["at_risk"] else ("#57cc99" if lvl["comeback_active"] else FG)
        self.level_lbl.config(text=f"Lv.{lvl['current_level']} {lvl['name']} · {lvl['rating']:,} rating",
                              fg=level_color)
        if lvl["next_threshold"]:
            detail = f"{lvl['xp_to_next']:,} rolling XP to next level · floor {lvl['demotion_floor']:,}"
        else:
            detail = f"Top V1 tier · floor {lvl['demotion_floor']:,}"
        if lvl["at_risk"]:
            hrs = int((lvl["at_risk_seconds_remaining"] or 0) / 3600)
            detail += f" · AT RISK ~{hrs}h left"
        if lvl["comeback_active"]:
            detail += f" · comeback {lvl['comeback_multiplier']}x level credit"
        self.level_detail_lbl.config(text=detail)

        now = time.time()
        if force or now - self._last_chart_refresh > 8:
            self._draw_mini_performance()
            self._last_chart_refresh = now
        if force or now - self._last_insight_refresh > 60:
            self._cached_insight_text = self._build_insight_teaser()
            self._last_insight_refresh = now
        self.insight_teaser_lbl.config(text=self._cached_insight_text, fg=FG)

        last = snap.get("last_completed_week", {})
        if last:
            gap_txt = f"{'+' if last.get('gap', 0) > 0 else ''}{last.get('gap', 0):,} XP"
            self.week_close_lbl.config(
                text=(f"Last week: {last.get('status', '?').upper()} · "
                      f"{last.get('you', 0):,} vs {last.get('ghost', 0):,} · {gap_txt}"))

        try:
            import demo_data
            ds = demo_data.status()
            self.demo_badge.config(text=(f"SYNTHETIC DEMO · {ds['days']} days"
                                         if ds["active"] else ""))
        except Exception:
            self.demo_badge.config(text="")

    def _draw_battle_bar(self, battle):
        c = self.battle_canvas
        c.delete("all")
        c.update_idletasks()
        w = max(100, c.winfo_width())
        you = max(0, int(battle.get("you", 0)))
        ghost = max(0, int(battle.get("ghost", 0)))
        ghost_final = max(0, int(battle.get("ghost_final", 0)))
        scale = max(1, you, ghost, ghost_final)
        pad = 52
        usable = max(20, w - pad - 10)
        def x(v):
            return pad + usable * max(0, v) / scale
        c.create_text(4, 9, text="YOU", fill=FG, anchor="w", font=("Segoe UI", 7, "bold"))
        c.create_text(4, 25, text="GHOST", fill=DIM, anchor="w", font=("Segoe UI", 7, "bold"))
        c.create_rectangle(pad, 4, pad + usable, 13, fill="#25252b", outline="")
        c.create_rectangle(pad, 20, pad + usable, 29, fill="#25252b", outline="")
        live_color = "#57cc99" if you >= ghost else "#c74b50"
        c.create_rectangle(pad, 4, x(you), 13, fill=live_color, outline="")
        c.create_rectangle(pad, 20, x(ghost), 29, fill="#777782", outline="")
        if ghost_final > 0:
            gx = x(ghost_final)
            c.create_line(gx, 2, gx, 31, fill="#a0a0aa", dash=(2, 2))

    def _draw_mini_performance(self):
        c = self.mini_chart
        c.delete("all")
        c.update_idletasks()
        w, h = max(120, c.winfo_width()), max(90, c.winfo_height())
        rows = game_engine.performance_series(14)
        vals = [r["score_xp"] for r in rows]
        ghosts = [r["ghost_xp"] for r in rows]
        ymax = max([1] + vals + ghosts)
        ml, mr, mt, mb = 34, 8, 8, 20
        pw, ph = max(1, w-ml-mr), max(1, h-mt-mb)
        def px(i): return ml + (pw * i / max(1, len(rows)-1))
        def py(v): return mt + ph * (1 - max(0, v)/ymax)
        for frac in (0, .5, 1):
            y = mt + ph * frac
            c.create_line(ml, y, w-mr, y, fill="#292930")
        if len(rows) > 1:
            ghost_pts=[]; live_pts=[]
            for i,r in enumerate(rows):
                ghost_pts += [px(i), py(r["ghost_xp"])]
                live_pts += [px(i), py(r["score_xp"])]
            c.create_line(*ghost_pts, fill="#666670", width=1, dash=(3,3), smooth=True)
            c.create_line(*live_pts, fill="#57cc99", width=2, smooth=True)
        for i, r in enumerate(rows):
            if i in (0, len(rows)-1) or i % 4 == 0:
                c.create_text(px(i), h-5, text=r["weekday"], fill="#666670",
                              font=("Segoe UI", 6), anchor="s")
        c.create_text(2, mt, text=f"{ymax:,}", fill="#666670",
                      font=("Segoe UI", 6), anchor="nw")
        c.create_text(2, mt+ph, text="0", fill="#666670",
                      font=("Segoe UI", 6), anchor="sw")

    def _build_insight_teaser(self):
        try:
            out = game_analytics.correlations(days=60)
        except Exception as ex:
            return f"Analytics unavailable: {ex}"
        if not out.get("ready"):
            return (f"Analytics: {out.get('tracked_days', 0)}/{out.get('minimum_days', 7)} "
                    "tracked/scored days. More history needed.")
        corr = out.get("correlations", [])
        if not corr:
            return "Analytics has enough history, but no varying signal is strong enough to rank yet."
        top = corr[0]
        return (f"Top observed association ({top['sample_days']} days): "
                f"{top['label']} — {top['association']} "
                f"({top['strength']}, r={top['spearman_r']:+.2f}).")

    def refresh_static(self):
        # Static refresh now means: roster + canonical Arena. Legacy goal/
        # schedule/energy widgets are no longer part of the active surface.
        self.refresh_tasks()
        try:
            self.refresh_arena(force=True)
        except Exception:
            pass

    def refresh_tasks(self):
        """Render the deliberately-plain V1 Activity Forge controls.

        This is still backend-first: rows are functional controls over the
        canonical timestamped ledger in shared/game_engine.py, not the final
        visual card design. Repeatables can be hit endlessly, once-daily
        activities complete once, and timed activities add 15-minute chunks.
        """
        for w in self.tasks_frame.winfo_children():
            w.destroy()
        self.task_vars = []  # kept only for compatibility with older UI code
        try:
            items = game_engine.activities_snapshot()
        except Exception as ex:
            tk.Label(self.tasks_frame, text=f"Activity backend error: {ex}",
                     fg=RED, bg=BG, font=("Segoe UI", 8)).pack(pady=2)
            return

        def add_one(aid):
            try:
                event = game_engine.record_activity(aid)
                self.convo_add(
                    "Witness",
                    f"{event['activity_name']} +{event['score_xp']} XP. "
                    f"Today: {event['day_total']} XP.",
                    speak_it=False)
            except game_engine.ActivityAlreadyCompleted:
                self.convo_add("Witness", "Already completed today.", speak_it=False)
            except Exception as ex:
                self.convo_add("Witness", f"XP ERROR: {ex}", speak_it=False)
            self.refresh_tasks()

        def add_minutes(aid, mins=15):
            try:
                event = game_engine.record_activity(aid, minutes=mins)
                self.convo_add(
                    "Witness",
                    f"{event['activity_name']} +{event['score_xp']} XP "
                    f"({mins} min). Today: {event['day_total']} XP.",
                    speak_it=False)
            except Exception as ex:
                self.convo_add("Witness", f"XP ERROR: {ex}", speak_it=False)
            self.refresh_tasks()

        def undo_one(aid):
            try:
                event = game_engine.undo_last_activity(aid)
                self.convo_add(
                    "Witness",
                    f"Undid {event['activity_name']} ({event['score_xp']} XP). "
                    f"Today: {event['day_total']} XP.",
                    speak_it=False)
            except game_engine.NothingToUndo:
                self.convo_add("Witness", "Nothing to undo for today.", speak_it=False)
            except Exception as ex:
                self.convo_add("Witness", f"UNDO ERROR: {ex}", speak_it=False)
            self.refresh_tasks()

        for a in items:
            row = tk.Frame(self.tasks_frame, bg=BG)
            row.pack(fill="x", pady=1)
            st = a["today"]
            kind = a["kind"]
            xp = int(a["xp_value"])
            if kind == "timed":
                units = int(round(st["units"]))
                label = f"{a['name']}  (+{xp} XP/hr)   {units}m | {st['score_xp']} XP"
                tk.Label(row, text=label, fg=FG, bg=BG, anchor="w",
                         font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)
                tk.Button(row, text="+15m", command=lambda aid=a["id"]: add_minutes(aid),
                          bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 7),
                          width=5, cursor="hand2").pack(side="right", padx=(2, 0))
            elif kind == "once_daily":
                done = bool(st["complete"])
                label = f"{'✓ ' if done else ''}{a['name']}  (+{xp} XP)"
                tk.Label(row, text=label, fg=DIM if done else FG, bg=BG, anchor="w",
                         font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)
                if not done:
                    tk.Button(row, text="Done", command=lambda aid=a["id"]: add_one(aid),
                              bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 7),
                              width=5, cursor="hand2").pack(side="right", padx=(2, 0))
            else:
                units = st["units"]
                units_txt = str(int(units)) if float(units).is_integer() else f"{units:g}"
                label = f"{a['name']}  (+{xp} XP)   x{units_txt} | {st['score_xp']} XP"
                tk.Label(row, text=label, fg=FG, bg=BG, anchor="w",
                         font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True)
                tk.Button(row, text="+1", command=lambda aid=a["id"]: add_one(aid),
                          bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8, "bold"),
                          width=4, cursor="hand2").pack(side="right", padx=(2, 0))

            if st["units"] > 0:
                tk.Button(row, text="↶", command=lambda aid=a["id"]: undo_one(aid),
                          bg=BG, fg=DIM, relief="flat", font=("Segoe UI", 7),
                          width=2, cursor="hand2").pack(side="right", padx=(2, 0))

        if not items:
            tk.Label(self.tasks_frame,
                     text="(no activities yet — hit Edit to add one)",
                     fg=DIM, bg=BG, font=("Segoe UI", 8)).pack(pady=2)

    def draw_timeline(self):
        c = self.timeline
        c.delete("all")
        w = c.winfo_width()
        if w < 50:
            return
        d = data.load()
        tasks = data.get_tasks()
        now24 = timeutil.now24()

        # day range: 7:00 to 22:00 (15 hours)
        day_start, day_end = 7, 22
        span = day_end - day_start

        def x_for(t24):
            try:
                h, m = t24.split(":")
                frac = (int(h) + int(m)/60 - day_start) / span
                return max(6, min(w - 6, int(6 + frac * (w - 12))))
            except:
                return 6

        # background track
        c.create_rectangle(6, 14, w-6, 26, fill="#1c1c24", outline="")

        # schedule blocks as colored segments
        for blk in d["schedule"]:
            x1 = x_for(blk["start"])
            x2 = x_for(blk["end"])
            c.create_rectangle(x1, 14, x2, 26, fill="#1d3557", outline="#2a4a7f")

        # task deadline markers
        for t in tasks:
            bx = x_for(t.get("by", "23:59"))
            color = "#57cc99" if t.get("done") else ("#e63946" if t.get("by","23:59") <= now24 else FIRE)
            c.create_line(bx, 10, bx, 30, fill=color, width=2)
            c.create_oval(bx-3, 7, bx+3, 13, fill=color, outline="")

        # hour labels
        for h in range(day_start, day_end + 1, 2):
            x = x_for(f"{h:02d}:00")
            h12 = h % 12 or 12
            sfx = "a" if h < 12 else "p"
            c.create_text(x, 35, text=f"{h12}{sfx}", fill="#555",
                          font=("Consolas", 7), anchor="n")

        # current time marker
        nx = x_for(now24)
        c.create_line(nx, 8, nx, 32, fill="white", width=2)
        c.create_text(nx, 3, text=timeutil.now12(), fill="white",
                      font=("Consolas", 7), anchor="s")

        # hover tooltips
        def on_hover(event):
            if self.tooltip:
                self.tooltip.destroy()
            # find what's at this x position
            frac = (event.x - 6) / max(1, w - 12)
            hover_h = day_start + frac * span
            hover_t = f"{int(hover_h):02d}:{int((hover_h % 1)*60):02d}"
            info = timeutil.to12(hover_t)
            # check schedule
            for blk in d["schedule"]:
                if blk["start"] <= hover_t < blk["end"]:
                    info += f"\n{blk['label']}"
                    break
            # check tasks near this time
            for t in tasks:
                if abs(x_for(t.get("by","23:59")) - event.x) < 15:
                    status = "✓" if t.get("done") else "○"
                    info += f"\n{status} by {timeutil.to12(t.get('by',''))} {t['text']}"
            self.tooltip = tk.Toplevel(self.root)
            self.tooltip.overrideredirect(True)
            self.tooltip.attributes("-topmost", True)
            tk.Label(self.tooltip, text=info, bg="#2a2a34", fg=FG,
                     font=("Consolas", 8), padx=6, pady=4,
                     justify="left").pack()
            self.tooltip.geometry(
                f"+{self.root.winfo_rootx()+event.x+10}"
                f"+{self.root.winfo_rooty()+c.winfo_y()-40}")

        def on_leave(event):
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None

        c.bind("<Motion>", on_hover)
        c.bind("<Leave>", on_leave)

    def draw_jar(self):
        """Draw a male silhouette energy jar."""
        c = self.jar_canvas
        c.delete("all")
        e = energy.calculate()
        fill_pct = e["total"] / 100
        color = e["color"]

        # male silhouette outline — anatomically proportioned
        # head (oval)
        # silhouette outline color evolves with level
        try:
            prog = progression.get_stats()
            outline_color = prog["color"]
            glow = prog["level"] >= 10
        except Exception:
            outline_color = "#3a3a42"
            glow = False

        if glow:
            # glow effect for high levels
            c.create_oval(27, -1, 53, 27, outline=outline_color,
                          width=1)
        c.create_oval(30, 2, 50, 24, outline=outline_color, width=1.5)

        # neck
        neck = [(36, 24), (44, 24), (44, 30), (36, 30)]

        # body — broad shoulders, tapered waist, legs
        body_points = [
            # right shoulder
            (44, 30), (56, 34), (60, 38),
            # right arm (tucked)
            (62, 42), (63, 60), (62, 78), (60, 82),
            # right side torso
            (56, 82), (54, 90), (52, 98),
            # right hip
            (54, 104), (54, 108),
            # right leg outer
            (56, 118), (56, 130), (55, 140), (54, 148),
            # right foot
            (56, 152), (56, 156), (48, 156),
            # right leg inner
            (48, 152), (46, 140), (44, 130), (43, 118),
            # crotch
            (42, 112), (40, 112), (38, 112),
            # left leg inner
            (37, 118), (36, 130), (34, 140), (32, 152),
            # left foot
            (32, 156), (24, 156), (24, 152),
            # left leg outer
            (26, 148), (25, 140), (24, 130), (24, 118),
            # left hip
            (26, 108), (26, 104),
            # left side torso
            (28, 98), (26, 90), (24, 82),
            # left arm (tucked)
            (20, 82), (18, 78), (17, 60), (18, 42),
            # left shoulder
            (20, 38), (24, 34), (36, 30),
        ]

        # draw outline
        flat = []
        for x, y in body_points:
            flat.extend([x, y])
        c.create_polygon(flat, outline=outline_color, fill="", width=1.5,
                          smooth=True)

        # fill with liquid from bottom up
        if fill_pct > 0:
            fill_top = int(156 - fill_pct * 130)  # 156=feet, 26=shoulders

            # draw fill rectangles inside body shape
            for y in range(156, max(fill_top, 26), -2):
                # calculate body width at this y level
                if y > 148:       # feet
                    lx, rx = 26, 54
                elif y > 140:     # ankles
                    lx, rx = 26, 55
                elif y > 118:     # legs
                    lx, rx = 25, 56
                elif y > 112:     # upper legs
                    lx, rx = 26, 54
                elif y > 104:     # hips
                    lx, rx = 27, 54
                elif y > 98:      # waist
                    lx, rx = 28, 53
                elif y > 82:      # lower torso
                    lx, rx = 26, 56
                elif y > 60:      # mid torso
                    lx, rx = 20, 62
                elif y > 42:      # upper torso
                    lx, rx = 19, 63
                elif y > 34:      # shoulders
                    lx, rx = 22, 60
                else:             # neck
                    lx, rx = 36, 44

                c.create_rectangle(lx + 3, y - 1, rx - 3, y + 1,
                                   fill=color, outline="")

            # liquid surface highlight
            if fill_top < 150:
                sy = fill_top
                if sy > 118:
                    sl, sr = 27, 55
                elif sy > 104:
                    sl, sr = 28, 54
                elif sy > 82:
                    sl, sr = 27, 55
                elif sy > 42:
                    sl, sr = 22, 60
                else:
                    sl, sr = 34, 46
                c.create_line(sl + 3, sy, sr - 3, sy,
                              fill="white", width=1)

        # percentage text centered on torso
        text_color = "white" if fill_pct > 0.35 else "#555"
        c.create_text(40, 80, text=f"{e['total']}%",
                      fill=text_color, font=("Segoe UI", 11, "bold"))

        # update labels
        self.jar_level_lbl.config(text=e["level"], fg=color)
        self.jar_pct_lbl.config(text=f"{e['total']}% energy")
        clean_text = (f"{e['clean_days']} days clean"
                      if e["clean_days"] > 0 else "Day 0 — rebuilding")
        self.jar_clean_lbl.config(text=clean_text,
                                  fg="#57cc99" if e["clean_days"] >= 7
                                  else FG)
        self.jar_breakdown_lbl.config(text=e["breakdown"])
        self.jar_suggest_lbl.config(text=energy.suggest_action())

    def highlight_schedule(self):
        now = datetime.now().strftime("%H:%M")
        d = data.load()
        current = None
        for lab, blk in zip(self.sched_labels, d["schedule"]):
            active = blk["start"] <= now < blk["end"]
            if active:
                current = blk["label"]
            lab.config(fg=FG if active else DIM,
                       font=("Segoe UI", 8, "bold" if active else "normal"))
        # speak block transitions so the day has a pulse
        if current != self.last_block:
            if self.last_block is not None and current and \
                    state.get("present"):
                voice.speak(f"New block: {current}")
            self.last_block = current

    # ── unified conversation ────────────────────────────────────────────
    def convo_add(self, who, text, speak_it=True):
        """Record a line in conversation history and speak it if it's
        from Witness. No visual log widget anymore -- Witness's spoken
        lines already appear as floating bubbles via voice.bubble_q."""
        # strip any markdown/emoji formatting the AI sneaks in
        if who == "Witness":
            import re
            text = text.replace("**", "").replace("*", "").replace("##", "").replace("# ", "")
            # remove emoji
            text = re.sub(r'[^-‘’“”—–…]+', '', text)
            text = re.sub(r'  +', ' ', text).strip()
        if who == "Witness":
            self.convo_history.append({"role": "assistant", "content": text})
            if speak_it:
                voice.speak_voice_only(text)
        else:
            self.convo_history.append({"role": "user", "content": text})
        _save_convo(self.convo_history)

    # convo_send / _do_chat removed -- these drove the typed chat box,
    # which no longer exists (see __init__: "Conversation box removed
    # entirely"). _direct_add_task below is left in place, unused for
    # now, in case typed input is reconnected to something later.

    def _direct_add_task(self, text):
        """Directly add a task without relying on the brain."""
        import re
        # try to extract XP value if mentioned
        xp = 15
        xp_words = {"big": 200, "huge": 250, "massive": 300,
                     "important": 150, "high": 150, "lot": 200,
                     "serious": 200, "major": 200}
        text_lower = text.lower()
        for word, val in xp_words.items():
            if word in text_lower:
                xp = val
                break
        # try to find a number for XP
        nums = re.findall(r'(\d+)\s*xp', text_lower)
        if nums:
            xp = int(nums[0])

        # extract the task description — remove command words
        desc = text
        for phrase in ["add task", "add to tasks", "add to my tasks",
                       "add to my plan", "add to plan", "add to my list",
                       "add to list", "put on my list",
                       "make it", "high xp", "big xp", "worth",
                       "a lot of xp", "serious xp", "please", "can you"]:
            desc = re.sub(re.escape(phrase), "", desc, flags=re.IGNORECASE)
        desc = re.sub(r'\d+\s*xp', '', desc, flags=re.IGNORECASE)
        desc = desc.strip().strip(".,!?:;-").strip()

        if not desc or len(desc) < 3:
            desc = text.strip()

        # capitalize first letter
        desc = desc[0].upper() + desc[1:] if desc else desc

        tasks = data.get_tasks()
        tasks.append({"text": desc, "by": "23:59", "done": False,
                      "custom_xp": xp})
        data.set_tasks(tasks)
        self.refresh_tasks()
        self.convo_add("Witness",
                       f"Added: {desc} [{xp} XP]. It's on the list.",
                       speak_it=True)

    def _brain_respond(self, event=None):
        """Route everything through the unified brain."""
        hist = list(self.convo_history[-30:])

        def got(result):
            if isinstance(result, str):
                result = {"text": result, "actions": []}
            text = result.get("text", "")
            actions = result.get("actions", [])
            if actions and not text:
                text = "(done)"
            if not text or text.strip() in ("", "-", "--", "—", "——"):
                return  # skip empty/dash responses
            self.convo_add("Witness", text)
            self._handle_actions(actions)
            for a in actions:
                if a.startswith("ACTION:ADD_TASK:"):
                    self.convo_add("Witness", "Task added.",
                                  speak_it=False)

        def failed(error):
            self.convo_add("Witness",
                           f"(brain error: {error})", speak_it=False)

        def do_respond():
            try:
                return brain.respond(hist, event=event)
            except Exception as e:
                return {"text": f"(error: {e})", "actions": []}

        run_bg(do_respond, got, self.root)

    def _handle_actions(self, actions):
        """Parse and execute ACTION tags from brain responses."""
        for action in actions:
            action = action.strip()
            if action == "ACTION:LOG_REDLINE":
                db.log_redline("self-reported via chat")
                try:
                    import energy
                    self.draw_jar()
                except Exception:
                    pass
            elif action.startswith("ACTION:LOG_WIN:"):
                desc = action.replace("ACTION:LOG_WIN:", "").strip()
                if desc:
                    data.add_win(desc)
            elif action.startswith("ACTION:LOG_SOS:"):
                trigger = action.replace("ACTION:LOG_SOS:", "").strip()
                db.log_sos(trigger, "chat conversation")
            elif action.startswith("ACTION:CLEAN_RESET:"):
                try:
                    days = int(action.replace("ACTION:CLEAN_RESET:", "").strip())
                    import energy as energy_mod
                    energy_mod.set_clean_start(days)
                    self.draw_jar()
                except Exception:
                    pass
            elif action.startswith("ACTION:ADD_TASK:"):
                try:
                    parts = action.replace("ACTION:ADD_TASK:", "").split("|")
                    if len(parts) >= 2:
                        by_time = parts[0].strip()
                        task_text = parts[1].strip()
                        xp_val = int(parts[2].strip()) if len(parts) >= 3 else 15
                        tasks = data.get_tasks()
                        tasks.append({"text": task_text, "by": by_time,
                                      "done": False, "custom_xp": xp_val})
                        data.set_tasks(tasks)
                        self.refresh_tasks()
                except Exception:
                    pass
            elif action.startswith("ACTION:SET_MISSION:"):
                try:
                    new_mission = action.replace("ACTION:SET_MISSION:", "").strip()
                    if new_mission:
                        d = data.load()
                        d["mission"] = new_mission
                        data.save(d)
                        self.refresh_static()
                except Exception:
                    pass
            elif action.startswith("ACTION:ADD_GOAL:"):
                try:
                    parts = action.replace("ACTION:ADD_GOAL:", "").split("|")
                    if parts:
                        data.add_goal(
                            parts[0].strip(),
                            parts[1].strip() if len(parts) > 1 else "",
                            parts[2].strip() if len(parts) > 2 else "",
                            parts[3].strip() if len(parts) > 3 else "")
                except Exception:
                    pass
            elif action.startswith("ACTION:LIFE:"):
                parts = action.replace("ACTION:LIFE:", "").split(":", 1)
                if len(parts) == 2:
                    field, value = parts[0].strip(), parts[1].strip()
                    try:
                        value = float(value) if value.replace(".", "").isdigit() else value
                    except Exception:
                        pass
                    lifedata.log_day_field(field, value)
            elif action.startswith("ACTION:MILESTONE:"):
                desc = action.replace("ACTION:MILESTONE:", "").strip()
                if desc:
                    data.add_win(f"MILESTONE: {desc}")

    # ── events ──────────────────────────────────────────────────────────
    def handle_event(self, ev):
        kind = ev[0]
        if kind == "greet":
            run_bg(lambda: ai.greeting_line(ev[1]),
                   lambda t: self.convo_add("Witness", t), self.root)
        elif kind == "speak_escalation":
            _, stage, proc, title = ev
            run_bg(lambda: ai.escalation_line(stage, proc, title),
                   lambda t: self.convo_add("Witness", t), self.root)
        elif kind == "checkin":
            _, ck, proc, title = ev
            if ck == "redline":
                self.nuclear_response(proc, title)
                return
            elif ck in ("offtask", "drift", "routine"):
                ctx = {"active_app": proc, "window_title": title[:80]}
                run_bg(lambda: ai.checkin_question(ck, ctx),
                       lambda t: self.convo_add("Witness", t), self.root)

    def show_bubble(self, text):
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.attributes("-topmost", True)
        b.configure(bg="#1c1c24")
        tk.Label(b, text=text, fg=FG, bg="#1c1c24", wraplength=300,
                 font=("Arial", 10), padx=14, pady=10).pack()
        b.update_idletasks()
        sw = self.root.winfo_screenwidth()
        y = 80 + 90 * len([x for x in self.bubbles if x.winfo_exists()])
        b.geometry(f"+{sw - b.winfo_width() - 30}+{y}")
        self.bubbles.append(b)
        b.after(10000, b.destroy)

    # ── check-in window ─────────────────────────────────────────────────
            # ── SOS ─────────────────────────────────────────────────────────────
    def sos(self):
        videos = []
        if os.path.isdir(config.SOS_VIDEO_DIR):
            videos = [os.path.join(config.SOS_VIDEO_DIR, f)
                      for f in os.listdir(config.SOS_VIDEO_DIR)
                      if f.lower().endswith((".mp4", ".mov", ".mkv", ".webm",
                                            ".avi"))]
        random.shuffle(videos)
        played = {"n": 0}

        win = tk.Toplevel(self.root)
        win.title("SOS")
        win.attributes("-topmost", True)
        win.configure(bg="#17171d")
        win.geometry("460x260")
        msg = tk.Label(win, text="...", fg=FG, bg="#17171d", wraplength=420,
                       font=("Arial", 11))
        msg.pack(pady=(14, 8))
        btns = tk.Frame(win, bg="#17171d"); btns.pack()

        def set_msg(t):
            msg.config(text=t); voice.speak(t)

        def play_next():
            if played["n"] < len(videos) and played["n"] < 2:
                try:
                    os.startfile(os.path.abspath(videos[played["n"]]))
                except Exception:
                    pass
                played["n"] += 1
            else:
                talk_stage()

        def watched():
            if played["n"] >= 2 or played["n"] >= len(videos):
                talk_stage()
            else:
                run_bg(lambda: ai.sos_line("after_video"), set_msg, self.root)
                play_next()

        def talk_stage():
            for w in btns.winfo_children():
                w.destroy()
            run_bg(lambda: ai.sos_line("talk"), set_msg, self.root)
            entry = tk.Text(win, height=3, width=48, bg="#0d0d0f", fg=FG,
                            insertbackground=FG)
            entry.pack(pady=6); entry.focus_set()

            def done():
                trigger = entry.get("1.0", "end").strip() or "(unspoken)"
                db.log_sos(trigger, "worked through it")
                data.add_win("Hit SOS and worked through an urge instead of "
                             "acting on it.")
                voice.speak("Logged as a win. That's the rep that counts.")
                win.destroy()
            tk.Button(win, text="I'm good — back to work", command=done,
                      bg="#2c2c36", fg=FG, relief="flat").pack()

        if videos:
            run_bg(lambda: ai.sos_line("open"), set_msg, self.root)
            tk.Button(btns, text="▶ Play my video", command=play_next,
                      bg="#2c2c36", fg=FG, relief="flat").pack(side="left",
                                                              padx=4)
            tk.Button(btns, text="I watched it", command=watched,
                      bg="#2c2c36", fg=FG, relief="flat").pack(side="left",
                                                              padx=4)
        else:
            set_msg("No videos in the sos_videos folder yet — drop a few in. "
                    "For now: talk to me.")
            talk_stage()

    # ── panels: goals / wins / money ────────────────────────────────────
    def panel(self, which):
        d = data.load()
        win = tk.Toplevel(self.root)
        win.title(which.capitalize())
        win.attributes("-topmost", True)
        win.configure(bg="#17171d")
        win.geometry("480x430")

        if which == "money":
            fields = ["target_monthly", "current_monthly", "savings", "debt",
                      "subscriptions", "deadline_note"]
            entries = {}
            for f in fields:
                tk.Label(win, text=f.replace("_", " "), fg=DIM, bg="#17171d",
                         font=("Consolas", 9)).pack()
                e = tk.Entry(win, width=40, bg="#0d0d0f", fg=FG,
                             insertbackground=FG)
                e.insert(0, str(d["money"][f])); e.pack(pady=(0, 6))
                entries[f] = e

            def save_money():
                for f in fields:
                    v = entries[f].get().strip()
                    d["money"][f] = v if f == "deadline_note" else \
                        int(float(v or 0))
                data.save(d); self.refresh_static(); win.destroy()
            tk.Button(win, text="Save", command=save_money, bg="#2c2c36",
                      fg=FG, relief="flat", width=12).pack(pady=8)
            return

        # goals & wins share a list+add layout
        box = tk.Text(win, wrap="word", bg="#0d0d0f", fg=FG, height=14,
                      padx=10, pady=10)
        box.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        if which == "goals":
            box.insert("1.0", f"LIFESTYLE: {d['lifestyle']}\n"
                              f"MISSION: {d['mission']}\n\n")
            for i, g in enumerate(d["goals"], 1):
                box.insert("end", f"{i}. {g['title']}\n   why: {g['why']}\n"
                                  f"   by: {g['target_date']} | stakes: "
                                  f"{g['stakes']}\n")
            tk.Label(win, text="Add goal — one line: "
                     "title | why | target date | stakes", fg=DIM,
                     bg="#17171d", font=("Consolas", 8)).pack()
        else:
            for w in d["wins"][-40:]:
                box.insert("end", f"[{w['date']}] {w['text']}\n")
            tk.Label(win, text="Add a win:", fg=DIM, bg="#17171d",
                     font=("Consolas", 8)).pack()
        box.config(state="disabled")
        entry = tk.Entry(win, width=60, bg="#0d0d0f", fg=FG,
                         insertbackground=FG)
        entry.pack(pady=4)

        def add():
            t = entry.get().strip()
            if not t:
                return
            if which == "goals":
                parts = [p.strip() for p in t.split("|")] + ["", "", ""]
                data.add_goal(parts[0], parts[1], parts[2], parts[3])
            else:
                data.add_win(t)
                voice.speak("Win logged. Stack them.")
            win.destroy(); self.panel(which)
        tk.Button(win, text="Add", command=add, bg="#2c2c36", fg=FG,
                  relief="flat", width=10).pack(pady=4)
        if which == "goals":
            def edit_core():
                win.destroy(); self.edit_core()
            tk.Button(win, text="Edit lifestyle / mission", command=edit_core,
                      bg="#2c2c36", fg=FG, relief="flat").pack(pady=(0, 8))

    def metrics_panel(self, category):
        metrics = data.get_metrics()
        items = metrics[category]
        win = tk.Toplevel(self.root)
        win.title(f"{category.capitalize()} Tracker")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("380x360")
        tk.Label(win, text=category.upper(), fg=DIM, bg="#141418",
                 font=("Segoe UI", 9, "bold")).pack(pady=(10, 6))
        entries = {}
        for key, val in items.items():
            row = tk.Frame(win, bg="#141418")
            row.pack(fill="x", padx=20, pady=3)
            label = key.replace("_", " ").title()
            tk.Label(row, text=label, fg=FG, bg="#141418",
                     font=("Segoe UI", 9), width=16, anchor="w").pack(side="left")
            if isinstance(val, bool):
                var = tk.IntVar(value=1 if val else 0)
                tk.Checkbutton(row, variable=var, bg="#141418",
                               activebackground="#141418",
                               selectcolor=BG3).pack(side="left")
                entries[key] = ("bool", var)
            else:
                e = tk.Entry(row, width=10, bg=BG3, fg=FG,
                             insertbackground=FG, font=("Segoe UI", 9),
                             relief="flat")
                e.insert(0, str(val))
                e.pack(side="left", padx=(4, 0))
                entries[key] = ("num", e)

        def save_metrics():
            for key, (kind, widget) in entries.items():
                if kind == "bool":
                    data.update_metric(category, key, bool(widget.get()))
                else:
                    try:
                        v = widget.get().strip()
                        data.update_metric(category, key,
                                           float(v) if "." in v else int(v))
                    except ValueError:
                        pass
            total = sum(1 for k, v in data.get_metrics()[category].items()
                        if (isinstance(v, bool) and v) or
                        (isinstance(v, (int, float)) and v > 0))
            self.convo_add("Witness",
                           f"{category.capitalize()} updated. "
                           f"{total}/{len(entries)} metrics active.")
            win.destroy()

        tk.Button(win, text="Save", command=save_metrics, bg=BG2,
                  fg=FG, relief="flat", font=("Segoe UI", 9),
                  cursor="hand2", width=12).pack(pady=10)

    def show_menu(self):
        win = tk.Toplevel(self.root)
        win.title(f"WITNESS Menu — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("340x455")

        def mbtn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=lambda: (cmd(), win.destroy()),
                          bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 9),
                          cursor="hand2", activebackground="#222228",
                          anchor="w", padx=16)
            b.pack(fill="x", padx=12, pady=2)

        tk.Label(win, text="DO / HISTORY", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
        mbtn(win, "Activity Forge / Scoring Setup", self.activities_window)
        mbtn(win, "Calendar / History", self.calendar_panel)

        tk.Label(win, text="GAME", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16, pady=(10, 2))
        mbtn(win, "Records / High Scores", self.records_panel)
        mbtn(win, "Rolling Level Details", self.level_panel)
        mbtn(win, "Weekly Closure", self.weekly_review_panel)
        mbtn(win, "Performance Chart", self.show_chart)

        tk.Label(win, text="INTELLIGENCE", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16, pady=(10, 2))
        mbtn(win, "Behavior → Score Insights", self.insights_panel)

        tk.Label(win, text="SETTINGS / BUILD", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16, pady=(10, 2))
        mbtn(win, "Integrations", self.integrations_panel)
        mbtn(win, "Synthetic Demo History", self.demo_data_panel)
        mbtn(win, "Raw Backend Snapshot", self.backend_snapshot_panel)

    def records_panel(self):
        win = tk.Toplevel(self.root)
        win.title(f"Records / High Scores — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("590x650")
        tk.Label(win, text="RECORDS / HIGH SCORES", fg=FG, bg="#141418",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        box = tk.Text(win, wrap="word", bg=BG2, fg=FG, insertbackground=FG,
                      font=("Consolas", 9), relief="flat", padx=12, pady=10)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        hof = game_engine.hall_of_fame()
        rec = game_engine.records_snapshot()
        lines = []
        bd = hof.get("best_day")
        bw = hof.get("best_week")
        lines.append("ALL-TIME\n")
        lines.append(f"Best day:  {bd['day']} — {bd['score_xp']:,} XP\n" if bd else "Best day:  none yet\n")
        lines.append(f"Best week: {bw['week_start']} — {bw['score_xp']:,} XP\n" if bw else "Best week: none yet\n")
        lines.append(f"Current day: {rec['current_daily']:,} XP\n")
        if rec["daily_all_time_before"]:
            lines.append(f"XP to prior daily record: {rec['daily_remaining']:,}\n")
        lines.append("\nWEEKDAY RECORDS\n")
        for r in hof.get("weekday_records", []):
            lines.append(f"{r['weekday']:<10} {r['score_xp']:>7,} XP   {r['day']}\n")
        lines.append("\nACTIVITY RECORDS\n")
        for r in hof.get("activity_records", []):
            units = r["best_units"]
            units_txt = f"{units:.1f}" if abs(units-round(units)) > .001 else str(int(round(units)))
            lines.append(f"{r['name']}: {units_txt} units / {r['best_score_xp']:,} XP on {r['best_day']}\n")
        lines.append("\nRECORD-SETTING DAYS\n")
        lines.append(", ".join(hof.get("record_days", [])) or "none")
        lines.append("\n\nRECORD-SETTING WEEKS\n")
        lines.append(", ".join(hof.get("record_weeks", [])) or "none")
        box.insert("1.0", "".join(lines))
        box.config(state="disabled")

    def level_panel(self):
        win = tk.Toplevel(self.root)
        win.title(f"Rolling Level — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("590x650")
        lvl = game_engine.level_status()
        tk.Label(win, text=f"LV.{lvl['current_level']} {lvl['name']}", fg=FG, bg="#141418",
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        status_bits = [f"Rolling rating: {lvl['rating']:,}", f"Peak level: {lvl['peak_level']}",
                       f"Demotion floor: {lvl['demotion_floor']:,}"]
        if lvl["next_threshold"]:
            status_bits.append(f"Next threshold: {lvl['next_threshold']:,} ({lvl['xp_to_next']:,} away)")
        if lvl["at_risk"]:
            status_bits.append(f"AT RISK: {int((lvl['at_risk_seconds_remaining'] or 0)/3600)}h grace remaining")
        if lvl["comeback_active"]:
            status_bits.append(f"COMEBACK ACTIVE: {lvl['comeback_multiplier']}x level credit")
        tk.Label(win, text=" · ".join(status_bits), fg=DIM, bg="#141418",
                 font=("Segoe UI", 8), wraplength=550, justify="left").pack(anchor="w", padx=16)
        tk.Label(win, text="14-DAY DECAY COMPONENTS", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        box = tk.Text(win, wrap="none", bg=BG2, fg=FG, font=("Consolas", 9),
                      relief="flat", padx=12, pady=10)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        box.insert("end", "DAY          RAW LEVEL XP    WEIGHT     WEIGHTED\n")
        box.insert("end", "-"*55 + "\n")
        for c in lvl["components"]:
            box.insert("end", f"{c['day']}   {c['raw_level_xp']:>9,}       {c['weight']:.3f}      {c['weighted_xp']:>9,.1f}\n")
        box.config(state="disabled")

    def weekly_review_panel(self):
        win = tk.Toplevel(self.root)
        win.title(f"Weekly Closure — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("620x650")
        live = game_engine.weekly_campaign()
        last = game_engine.week_summary()
        tk.Label(win, text="WEEKLY CAMPAIGN / CLOSURE", fg=FG, bg="#141418",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(win,
                 text=(f"LIVE: {live['you']:,} XP vs {live['ghost']:,} XP  "
                       f"({'+' if live['gap']>0 else ''}{live['gap']:,}) — {live['status'].upper()}"),
                 fg="#57cc99" if live["gap"] > 0 else (RED if live["gap"] < 0 else FIRE),
                 bg="#141418", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16)
        tk.Label(win,
                 text=(f"LAST COMPLETED WEEK {last['week_start']} → {last['week_end']}: "
                       f"{last['status'].upper()} · {last['you']:,} vs {last['ghost']:,} XP · "
                       f"gap {'+' if last['gap']>0 else ''}{last['gap']:,}"),
                 fg=FG, bg="#141418", font=("Segoe UI", 9), wraplength=580,
                 justify="left").pack(anchor="w", padx=16, pady=(3, 8))
        if last.get("record_broken"):
            tk.Label(win, text="WEEKLY HIGH SCORE SET", fg="#d9b85b", bg="#141418",
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16)
        box = tk.Text(win, wrap="word", bg=BG2, fg=FG, font=("Consolas", 9),
                      relief="flat", padx=12, pady=10)
        box.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        box.insert("end", "LAST WEEK'S 7 PLAYERS\n\n")
        for p in last["players"]:
            marker = "WIN " if p["gap"] > 0 else ("LOSS" if p["gap"] < 0 else "TIE ")
            box.insert("end", (f"{p['weekday']:<9} {marker}   YOU {p['you']:>6,}   "
                               f"GHOST {p['ghost']:>6,}   GAP {'+' if p['gap']>0 else ''}{p['gap']:,}\n"))
        box.insert("end", f"\nWeekly record before that week: {last['record_before']:,} XP\n")
        box.config(state="disabled")

    def insights_panel(self):
        win = tk.Toplevel(self.root)
        win.title(f"Behavior → Score Insights — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("700x680")
        tk.Label(win, text="BEHAVIOR → USER-DEFINED OUTCOME", fg=FG, bg="#141418",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Label(win,
                 text="Scoring stays manual. This screen only asks which automatically observed behaviors are associated with the outcomes you chose to reward.",
                 fg=DIM, bg="#141418", font=("Segoe UI", 8), wraplength=650,
                 justify="left").pack(anchor="w", padx=16, pady=(0, 8))
        controls = tk.Frame(win, bg="#141418"); controls.pack(fill="x", padx=16)
        names = ["Total Score"] + [a["name"] for a in game_engine.list_activities(True)]
        target_var = tk.StringVar(value="Total Score")
        tk.Label(controls, text="Outcome:", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8)).pack(side="left")
        tk.OptionMenu(controls, target_var, *names).pack(side="left", padx=6)
        box = tk.Text(win, wrap="word", bg=BG2, fg=FG, font=("Consolas", 9),
                      relief="flat", padx=12, pady=10)
        box.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        def run():
            box.config(state="normal"); box.delete("1.0", "end")
            selected = target_var.get()
            try:
                out = game_analytics.correlations(
                    days=60, target_activity=None if selected == "Total Score" else selected)
            except Exception as ex:
                box.insert("end", f"Analytics error: {ex}")
                box.config(state="disabled")
                return
            box.insert("end", f"Target: {out['target']}\n")
            box.insert("end", f"Tracked/scored days: {out['tracked_days']}  | minimum: {out['minimum_days']}\n")
            box.insert("end", "Association only — not proof of causation.\n\n")
            if not out["ready"]:
                box.insert("end", "Not enough history yet. Seed Synthetic Demo History from Menu if you want to exercise this screen immediately.\n")
            elif not out["correlations"]:
                box.insert("end", "Enough history exists, but no varying metric can be ranked against this outcome yet.\n")
            else:
                for i, r in enumerate(out["correlations"], 1):
                    box.insert("end", (f"{i}. {r['label']}\n"
                                       f"   {r['association']}\n"
                                       f"   strength={r['strength']}  Spearman r={r['spearman_r']:+.3f}  n={r['sample_days']} days\n\n"))
            box.config(state="disabled")
        tk.Button(controls, text="Run Analysis", command=run, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 8), cursor="hand2").pack(side="left")
        run()

    def demo_data_panel(self):
        import demo_data
        win = tk.Toplevel(self.root)
        win.title(f"Synthetic Demo History — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("520x350")
        tk.Label(win, text="SYNTHETIC HISTORY", fg=FG, bg="#141418",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=16, pady=(14, 3))
        tk.Label(win,
                 text=("Creates ~28 days of timestamped XP events plus isolated demo analytics features so Ghost, records, levels, weekly closure, Calendar and Insights can all be tested now. Demo XP is tagged synthetic_demo; Clear removes only that fixture and leaves real XP/telemetry/notes/videos alone."),
                 fg=DIM, bg="#141418", font=("Segoe UI", 8), wraplength=480,
                 justify="left").pack(anchor="w", padx=16)
        status = tk.Label(win, text="", fg=FG, bg="#141418",
                          font=("Segoe UI", 9), justify="left")
        status.pack(anchor="w", padx=16, pady=(12, 8))
        buttons = tk.Frame(win, bg="#141418"); buttons.pack(fill="x", padx=16)

        def refresh_status(extra=""):
            st = demo_data.status()
            status.config(text=(f"Demo active: {'YES' if st['active'] else 'NO'}\n"
                                f"Demo days: {st['days']}  |  synthetic XP events: {st['events']}"
                                + (f"\n{extra}" if extra else "")))

        def seeded(result):
            if isinstance(result, str):
                refresh_status(result)
            else:
                refresh_status(f"Seed complete. Highest fixture day: {result.get('highest_day', 0):,} XP")
            self.refresh_static()

        def cleared(result):
            refresh_status(f"Cleared {result.get('removed_events', 0) if isinstance(result, dict) else 0} synthetic XP events.")
            self.refresh_static()

        tk.Button(buttons, text="Seed / Reset 28-Day Demo",
                  command=lambda: run_bg(lambda: demo_data.seed(28), seeded, self.root),
                  bg="#253a31", fg=FG, relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2").pack(fill="x", pady=3)
        tk.Button(buttons, text="Clear Synthetic Demo",
                  command=lambda: run_bg(demo_data.clear, cleared, self.root),
                  bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 9),
                  cursor="hand2").pack(fill="x", pady=3)
        refresh_status()

    def backend_snapshot_panel(self):
        win = tk.Toplevel(self.root)
        win.title(f"Raw Backend Snapshot — {BUILD_TAG}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("760x720")
        tk.Label(win, text="CANONICAL GAME ENGINE SNAPSHOT", fg=FG, bg="#141418",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        box = tk.Text(win, wrap="none", bg="#0d0d10", fg=FG,
                      font=("Consolas", 8), relief="flat", padx=10, pady=10)
        box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        payload = {
            "dashboard_snapshot": game_engine.dashboard_snapshot(),
            "analytics": game_analytics.correlations(days=60),
        }
        box.insert("1.0", _json.dumps(payload, indent=2, default=str))
        box.config(state="disabled")

    def xp_history(self):
        win = tk.Toplevel(self.root)
        win.title("XP History")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("420x500")

        # daily challenge at top
        ch = progression.get_daily_challenge()
        if ch:
            ch_frame = tk.Frame(win, bg="#1d2530")
            ch_frame.pack(fill="x", padx=10, pady=(10, 4))
            tk.Label(ch_frame, text="DAILY CHALLENGE", fg=FIRE, bg="#1d2530",
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=8, pady=(4, 0))
            tk.Label(ch_frame, text=f"{ch['text']}  (+{ch['xp']} XP)",
                     fg=FG, bg="#1d2530", font=("Segoe UI", 9)).pack(
                         anchor="w", padx=8, pady=(0, 4))

        # stats summary
        stats = progression.get_stats()
        tk.Label(win, text=f"Today: {stats.get('daily_xp', 0)} XP | "
                           f"Record: {stats.get('daily_record', 0)} XP | "
                           f"Multiplier: {stats['multiplier']}x",
                 fg=FG, bg="#141418", font=("Segoe UI", 9)).pack(pady=(8, 2))

        # needs
        needs = stats.get("needs", {})
        if needs:
            n_frame = tk.Frame(win, bg="#141418")
            n_frame.pack(fill="x", padx=16, pady=4)
            for need, val in needs.items():
                color = "#57cc99" if val >= 70 else (FIRE if val >= 40 else RED)
                tk.Label(n_frame, text=f"{need}: {val}%", fg=color,
                         bg="#141418", font=("Segoe UI", 8)).pack(
                             side="left", padx=6)

        # achievements
        achs = stats.get("achievements", [])
        if achs:
            tk.Label(win, text=f"Achievements: {len(achs)}/{len(ACHIEVEMENTS)}",
                     fg=DIM, bg="#141418", font=("Segoe UI", 8)).pack(pady=(4, 0))

        # history log
        tk.Label(win, text="HISTORY", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                     pady=(8, 2))
        box = tk.Text(win, wrap="word", bg="#0e0e12", fg=FG,
                      padx=10, pady=8, font=("Segoe UI", 8), relief="flat")
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        history = progression.get_history(100)
        for entry in history:
            xp = entry["xp"]
            color_tag = "gain" if xp > 0 else "loss"
            sign = "+" if xp > 0 else ""
            box.insert("end", f"{entry['ts']}  {sign}{xp} XP  {entry['reason']}\n")
        box.config(state="disabled")

    def habits_panel(self):
        stacks = habits.get_today()
        win = tk.Toplevel(self.root)
        win.title("Habits")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("360x400")

        for stack_name, items in stacks.items():
            tk.Label(win, text=stack_name.upper(), fg=DIM, bg="#141418",
                     font=("Segoe UI", 8, "bold")).pack(anchor="w",
                                                         padx=16, pady=(10, 4))
            for i, habit in enumerate(items):
                row = tk.Frame(win, bg="#141418")
                row.pack(fill="x", padx=16)
                var = tk.IntVar(value=1 if habit["done"] else 0)
                def toggle(sn=stack_name, idx=i):
                    habits.toggle(sn, idx)
                    pct = habits.completion_rate()
                    notif = ""
                    if pct >= 100:
                        notif = progression.award_xp("morning_habits") or ""
                    self.convo_add("Witness",
                                  f"Habit checked. {int(pct)}% done. {notif}",
                                  speak_it=False)
                cb = tk.Checkbutton(row, text=habit["name"], variable=var,
                                    command=toggle, fg=FG, bg="#141418",
                                    activebackground="#141418",
                                    selectcolor=BG3, font=("Segoe UI", 9))
                cb.pack(anchor="w")

    def pipeline_panel(self):
        p = pipeline.get_pipeline()
        win = tk.Toplevel(self.root)
        win.title("Revenue Pipeline")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("400x380")
        tk.Label(win, text="PIPELINE", fg=DIM, bg="#141418",
                 font=("Segoe UI", 9, "bold")).pack(pady=(10, 6))
        entries = {}
        stages = ["total_leads", "contacted", "quoted", "booked",
                  "completed", "paid"]
        for stage in stages:
            row = tk.Frame(win, bg="#141418")
            row.pack(fill="x", padx=20, pady=3)
            label = stage.replace("_", " ").title()
            tk.Label(row, text=label, fg=FG, bg="#141418",
                     font=("Segoe UI", 9), width=14, anchor="w").pack(side="left")
            e = tk.Entry(row, width=8, bg=BG3, fg=FG, insertbackground=FG,
                         font=("Segoe UI", 9), relief="flat")
            e.insert(0, str(p["stats"].get(stage, 0)))
            e.pack(side="left", padx=4)
            entries[stage] = e

        # show conversion rates
        rates = pipeline.get_conversion_rates()
        if rates:
            tk.Label(win, text="Conversion Rates", fg=DIM, bg="#141418",
                     font=("Segoe UI", 8)).pack(pady=(10, 2))
            for k, v in rates.items():
                tk.Label(win, text=f"{k.replace('_', ' ').title()}: {v}%",
                         fg=FG, bg="#141418", font=("Segoe UI", 9)).pack()

        def save():
            for stage, entry in entries.items():
                try:
                    pipeline.update_stats(stage, int(entry.get() or 0))
                except ValueError:
                    pass
            self.convo_add("Witness", "Pipeline updated.", speak_it=False)
            win.destroy()
        tk.Button(win, text="Save", command=save, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  width=12).pack(pady=10)

    def show_projection(self):
        p = finance.project()
        win = tk.Toplevel(self.root)
        win.title("Financial Projection")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("480x400")
        box = tk.Text(win, wrap="word", bg="#0e0e12", fg=FG, padx=14,
                      pady=14, font=("Segoe UI", 9), relief="flat")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        text = (f"FINANCIAL PROJECTION\n{'=' * 35}\n\n"
                f"Current: ${p['current']}/mo\n"
                f"Target:  ${p['target']}/mo\n"
                f"Gap:     ${p['gap']}/mo\n"
                f"Trend:   {p.get('trend', '?')}\n\n")
        if p.get("productive_hours_mo"):
            text += f"Productive hours/mo: ~{p['productive_hours_mo']}\n"
        if p.get("rev_per_hour"):
            text += f"Revenue per hour: ${p['rev_per_hour']}\n"
        text += f"\nSCENARIOS\n{'-' * 35}\n"
        for s in p.get("scenarios", []):
            text += f"\n{s['name']}:\n  {s.get('note', '')}\n"
        if p.get("deadline"):
            text += f"\nDeadline: {p['deadline']}\n"
        box.insert("1.0", text)
        box.config(state="disabled")

    def voice_journal(self):
        self.convo_add("Witness", "Voice journal — talk for up to 90 seconds. "
                       "Recording starts now...", speak_it=True)
        def record():
            text = journal.record_and_transcribe(90)
            path = journal.save_journal(text)
            return text, path
        def got(result):
            text, path = result
            self.convo_add("Witness",
                           f"Captured. Saved to {path}.", speak_it=False)
            notif = progression.award_xp("voice_journal")
            if notif:
                self.convo_add("Witness", notif, speak_it=False)
            # feed it to brain for response
            self.convo_add("You", f"[Voice journal]: {text}", speak_it=False)
            self._brain_respond(event=f"User recorded voice journal: {text[:200]}")
        run_bg(record, got, self.root)

    def reset_chat(self):
        import brain as brain_mod
        brain_mod.reset_conversation()
        self.convo_history = []
        self.convo_add("Witness", "Fresh start. What are we working on?")

    def nuclear_response(self, proc, title):
        # HARD WHITELIST — these NEVER trigger nuclear no matter what
        safe_check = f"{proc} {title}".lower()
        NEVER_NUCLEAR = [
            "google drive", "google docs", "google sheets", "gmail",
            "booking koala", "vonage", "thumbtack", "calendar",
            "github", "stackoverflow", "claude", "anthropic",
            "microsoft", "office", "outlook", "word", "excel",
            "witness", "spotify", "pandora", "apple music",
            "amazon", "ebay", "walmart", "linkedin",
            "slack", "zoom", "teams", "discord", "whatsapp",
            "wikipedia", "maps", "weather", "bank", "chase",
            "paypal", "stripe", "shopify", "canva",
            "gohighlevel", "highlevel", "youtube music",
            "file explorer", "notepad", "task manager",
        ]
        if any(safe in safe_check for safe in NEVER_NUCLEAR):
            # false trigger on a safe site — log and ignore
            self.convo_add("Witness",
                           f"(Blocked false trigger on: {title[:40]})",
                           speak_it=False)
            return

        # log what triggered this so user can see
        self.convo_add("Witness",
                       f"Nuclear triggered by: {proc} - {title[:60]}",
                       speak_it=False)
        try:
            trail.record_incident()
        except Exception:
            pass
        progression.apply_penalty("redline_event")
        """Full nuclear red-line response. No half measures."""
        self.popup_open = True

        # 1. IMMEDIATELY kill browsers
        killed = nuclear.kill_browsers()
        kill_msg = f"Browser killed." if killed else ""

        # 2. Block sites for 2 hours
        blocker.block_sites(duration_min=120)

        # 3. Log it
        db.log_redline(title[:80])
        nuclear.log_intervention("browser_kill", False)

        # 4. Send accountability alert in background
        def send_alert():
            try:
                import export
                if export.is_configured():
                    nuclear.send_accountability_alert()
                    self.root.after(0, lambda: self.convo_add(
                        "Witness",
                        "Your accountability partner was notified.",
                        speak_it=False))
            except Exception:
                pass
        threading.Thread(target=send_alert, daemon=True).start()

        # 5. First message + AI line
        self.convo_add("Witness",
                       f"{kill_msg} Sites blocked for 2 hours. "
                       "This is the moment, not later — right now.",
                       speak_it=True)

        # 6. Webcam mirror
        frame = nuclear.capture_webcam_frame(state)

        # 7. Build the intervention window
        win = tk.Toplevel(self.root)
        win.title("WITNESS — RED LINE")
        win.attributes("-topmost", True)
        win.configure(bg="#1a0000")
        win.geometry("500x550")
        # prevent closing
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        win.grab_set()

        # mirror image
        if frame is not None:
            try:
                import cv2
                from PIL import Image, ImageTk
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_rgb = cv2.resize(frame_rgb, (200, 150))
                img = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(img)
                mirror = tk.Label(win, image=photo, bg="#1a0000")
                mirror.image = photo
                mirror.pack(pady=(12, 4))
                tk.Label(win, text="This is you right now.",
                         fg="#c74b50", bg="#1a0000",
                         font=("Segoe UI", 10, "bold")).pack()
                tk.Label(win, text="Is this who you're becoming?",
                         fg="#d4d4d8", bg="#1a0000",
                         font=("Segoe UI", 10)).pack(pady=(0, 8))
            except ImportError:
                tk.Label(win, text="Look at yourself right now.",
                         fg="#c74b50", bg="#1a0000",
                         font=("Segoe UI", 12, "bold")).pack(pady=(20, 8))
        else:
            tk.Label(win, text="STOP.", fg="#c74b50", bg="#1a0000",
                     font=("Segoe UI", 16, "bold")).pack(pady=(20, 8))

        # escalation state
        esc = {"stage": 0, "video_idx": 0}

        # get SOS videos
        sos_videos = []
        if os.path.isdir(config.SOS_VIDEO_DIR):
            sos_videos = sorted([
                os.path.join(config.SOS_VIDEO_DIR, f)
                for f in os.listdir(config.SOS_VIDEO_DIR)
                if f.lower().endswith((".mp4", ".mov", ".mkv",
                                      ".webm", ".avi"))])

        msg_label = tk.Label(win, text="", fg="#d4d4d8", bg="#1a0000",
                             wraplength=440, font=("Segoe UI", 10),
                             justify="center")
        msg_label.pack(pady=8)

        redirect_label = tk.Label(win, text="", fg="#d4943a", bg="#1a0000",
                                  wraplength=440, font=("Segoe UI", 11, "bold"),
                                  justify="center")
        redirect_label.pack(pady=4)

        btn_frame = tk.Frame(win, bg="#1a0000")
        btn_frame.pack(pady=8)

        def play_video():
            if esc["video_idx"] < len(sos_videos):
                try:
                    os.startfile(os.path.abspath(
                        sos_videos[esc["video_idx"]]))
                except Exception:
                    pass
                esc["video_idx"] += 1

        def escalate():
            stage = esc["stage"]
            esc["stage"] += 1

            # play next video if available
            if stage < len(sos_videos):
                play_video()

            # get redirect
            redirect = nuclear.get_redirect(stage)
            redirect_label.config(text=redirect)

            # AI message based on stage
            if stage == 0:
                run_bg(lambda: ai.sos_line("open"),
                       lambda t: (msg_label.config(text=t),
                                  voice.speak_voice_only(t)), self.root)
            elif stage == 1:
                run_bg(lambda: ai.sos_line("after_video"),
                       lambda t: (msg_label.config(text=t),
                                  voice.speak_voice_only(t)), self.root)
            else:
                msg = (f"Attempt {stage + 1}. The sites are blocked. "
                       f"Your partner was notified. "
                       f"{redirect}")
                msg_label.config(text=msg)
                voice.speak_voice_only(redirect)

            nuclear.log_intervention(f"stage_{stage}",
                                     False if stage > 0 else False)

        def walked_away():
            """User chose to walk away — this is the win."""
            nuclear.log_intervention("walked_away", True)
            db.log_sos("red-line nuclear response", "walked away — won")
            data.add_win("Fought through a red-line moment and walked away.")
            progression.award_xp("sos_survived")
            self.convo_add("Witness",
                           "You walked away. That's the hardest rep and "
                           "you just did it. Logged as a win.",
                           speak_it=True)
            self.popup_open = False
            win.grab_release()
            win.destroy()

        tk.Button(btn_frame, text="I'm fighting it — show me more",
                  command=escalate, bg="#2a1a1a", fg="#d4d4d8",
                  relief="flat", font=("Segoe UI", 9),
                  cursor="hand2").pack(side="left", padx=4)
        tk.Button(btn_frame, text="I'm walking away",
                  command=walked_away, bg="#1d3520", fg="#d4d4d8",
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2").pack(side="left", padx=4)

        # start first escalation
        escalate()

        # if they try to close, escalate instead
        close_attempts = {"n": 0}
        def on_close():
            close_attempts["n"] += 1
            if close_attempts["n"] >= 5:
                voice.speak_voice_only(
                    "You've tried to close this 5 times. "
                    "The sites are blocked. Walk away from the computer.")
            else:
                escalate()
        win.protocol("WM_DELETE_WINDOW", on_close)

    def show_insights(self):
        win = tk.Toplevel(self.root)
        win.title("Insights — Correlations")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("500x400")
        tk.Label(win, text="YOUR PATTERNS", fg=DIM, bg="#141418",
                 font=("Segoe UI", 9, "bold")).pack(pady=(10, 6))
        box = tk.Text(win, wrap="word", bg="#0e0e12", fg=FG,
                      padx=12, pady=12, font=("Segoe UI", 9),
                      relief="flat")
        box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        box.insert("1.0", "Analyzing your data...\n")

        target, phase, days = get_target()
        def got(insights):
            box.delete("1.0", "end")
            box.insert("1.0", f"Day {days} — {phase}\n"
                               f"Current target: {target}%\n\n")
            for i, insight in enumerate(insights, 1):
                box.insert("end", f"{i}. {insight}\n\n")
            # add trail pattern info
            trail_info = trail.get_pattern_summary()
            box.insert("end", f"\nDrift Trail:\n{trail_info}\n")

            # add statistical model findings
            try:
                se = stats_engine.get_engine()
                stats_summary = se.summary_for_brain()
                if stats_summary:
                    box.insert("end", f"\n{stats_summary}\n")
            except Exception:
                pass
            box.config(state="disabled")
        run_bg(correlations.analyze, got, self.root)

    def show_strategy(self):
        self.convo_add("Witness", "Running deep strategic analysis — "
                       "this reads all your data...", speak_it=True)

        def got(result):
            if isinstance(result, str):
                result = {"analysis": result, "spoken": ""}

            win = tk.Toplevel(self.root)
            win.title("WITNESS — Life Strategy")
            win.configure(bg="#141418")
            win.geometry("600x550")

            box = tk.Text(win, wrap="word", bg="#0e0e12", fg=FG,
                          padx=14, pady=14, font=("Segoe UI", 9),
                          relief="flat")
            box.pack(fill="both", expand=True, padx=10, pady=10)

            # format the strategy
            text = ""
            if result.get("analysis"):
                text += "STRATEGIC ANALYSIS\n" + "=" * 40 + "\n\n"
                text += result["analysis"] + "\n\n"

            if result.get("one_thing"):
                text += "THE ONE THING THIS WEEK\n" + "-" * 30 + "\n"
                text += result["one_thing"] + "\n\n"

            if result.get("habits_to_add"):
                text += "ADD THESE HABITS\n" + "-" * 30 + "\n"
                for h in result["habits_to_add"]:
                    text += f"  + {h}\n"
                text += "\n"

            if result.get("habits_to_remove"):
                text += "REMOVE THESE PATTERNS\n" + "-" * 30 + "\n"
                for h in result["habits_to_remove"]:
                    text += f"  - {h}\n"
                text += "\n"

            if result.get("milestones"):
                text += "MILESTONES (next 4 weeks)\n" + "-" * 30 + "\n"
                for m in result["milestones"]:
                    text += (f"  Week {m.get('week', '?')}: "
                             f"{m.get('target', '')} "
                             f"[{m.get('metric', '')}]\n")
                text += "\n"

            if result.get("optimal_schedule"):
                text += "OPTIMIZED SCHEDULE\n" + "-" * 30 + "\n"
                for blk in result["optimal_schedule"]:
                    text += (f"  {blk['start']} - {blk['end']}  "
                             f"{blk['label']}\n")
                self.refresh_static()

            box.insert("1.0", text)
            box.config(state="disabled")

            if result.get("spoken"):
                voice.speak_voice_only(result["spoken"])

        run_bg(strategist.generate_strategy, got, self.root)

    def weekly_review(self):
        self.convo_add("Witness", "Running weekly review — this takes "
                       "a moment...", speak_it=True)
        def got(j):
            if isinstance(j, str):
                j = {"review": j, "spoken": "", "schedule": data.load()["schedule"]}
            path = weekly.save_review(j)
            # update schedule
            if j.get("schedule"):
                d = data.load()
                d["schedule"] = j["schedule"]
                data.save(d)
                self.refresh_static()
            # show review
            win = tk.Toplevel(self.root)
            win.title("Weekly Review")
            win.configure(bg="#141418")
            win.geometry("560x500")
            box = tk.Text(win, wrap="word", bg="#0e0e12", fg=FG,
                          padx=14, pady=14, font=("Segoe UI", 9),
                          relief="flat")
            box.pack(fill="both", expand=True, padx=10, pady=10)
            box.insert("1.0", j.get("review", "(no review)"))
            box.insert("end", f"\n\n(saved to {path})")
            box.config(state="disabled")
            if j.get("spoken"):
                voice.speak_voice_only(j["spoken"])
            # auto-export if configured
            if export.is_configured():
                ok, msg = export.send_weekly(j.get("review", ""))
                if ok:
                    self.convo_add("Witness",
                                  f"Weekly review sent to your "
                                  f"accountability partner.", speak_it=False)
        run_bg(weekly.generate, got, self.root)

    def toggle_block(self):
        blocked, remaining = blocker.is_blocked()
        if blocked:
            self.convo_add("Witness",
                           f"Sites blocked for {remaining} more minutes. "
                           "Can't override — you set it up this way.",
                           speak_it=True)
            return
        ok, msg = blocker.block_sites(duration_min=120)
        if ok:
            self.convo_add("Witness", f"{msg} No undo for 2 hours.",
                           speak_it=True)
            self.block_btn.config(text="🔒 120m")
        else:
            self.convo_add("Witness", msg, speak_it=True)

    def edit_core(self):
        d = data.load()
        win = tk.Toplevel(self.root)
        win.title("Lifestyle & Mission")
        win.attributes("-topmost", True)
        win.configure(bg="#17171d"); win.geometry("480x300")
        tk.Label(win, text="Dream lifestyle:", fg=DIM, bg="#17171d").pack()
        t1 = tk.Text(win, height=3, width=54, bg="#0d0d0f", fg=FG,
                     insertbackground=FG)
        t1.insert("1.0", d["lifestyle"]); t1.pack(pady=4)
        tk.Label(win, text="Current mission:", fg=DIM, bg="#17171d").pack()
        t2 = tk.Text(win, height=3, width=54, bg="#0d0d0f", fg=FG,
                     insertbackground=FG)
        t2.insert("1.0", d["mission"]); t2.pack(pady=4)

        def save():
            d["lifestyle"] = t1.get("1.0", "end").strip()
            d["mission"] = t2.get("1.0", "end").strip()
            data.save(d); self.refresh_static(); win.destroy()
        tk.Button(win, text="Save", command=save, bg="#2c2c36", fg=FG,
                  relief="flat", width=12).pack(pady=6)

    # ── manual Activities ────────────────────────────────────────────────
    def activities_window(self):
        """Plain-text Activity editor backed by shared/game_engine.py.

        R = repeatable one-tap counter, D = once per day, T = timed with the
        configured XP interpreted per hour. ``XP | Activity`` remains accepted
        as shorthand for a repeatable activity, preserving the v7.41 format.
        """
        win = tk.Toplevel(self.root)
        win.title(f"Activities / Scoring (build {BUILD_TAG})")
        win.attributes("-topmost", True)
        win.configure(bg="#17171d")
        win.geometry("520x430")
        tk.Label(win, text="TYPE | XP | ACTIVITY",
                 fg=FG, bg="#17171d", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        tk.Label(win, text="R = repeatable   D = once/day   T = timed (XP per hour)",
                 fg=DIM, bg="#17171d", font=("Segoe UI", 8)).pack()
        tk.Label(win, text="Examples:  R | 10 | Cold calls     D | 150 | Workout     T | 100 | Focus",
                 fg=DIM, bg="#17171d", font=("Consolas", 8)).pack(pady=(1, 5))
        box = tk.Text(win, height=14, width=61, bg="#0d0d0f", fg=FG,
                      insertbackground=FG)
        box.pack(pady=4)
        aliases = {"repeatable": "R", "once_daily": "D", "timed": "T"}
        try:
            existing = game_engine.list_activities(True)
        except Exception:
            existing = []
        for a in existing:
            box.insert("end", f"{aliases.get(a['kind'], 'R')} | {a['xp_value']} | {a['name']}\n")
        win.after(200, lambda: (win.focus_force(), box.focus_force()))

        def parse_lines(text):
            items = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = [x.strip() for x in line.split("|")]
                if len(parts) >= 3:
                    kind_raw, xp_raw = parts[0], parts[1]
                    activity = "|".join(parts[2:]).strip()
                elif len(parts) == 2:
                    # v7.41 shorthand: XP | Activity
                    kind_raw, xp_raw, activity = "R", parts[0], parts[1]
                else:
                    kind_raw, xp_raw, activity = "R", "10", parts[0]
                try:
                    kind = game_engine.normalize_kind(kind_raw)
                except ValueError:
                    kind = "repeatable"
                try:
                    xp = max(0, int(xp_raw))
                except ValueError:
                    xp = 10
                if activity:
                    items.append({"name": activity, "xp_value": xp, "kind": kind})
            return items

        def save_activities():
            try:
                items = parse_lines(box.get("1.0", "end"))
                saved = game_engine.sync_activity_roster(items)
                self.refresh_tasks()
                self.convo_add(
                    "Witness",
                    f"Activities saved: {len(saved)}. Scoring ledger is live.",
                    speak_it=False)
                win.destroy()
            except Exception as ex:
                self.convo_add("Witness", f"ACTIVITY SAVE ERROR: {ex}", speak_it=False)

        tk.Button(win, text="Save Activities", command=save_activities,
                  bg="#2c2c36", fg=FG, relief="flat", width=16).pack(pady=8)

    def offtask_tick(self):
        try:
            tasks = data.get_tasks()
            open_tasks = [t for t in tasks if not t["done"]]
            busy = (self.popup_open or not state.get("present")
                    or state["deep_work_until"] > time.time())
            if open_tasks and not busy:
                title = state["current_title"]
                app = state["current_app"]

                def got(res):
                    if res is False and not self.popup_open:
                        self.show_checkin("offtask", app, title)
                run_bg(lambda: ai.is_on_task(title, app, tasks), got,
                       self.root)
        finally:
            self.root.after(10 * 60 * 1000, self.offtask_tick)

    # ── chat ────────────────────────────────────────────────────────────
    def chat_window(self):
        """Toggle an embedded chat panel inside the dashboard (no separate
        window = no focus problems)."""
        if getattr(self, "chat_frame", None) and self.chat_frame.winfo_exists():
            self.chat_frame.destroy()
            self.root.geometry("380x580")
            return
        self.root.geometry("380x840")
        self.chat_frame = tk.Frame(self.root, bg=BG)
        self.chat_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        log = tk.Text(self.chat_frame, wrap="word", bg="#0d0d0f", fg=FG,
                      state="disabled", height=10, padx=8, pady=8,
                      font=("Arial", 9))
        log.pack(fill="both", expand=True)
        row = tk.Frame(self.chat_frame, bg=BG); row.pack(fill="x", pady=4)
        entry = tk.Entry(row, bg="#0d0d0f", fg=FG, insertbackground=FG,
                         font=("Arial", 10))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        entry.focus_set()
        history = []

        def append(who, text):
            log.config(state="normal")
            log.insert("end", f"{who}: {text}\n\n")
            log.config(state="disabled"); log.see("end")

        def send(_=None):
            t = entry.get().strip()
            if not t:
                return
            entry.delete(0, "end")
            append("You", t)
            history.append({"role": "user", "content": t})

            def got(reply):
                shown = reply.split("UPDATE:")[0].strip()
                append("Witness", shown)
                voice.speak_voice_only(shown)
                history.append({"role": "assistant", "content": reply})
                if "UPDATE:" in reply:
                    try:
                        import json as _j
                        upd = _j.loads(reply.split("UPDATE:", 1)[1].strip())
                        d = data.load()
                        for k in ("lifestyle", "mission"):
                            if k in upd:
                                d[k] = upd[k]
                        if "goals" in upd and isinstance(upd["goals"], list):
                            d["goals"] = upd["goals"]
                        data.save(d); self.refresh_static()
                        append("Witness", "(goals updated)")
                    except Exception:
                        pass
            run_bg(lambda: ai.chat(list(history)), got, self.root)
        entry.bind("<Return>", send)
        tk.Button(row, text="Send", command=send, bg="#2c2c36", fg=FG,
                  relief="flat", width=7).pack(side="left", padx=2)
        mic_btn = tk.Button(row, text="\U0001F3A4", bg="#2c2c36", fg=FG,
                            relief="flat", width=4)

        def do_mic():
            mic_btn.config(text="...", state="disabled")
            import mic as mic_mod

            def got(text):
                mic_btn.config(text="\U0001F3A4", state="normal")
                if text:
                    entry.delete(0, "end"); entry.insert(0, text)
                    entry.focus_set()
            run_bg(lambda: mic_mod.listen(), got, self.root)
        mic_btn.config(command=do_mic)
        mic_btn.pack(side="left", padx=2)
        append("Witness", "Here. What's on your mind?")

    # ── recap ───────────────────────────────────────────────────────────
    def goal_progress_panel(self):
        """Three-lane revenue completion projection (harsh/light/
        blended -- switch with the buttons) plus the efficiency trend
        and runway against the primary goal's target_date, if set.
        Pure Python (insight/projection.py), no AI in any calculation."""
        win = tk.Toplevel(self.root)
        win.title(f"Goal Progress (build {BUILD_TAG})")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("340x500")

        try:
            gp = insight_projection.goal_projection()
        except Exception as e:
            gp = {"note": f"Couldn't compute yet: {e}"}

        tk.Label(win, text="GOAL", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                     pady=(14, 2))
        tk.Label(win, text=gp.get("goal") or "(no goal set)", fg=FG,
                 bg="#141418", font=("Segoe UI", 10), wraplength=300,
                 justify="left", anchor="w").pack(anchor="w", padx=16)

        tk.Label(win, text="PROJECTED COMPLETION", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                     pady=(14, 2))

        lane_row = tk.Frame(win, bg="#141418")
        lane_row.pack(anchor="w", padx=16, pady=(0, 4))

        completion_lbl = tk.Label(win, text="", fg=FG, bg="#141418",
                                  font=("Segoe UI", 11), wraplength=300,
                                  justify="left", anchor="w")
        completion_lbl.pack(anchor="w", padx=16)
        detail_lbl = tk.Label(win, text="", fg=DIM, bg="#141418",
                              font=("Segoe UI", 8), wraplength=300,
                              justify="left", anchor="w")
        detail_lbl.pack(anchor="w", padx=16, pady=(2, 0))

        lane_fns = {
            "Blended": insight_projection.blended_completion_projection,
            "Harsh": insight_projection.harsh_completion_projection,
            "Light": insight_projection.light_completion_projection,
        }
        lane_buttons = {}

        def show_lane(name):
            for n, b in lane_buttons.items():
                b.config(bg=(BG3 if n == name else BG2),
                        fg=(FG if n == name else DIM))
            try:
                r = lane_fns[name]()
            except Exception as e:
                r = {"note": f"Couldn't compute: {e}"}
            completion_lbl.config(text=r.get("note", ""))
            if r.get("confidence"):
                detail_lbl.config(
                    text=f"Based on {r.get('evidence_count', 0)} logged "
                         f"sale(s), confidence: {r['confidence']}. Current "
                         f"rate: ${r.get('current_rate', 0):.0f}/mo.")
            elif "harsh_date" in r:
                detail_lbl.config(
                    text=f"Average of harsh ({r['harsh_date']}) and light "
                         f"({r['light_date']}).")
            else:
                detail_lbl.config(text="")

        for name in lane_fns:
            b = tk.Button(lane_row, text=name, bg=BG2, fg=DIM,
                         relief="flat", font=("Segoe UI", 8), cursor="hand2",
                         width=8, command=lambda n=name: show_lane(n))
            b.pack(side="left", padx=(0, 4))
            lane_buttons[name] = b

        show_lane("Blended")

        btn_row2 = tk.Frame(win, bg="#141418")
        btn_row2.pack(anchor="w", padx=16, pady=(6, 0))
        tk.Button(btn_row2, text="View Graph", command=self.goal_graph_panel,
                 bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                 cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(btn_row2, text="Debug Light Calc",
                 command=self.light_debug_panel,
                 bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                 cursor="hand2").pack(side="left")

        trend = gp.get("trend")
        if trend:
            tk.Label(win, text="EFFICIENCY TREND", fg=DIM, bg="#141418",
                     font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                         pady=(14, 2))
            tk.Label(win,
                     text=f"Last 7 days: {trend['avg_last_7']}%   "
                          f"All-time: {trend['avg_all_time']}%   "
                          f"Trend: {trend['trend']}",
                     fg=FG, bg="#141418", font=("Segoe UI", 9),
                     wraplength=300, justify="left",
                     anchor="w").pack(anchor="w", padx=16)

        tk.Label(win, text="NOTE", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                     pady=(14, 2))
        tk.Label(win, text=gp.get("note", ""), fg=FG, bg="#141418",
                 font=("Segoe UI", 9), wraplength=300, justify="left",
                 anchor="w").pack(anchor="w", padx=16, pady=(0, 12))

        tk.Label(win, text="STRIPE", fg=DIM, bg="#141418",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=16,
                                                     pady=(4, 2))
        stripe_status = tk.Label(win, text="", fg=FG, bg="#141418",
                                 font=("Segoe UI", 9), wraplength=300,
                                 justify="left", anchor="w")
        stripe_status.pack(anchor="w", padx=16)

        def refresh_stripe_status():
            import stripe_sync
            if not stripe_sync.is_configured():
                stripe_status.config(
                    text="Not connected. Set STRIPE_API_KEY (a read-only "
                         "restricted key) as a Windows environment "
                         "variable and restart WITNESS -- see "
                         "shared/stripe_sync.py for exact steps.")
            else:
                stripe_status.config(text="Connected. Syncing automatically "
                                          "every 15 minutes.")

        def sync_now():
            stripe_status.config(text="Syncing...")

            def do_sync():
                import stripe_sync
                return stripe_sync.sync()

            def done(result):
                if isinstance(result, dict) and result.get("error") is None:
                    stripe_status.config(
                        text=f"Synced {result['synced']} new payment(s) "
                             f"({result['already_had']} already had). "
                             "Connected, syncing automatically every 15 "
                             "minutes.")
                elif isinstance(result, dict):
                    stripe_status.config(text=f"Sync error: {result['error']}")
                else:
                    stripe_status.config(text=str(result))

            run_bg(do_sync, done, self.root)

        refresh_stripe_status()
        tk.Button(win, text="Sync Now", command=sync_now, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 8), cursor="hand2"
                  ).pack(anchor="w", padx=16, pady=(4, 12))

    def light_debug_panel(self):
        """Shows insight_projection.light_debug_info() as plain,
        copyable text -- exactly what the Light lane calculation is
        seeing (the actual sequence, which points it fit a trend
        through, the resulting slope). Built specifically so a result
        that looks wrong can be diagnosed from real numbers -- easy to
        screenshot and send back."""
        win = tk.Toplevel(self.root)
        win.title(f"Debug: Light Lane Calc (build {BUILD_TAG})")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("420x480")

        text = tk.Text(win, wrap="word", bg=BG2, fg=FG, font=("Consolas", 9),
                       relief="flat", padx=10, pady=10)
        text.pack(fill="both", expand=True, padx=12, pady=12)

        try:
            info = insight_projection.light_debug_info()
        except Exception as e:
            info = {"error": f"{type(e).__name__}: {e}"}

        lines_out = []
        lines_out.append(f"sequence_len: {info.get('sequence_len')}")
        lines_out.append(f"window_days_used: {info.get('window_days_used')}")
        lines_out.append(f"fit_points_count: {info.get('fit_points_count')}")
        lines_out.append(f"slope: {info.get('slope')}")
        lines_out.append(f"intercept: {info.get('intercept')}")
        lines_out.append(f"slope_positive: {info.get('slope_positive')}")
        if info.get("note"):
            lines_out.append(f"note: {info['note']}")
        if info.get("error"):
            lines_out.append(f"error: {info['error']}")
        lines_out.append("")
        lines_out.append("--- IMPORTANT: two different numbers below ---")
        lines_out.append("'$/mo equiv' = monthly-EQUIVALENT: today's daily")
        lines_out.append("pace projected out to a full month. NOT a real")
        lines_out.append("payment size. This is what the target line and")
        lines_out.append("the trend fit both use, since the goal is a")
        lines_out.append("monthly figure.")
        lines_out.append("'raw $' = the actual dollar amount received that")
        lines_out.append("day. This is the real number.")
        lines_out.append("")
        lines_out.append("fit_points (day, $/mo equiv) -- what the")
        lines_out.append("trend line was actually fit through:")
        for pt in info.get("fit_points", []):
            lines_out.append(f"  {pt}")
        lines_out.append("")
        lines_out.append("sequence_tail (last 15 days, day, $/mo equiv):")
        for pt in info.get("sequence_tail", []):
            lines_out.append(f"  {pt}")
        lines_out.append("")
        lines_out.append("raw_amounts_tail (last 15 days, day, raw $):")
        for pt in info.get("raw_amounts_tail", []):
            lines_out.append(f"  {pt}")

        text.insert("1.0", "\n".join(lines_out))
        text.config(state="disabled")

    def goal_graph_panel(self):
        """Visual version of the Harsh/Light/Blended projections --
        history (insight_projection.daily_average_sequence(), the
        same data light_completion_projection() fits a trend through)
        as a solid line with dots, each lane's forward projection as
        a dashed ray to where it crosses the target, a dashed target
        line. Hand-drawn on a Canvas, same style as show_chart() --
        no charting library. Lanes still sitting at the 5-year
        cold-start placeholder aren't drawn as a line (it would either
        be invisible off the right edge or misleadingly compressed) --
        noted in a caption underneath instead."""
        win = tk.Toplevel(self.root)
        win.title(f"Goal Projection Graph (build {BUILD_TAG})")
        win.configure(bg="#0e0e12")
        win.geometry("560x400")
        win.attributes("-topmost", True)

        canvas = tk.Canvas(win, bg="#0e0e12", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        caption = tk.Label(win, text="", fg=DIM, bg="#0e0e12",
                           font=("Segoe UI", 8), wraplength=530,
                           justify="left")
        caption.pack(fill="x", padx=12, pady=(0, 10))

        def draw():
            canvas.delete("all")
            canvas.update_idletasks()
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw < 50 or ch < 50:
                return

            margin_l, margin_r, margin_t, margin_b = 54, 16, 16, 28

            sequence = insight_projection.daily_average_sequence()
            d = data.load()
            target = d.get("money", {}).get("target_monthly", 0)

            if not sequence or target <= 0:
                canvas.create_text(
                    cw // 2, ch // 2,
                    text="Not enough data yet -- need at least one "
                         "Stripe payment and a target set (click the "
                         "goal line at the top).",
                    fill="#6b6b76", font=("Segoe UI", 9), width=cw - 60)
                return

            harsh = insight_projection.harsh_completion_projection()
            light = insight_projection.light_completion_projection()
            today = date.today()
            last_x = sequence[-1][0]
            last_val = sequence[-1][1]

            lanes = [("Harsh", harsh, "#c9634a"), ("Light", light, "#4caf6b")]
            plottable = []
            skipped = []
            for name, result, color in lanes:
                if result.get("confidence") == "none yet":
                    skipped.append(name)
                    continue
                try:
                    cdate = datetime.strptime(result["completion_date"],
                                              "%Y-%m-%d").date()
                    days_out = (cdate - today).days
                    plottable.append((name, color, last_x + days_out))
                except Exception:
                    skipped.append(name)

            x_max = max([p[2] for p in plottable] + [last_x + 5])
            all_y = [p[1] for p in sequence] + [target]
            y_max = max(all_y) * 1.15 or 1
            plot_w = cw - margin_l - margin_r
            plot_h = ch - margin_t - margin_b

            def x_for(day_val):
                return margin_l + int(max(0, day_val) / x_max * plot_w)

            def y_for(val):
                return margin_t + int((1 - val / y_max) * plot_h)

            target_y = y_for(target)
            canvas.create_line(margin_l, target_y, cw - margin_r, target_y,
                               fill="#6b6030", dash=(4, 3))
            canvas.create_text(cw - margin_r, target_y - 8,
                               text=f"target ${target:,.0f}/mo",
                               fill="#8a7a3a", font=("Segoe UI", 7),
                               anchor="e")

            for frac in (0, 0.25, 0.5, 0.75, 1.0):
                val = frac * y_max
                y = y_for(val)
                canvas.create_line(margin_l, y, cw - margin_r, y,
                                   fill="#22222a")
                canvas.create_text(margin_l - 6, y, text=f"${val:,.0f}",
                                   fill="#4a4a52", font=("Segoe UI", 7),
                                   anchor="e")

            pts = []
            for day_val, y_val in sequence:
                pts.extend([x_for(day_val), y_for(y_val)])
            if len(pts) >= 4:
                canvas.create_line(*pts, fill="#8888a0", width=2)
            for day_val, y_val in sequence:
                canvas.create_oval(x_for(day_val) - 2, y_for(y_val) - 2,
                                   x_for(day_val) + 2, y_for(y_val) + 2,
                                   fill="#8888a0", outline="")

            for name, color, end_x in plottable:
                canvas.create_line(x_for(last_x), y_for(last_val),
                                   x_for(end_x), y_for(target),
                                   fill=color, dash=(5, 3), width=2)
                canvas.create_text(x_for(end_x), y_for(target) - 10,
                                   text=name, fill=color,
                                   font=("Segoe UI", 7, "bold"), anchor="s")

            tx = x_for(last_x)
            canvas.create_line(tx, margin_t, tx, ch - margin_b,
                               fill="#3a3a44", dash=(2, 4))
            canvas.create_text(tx, ch - margin_b + 4, text="today",
                               fill="#6b6b76", font=("Segoe UI", 7),
                               anchor="n")

            if skipped:
                caption.config(
                    text=f"{' and '.join(skipped)} not plotted -- not "
                         "enough evidence of a trend yet, still showing "
                         "the 5-year no-signal placeholder rather than a "
                         "real projection.")
            else:
                caption.config(text="Dots/solid line: your actual "
                                    "cumulative daily average so far. "
                                    "Dashed lines: each lane's forward "
                                    "projection to the target.")

        draw()
        win.bind("<Configure>", lambda e: draw())

    def xp_triggers_panel(self):
        """Menu-editable XP triggers -- add/edit/delete/toggle, no
        code changes ever needed. Backed by shared/xp_triggers.py;
        XP awarded goes through the real character/progression.py
        system (streak multipliers, bonus rolls, daily cashout --
        same as every other XP source)."""
        win = tk.Toplevel(self.root)
        win.title(f"XP Triggers (build {BUILD_TAG})")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("400x480")

        tk.Label(win, text="XP TRIGGERS", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(16, 4))
        tk.Label(win, text="Fires once per day when its condition is "
                           "met. Add as many as you want, change them "
                           "any time.",
                 fg=DIM, bg="#141418", font=("Segoe UI", 8),
                 wraplength=360, justify="left").pack(anchor="w", padx=16,
                                                       pady=(0, 8))

        canvas = tk.Canvas(win, bg="#141418", highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical",
                                 command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg="#141418")
        rows_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0))
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        def render_list():
            for w in rows_frame.winfo_children():
                w.destroy()
            triggers = xp_triggers.list_triggers()
            if not triggers:
                tk.Label(rows_frame, text="No triggers yet.", fg=DIM,
                         bg="#141418", font=("Segoe UI", 9)).pack(pady=8)
            for trig in triggers:
                card = tk.Frame(rows_frame, bg="#1c1c22")
                card.pack(fill="x", pady=(0, 6), padx=(0, 16))
                top = tk.Frame(card, bg="#1c1c22")
                top.pack(fill="x", padx=10, pady=(8, 2))
                tk.Label(top, text=trig["name"], fg=FG, bg="#1c1c22",
                         font=("Segoe UI", 9, "bold")
                         ).pack(side="left")
                tk.Label(top, text=f"+{trig.get('xp', 0)} XP", fg="#4caf6b",
                         bg="#1c1c22", font=("Segoe UI", 9)
                         ).pack(side="right")
                tk.Label(card,
                         text=f"{trig['type']}: {trig.get('param', '')}"
                              f"{'  (inactive)' if not trig.get('active', True) else ''}",
                         fg=DIM, bg="#1c1c22", font=("Segoe UI", 8)
                         ).pack(anchor="w", padx=10)
                btn_row = tk.Frame(card, bg="#1c1c22")
                btn_row.pack(fill="x", padx=10, pady=(4, 8))
                tk.Button(btn_row, text="Edit", bg=BG2, fg=FG,
                         relief="flat", font=("Segoe UI", 8),
                         cursor="hand2",
                         command=lambda t=trig: open_edit(t)
                         ).pack(side="left", padx=(0, 4))
                tk.Button(btn_row, text="Delete", bg=BG2, fg="#c9634a",
                         relief="flat", font=("Segoe UI", 8),
                         cursor="hand2",
                         command=lambda t=trig: do_delete(t)
                         ).pack(side="left")

        def do_delete(trig):
            xp_triggers.delete_trigger(trig["id"])
            render_list()

        def open_edit(trig=None):
            self._xp_trigger_edit_dialog(trig, render_list)

        tk.Button(win, text="+ Add Trigger", command=lambda: open_edit(None),
                 bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 9),
                 cursor="hand2").pack(pady=(8, 10))

        render_list()

    def _xp_trigger_edit_dialog(self, trig, on_save):
        """trig=None for a new trigger, or an existing trigger dict to
        edit. on_save is called (no args) after saving, to refresh the
        list behind this dialog."""
        win = tk.Toplevel(self.root)
        win.title("Edit Trigger" if trig else "New Trigger")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("340x460")

        tk.Label(win, text="Name", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(14, 2))
        name_entry = tk.Entry(win, bg=BG3, fg=FG, insertbackground=FG,
                              font=("Segoe UI", 9), relief="flat")
        name_entry.insert(0, trig["name"] if trig else "")
        name_entry.pack(fill="x", padx=16, ipady=4)

        tk.Label(win, text="Type", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(10, 2))
        type_var = tk.StringVar(value=trig["type"] if trig else
                                list(xp_triggers.TYPES.keys())[0])
        type_menu = tk.OptionMenu(win, type_var, *xp_triggers.TYPES.keys())
        type_menu.config(bg=BG2, fg=FG, relief="flat",
                         font=("Segoe UI", 9), highlightthickness=0)
        type_menu.pack(fill="x", padx=16)

        help_lbl = tk.Label(win, text="", fg=DIM, bg="#141418",
                            font=("Segoe UI", 7, "italic"), wraplength=300,
                            justify="left")
        help_lbl.pack(anchor="w", padx=16, pady=(2, 0))

        # Category dropdown -- only relevant for category_minutes, but
        # created up front and shown/hidden as the type changes.
        cat_label = tk.Label(win, text="Category", fg=DIM, bg="#141418",
                             font=("Segoe UI", 8))
        cat_var = tk.StringVar(value=trig.get("category", xp_triggers.CATEGORIES[0])
                               if trig else xp_triggers.CATEGORIES[0])
        cat_menu = tk.OptionMenu(win, cat_var, *xp_triggers.CATEGORIES)
        cat_menu.config(bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 9),
                        highlightthickness=0)

        param_label = tk.Label(win, text="Condition value", fg=DIM,
                               bg="#141418", font=("Segoe UI", 8))
        param_label.pack(anchor="w", padx=16, pady=(10, 2))
        param_entry = tk.Entry(win, bg=BG3, fg=FG, insertbackground=FG,
                               font=("Segoe UI", 9), relief="flat")
        param_entry.insert(0, trig.get("param", "") if trig else "")
        param_entry.pack(fill="x", padx=16, ipady=4)

        FIELD_LABELS = {
            "note_keyword": "Word/phrase to look for",
            "revenue_received": "Minimum $ (blank = any payment)",
            "focus_score_above": "Minimum score (0-100)",
            "arrived_before": "Time (24h HH:MM)",
            "category_minutes": "Minimum minutes",
        }

        def update_help(*_):
            t = type_var.get()
            help_lbl.config(text=xp_triggers.TYPES.get(t, ""))
            param_label.config(text=FIELD_LABELS.get(t, "Condition value"))
            if t == "category_minutes":
                cat_label.pack(anchor="w", padx=16, pady=(10, 2))
                cat_menu.pack(fill="x", padx=16)
            else:
                cat_label.pack_forget()
                cat_menu.pack_forget()
        type_var.trace_add("write", update_help)
        update_help()

        tk.Label(win, text="XP amount", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(10, 2))
        xp_entry = tk.Entry(win, bg=BG3, fg=FG, insertbackground=FG,
                            font=("Segoe UI", 9), relief="flat")
        xp_entry.insert(0, str(trig.get("xp", 10)) if trig else "10")
        xp_entry.pack(fill="x", padx=16, ipady=4)

        active_var = tk.BooleanVar(value=trig.get("active", True) if trig else True)
        tk.Checkbutton(win, text="Active", variable=active_var, fg=FG,
                       bg="#141418", selectcolor=BG2, activebackground="#141418",
                       activeforeground=FG, font=("Segoe UI", 9)
                       ).pack(anchor="w", padx=16, pady=(10, 0))

        status = tk.Label(win, text="", fg="#c9634a", bg="#141418",
                          font=("Segoe UI", 8))
        status.pack(anchor="w", padx=16, pady=(4, 0))

        def do_save():
            name = name_entry.get().strip()
            if not name:
                status.config(text="Name is required.")
                return
            try:
                xp_val = int(xp_entry.get().strip())
            except ValueError:
                status.config(text="XP must be a whole number.")
                return
            new_trig = {
                "id": trig["id"] if trig else None,
                "name": name,
                "type": type_var.get(),
                "param": param_entry.get().strip(),
                "xp": xp_val,
                "active": active_var.get(),
            }
            if type_var.get() == "category_minutes":
                new_trig["category"] = cat_var.get()
            xp_triggers.save_trigger(new_trig)
            win.destroy()
            on_save()

        tk.Button(win, text="Save", command=do_save, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 9), cursor="hand2"
                  ).pack(pady=(14, 0))

    def integrations_panel(self):
        """Settings > Integrations -- paste an API key, click Save,
        see a connection status light. Backed by shared/secrets_store.py
        -- keys are stored locally in secrets.json (plain text, same
        protection level as an environment variable) and take effect
        immediately, no restart needed. Loops over
        secrets_store.INTEGRATIONS, so adding a future integration
        (Whoop, Fitbit, etc.) needs no new UI code here."""
        import secrets_store

        win = tk.Toplevel(self.root)
        win.title("Integrations")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("380x480")

        tk.Label(win, text="INTEGRATIONS", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(16, 8))

        canvas = tk.Canvas(win, bg="#141418", highlightthickness=0)
        scrollbar = tk.Scrollbar(win, orient="vertical",
                                 command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg="#141418")
        rows_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0))
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        for integ in secrets_store.INTEGRATIONS:
            env_key = integ["env_key"]
            card = tk.Frame(rows_frame, bg="#1c1c22")
            card.pack(fill="x", pady=(0, 10), padx=(0, 16))

            header = tk.Frame(card, bg="#1c1c22")
            header.pack(fill="x", padx=12, pady=(10, 2))
            dot = tk.Canvas(header, width=10, height=10, bg="#1c1c22",
                            highlightthickness=0)
            dot.pack(side="left", padx=(0, 6))
            dot_id = dot.create_oval(1, 1, 9, 9, fill="#666670", outline="")
            tk.Label(header, text=integ["name"], fg=FG, bg="#1c1c22",
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            status_lbl = tk.Label(header, text="", fg=DIM, bg="#1c1c22",
                                  font=("Segoe UI", 8))
            status_lbl.pack(side="right")

            tk.Label(card, text=integ["help"], fg=DIM, bg="#1c1c22",
                     font=("Segoe UI", 8), wraplength=320, justify="left"
                     ).pack(anchor="w", padx=12, pady=(0, 6))

            entry_row = tk.Frame(card, bg="#1c1c22")
            entry_row.pack(fill="x", padx=12, pady=(0, 10))
            entry = tk.Entry(entry_row, bg=BG3, fg=FG,
                             insertbackground=FG, font=("Segoe UI", 9),
                             relief="flat", show="•")
            entry.pack(side="left", fill="x", expand=True, ipady=4,
                      padx=(0, 6))

            def set_dot(color, dot=dot, dot_id=dot_id):
                dot.itemconfig(dot_id, fill=color)

            def refresh_status(env_key=env_key, dot_fn=set_dot,
                               status_lbl=status_lbl):
                if secrets_store.is_set(env_key):
                    dot_fn("#4caf6b")
                    status_lbl.config(text="Connected")
                else:
                    dot_fn("#666670")
                    status_lbl.config(text="Not connected")

            def do_save(env_key=env_key, entry=entry,
                       refresh=refresh_status):
                val = entry.get().strip()
                if not val:
                    return
                secrets_store.set_key(env_key, val)
                entry.delete(0, "end")
                refresh()

            def do_test(integ=integ, dot_fn=set_dot,
                       status_lbl=status_lbl):
                verify_fn = integ.get("verify")
                if not verify_fn:
                    return
                status_lbl.config(text="Testing...")

                def run_test():
                    return verify_fn()

                def done(result):
                    ok, msg = result
                    if ok:
                        dot_fn("#4caf6b")
                    else:
                        dot_fn("#c9634a")
                    status_lbl.config(text=msg[:40])

                run_bg(run_test, done, self.root)

            def do_clear(env_key=env_key, refresh=refresh_status):
                secrets_store.clear_key(env_key)
                refresh()

            tk.Button(entry_row, text="Save", command=do_save, bg=BG2,
                     fg=FG, relief="flat", font=("Segoe UI", 8),
                     cursor="hand2", width=6).pack(side="left")

            btn_row = tk.Frame(card, bg="#1c1c22")
            btn_row.pack(fill="x", padx=12, pady=(0, 10))
            tk.Button(btn_row, text="Test Connection", command=do_test,
                     bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                     cursor="hand2").pack(side="left", padx=(0, 6))
            tk.Button(btn_row, text="Clear", command=do_clear, bg=BG2,
                     fg=DIM, relief="flat", font=("Segoe UI", 8),
                     cursor="hand2").pack(side="left")

            refresh_status()

    def edit_text_field(self, field_key, title, label_widget):
        """Click-to-edit for a plain text field in data.json (lifestyle,
        mission). Saves via data.save(), which every AI prompt already
        reads fresh from disk each call (see insight/distiller.py's
        _goal_line(), shared/ai.py's context building) -- so an edit
        here reaches the AI on its very next call, no extra wiring."""
        d = data.load()
        current = d.get(field_key, "")
        win = tk.Toplevel(self.root)
        win.title(f"Edit {title}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("360x220")

        tk.Label(win, text=title.upper(), fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(pady=(16, 6))
        text = tk.Text(win, wrap="word", bg=BG3, fg=FG,
                       insertbackground=FG, font=("Segoe UI", 10),
                       relief="flat", height=5, padx=8, pady=6)
        text.insert("1.0", current)
        text.pack(padx=20, fill="x")
        text.focus_set()

        def save():
            new_val = text.get("1.0", "end").strip()
            dd = data.load()
            dd[field_key] = new_val
            data.save(dd)
            label_widget.config(text=new_val)
            win.destroy()

        tk.Button(win, text="Save", command=save, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  width=10).pack(pady=(12, 0))

    def edit_goal_amount(self):
        """Click the money line to set the target monthly revenue
        goal. This is the one number that has no automatic source --
        everything else (current rate, completion date) is computed
        from logged sales."""
        d = data.load()
        win = tk.Toplevel(self.root)
        win.title("Set Goal Amount")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("280x140")

        tk.Label(win, text="Target monthly revenue ($)", fg=DIM,
                 bg="#141418", font=("Segoe UI", 9)).pack(pady=(16, 4))
        entry = tk.Entry(win, bg=BG3, fg=FG, insertbackground=FG,
                         font=("Segoe UI", 11), relief="flat",
                         justify="center")
        entry.insert(0, str(d["money"].get("target_monthly", 0)))
        entry.pack(pady=4, padx=30, fill="x", ipady=4)
        entry.focus_set()
        entry.select_range(0, "end")

        def save(_=None):
            try:
                val = int(float(entry.get().strip() or 0))
            except ValueError:
                return
            dd = data.load()
            dd["money"]["target_monthly"] = val
            data.save(dd)
            win.destroy()
            self.refresh_static()

        entry.bind("<Return>", save)
        tk.Button(win, text="Save", command=save, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  width=10).pack(pady=(10, 0))

    def calendar_panel(self):
        """Calendar archive -- browse month to month, click a day to see
        hourly activity, daily notes, and videos. Real drag-and-drop if tkinterdnd2
        is installed (DND_AVAILABLE), but every day also has a working
        file-picker button regardless -- the feature is fully usable
        either way, this is purely an upgrade when available."""
        win = tk.Toplevel(self.root)
        win.title("Calendar")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("500x600")

        state = {"year": date.today().year, "month": date.today().month}

        header = tk.Frame(win, bg="#141418")
        header.pack(fill="x", padx=16, pady=(16, 8))
        tk.Button(header, text="<", command=lambda: nav(-1), bg=BG2, fg=FG,
                  relief="flat", width=3, cursor="hand2").pack(side="left")
        month_lbl = tk.Label(header, text="", fg=FG, bg="#141418",
                             font=("Segoe UI", 13, "bold"))
        month_lbl.pack(side="left", expand=True)
        tk.Button(header, text=">", command=lambda: nav(1), bg=BG2, fg=FG,
                  relief="flat", width=3, cursor="hand2").pack(side="right")

        dow_row = tk.Frame(win, bg="#141418")
        dow_row.pack(fill="x", padx=16)
        for dname in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            tk.Label(dow_row, text=dname, fg=DIM, bg="#141418",
                     font=("Segoe UI", 8, "bold"), width=4).pack(
                         side="left", expand=True)

        grid_frame = tk.Frame(win, bg="#141418")
        grid_frame.pack(fill="both", expand=True, padx=16, pady=(4, 8))

        def render():
            for w in grid_frame.winfo_children():
                w.destroy()
            y, m = state["year"], state["month"]
            month_lbl.config(text=f"{pycalendar.month_name[m]} {y}")
            cal = pycalendar.Calendar(firstweekday=0)  # Monday first
            weeks = cal.monthdayscalendar(y, m)
            video_days = video_memories.days_with_videos_in_month(y, m)
            note_days = db.days_with_notes_in_month(y, m)
            game_month = game_engine.calendar_month_summary(y, m)
            game_days = {r["day_number"]: r for r in game_month.get("days", [])}
            today = date.today()

            for r, week in enumerate(weeks):
                for c, day_num in enumerate(week):
                    if day_num == 0:
                        tk.Label(grid_frame, text="", bg="#141418",
                                width=4, height=2).grid(row=r, column=c,
                                                        padx=1, pady=1)
                        continue
                    is_today = (y == today.year and m == today.month and
                               day_num == today.day)
                    has_memory = day_num in video_days or day_num in note_days
                    game_row = game_days.get(day_num)
                    is_record = bool(game_row and game_row.get("is_record_day"))
                    is_week_record = bool(game_row and game_row.get("is_record_week"))
                    bg = "#2a5a8a" if is_today else ("#3b3420" if is_record else BG2)
                    markers = (" ♛" if is_record else "") + (" W" if is_week_record else "")
                    mem = " •" if has_memory else ""
                    score_line = f"\n{game_row['score_xp']:,} XP" if game_row and game_row.get("score_xp", 0) else ""
                    text = f"{day_num}{markers}{mem}{score_line}"
                    tk.Button(grid_frame, text=text, bg=bg, fg=FG,
                             relief="flat", font=("Segoe UI", 8),
                             width=7, height=3, cursor="hand2",
                             command=lambda d=day_num: open_day(d)
                             ).grid(row=r, column=c, padx=1, pady=1, sticky="nsew")

        def nav(delta):
            m = state["month"] + delta
            y = state["year"]
            if m < 1:
                m = 12
                y -= 1
            elif m > 12:
                m = 1
                y += 1
            state["month"], state["year"] = m, y
            render()

        def open_day(day_num):
            day_str = f"{state['year']:04d}-{state['month']:02d}-{day_num:02d}"
            self._day_detail_panel(day_str, on_change=render)

        render()

    def _day_detail_panel(self, day_str, on_change=None):
        """The calendar's day-click destination: hourly history on
        top (click an hour for its app-level breakdown), notes and videos below.
        Hourly data is currently synthetic-only, generated on demand
        via the button shown when a day has none yet -- see
        shared/day_breakdown.py's module docstring for why, and what
        a real version would need to do differently."""
        win = tk.Toplevel(self.root)
        win.title(f"Day Detail \u2014 {day_str}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("620x900")

        tk.Label(win, text=day_str, fg=FG, bg="#141418",
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 4))

        # ── Canonical game history ───────────────────────────────────
        game = game_engine.day_summary(day_str)
        game_frame = tk.Frame(win, bg=BG2, highlightbackground=BORDER,
                              highlightthickness=1)
        game_frame.pack(fill="x", padx=16, pady=(2, 6))
        title_bits = [f"SCORE {game['score_xp']:,} XP",
                      f"GHOST {game['ghost_final_xp']:,}",
                      f"GAP {'+' if game['gap_final']>0 else ''}{game['gap_final']:,}"]
        if game.get("was_record_day"):
            title_bits.append("♛ RECORD DAY")
        if game.get("was_record_week"):
            title_bits.append("WEEK RECORD")
        tk.Label(game_frame, text="   |   ".join(title_bits), fg=FG, bg=BG2,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(7, 3))
        breakdown = game.get("activity_breakdown", [])
        if breakdown:
            btxt = "  •  ".join(
                f"{b['name']}: {b['score_xp']:,} XP" for b in breakdown[:6])
        else:
            btxt = "No scored activities on this day."
        tk.Label(game_frame, text=btxt, fg=DIM, bg=BG2, font=("Segoe UI", 8),
                 wraplength=570, justify="left").pack(anchor="w", padx=10, pady=(0, 4))
        timeline = game.get("timeline", [])
        if timeline:
            tbox = tk.Text(game_frame, height=5, wrap="none", bg="#101014", fg=FG,
                           font=("Consolas", 8), relief="flat", padx=6, pady=4)
            tbox.pack(fill="x", padx=10, pady=(0, 8))
            for e in timeline:
                sign = "+" if e['score_xp'] > 0 else ""
                qty = e.get('quantity', 1)
                qty_txt = f" x{qty:g}" if abs(qty-1) > .001 else ""
                tbox.insert("end", f"{e['clock']:<9} {sign}{e['score_xp']:>5} XP  {e['activity_name']}{qty_txt}  → {e['running_score']:,}\n")
            tbox.config(state="disabled")

        # ── Hourly history ──────────────────────────────────────────
        tk.Label(win, text="HOURLY HISTORY", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(12, 4))

        hourly_outer = tk.Frame(win, bg="#141418")
        hourly_outer.pack(fill="x", padx=16)

        def render_hourly():
            for w in hourly_outer.winfo_children():
                w.destroy()

            doc = day_breakdown.load_day(day_str)
            if not doc:
                if day_breakdown.has_real_activity(day_str):
                    tk.Label(hourly_outer,
                             text="Activity was tracked this day but hasn't "
                                  "been built into a breakdown yet.",
                             fg=DIM, bg="#141418", font=("Segoe UI", 9),
                             wraplength=340, justify="left"
                             ).pack(pady=(4, 4), anchor="w")
                    tk.Button(hourly_outer,
                              text="Build from Activity Log",
                              command=lambda: (
                                  day_breakdown.build_day_from_activity(day_str),
                                  render_hourly()),
                              bg=BG2, fg=FG, relief="flat",
                              font=("Segoe UI", 8), cursor="hand2"
                              ).pack(anchor="w", pady=(0, 8))
                else:
                    tk.Label(hourly_outer,
                             text="No activity was tracked this day.",
                             fg=DIM, bg="#141418", font=("Segoe UI", 9)
                             ).pack(pady=(4, 4), anchor="w")
                    tk.Button(hourly_outer,
                              text="Generate Preview Data (synthetic)",
                              command=lambda: (day_breakdown.synth_seed_day(day_str),
                                               render_hourly()),
                              bg=BG2, fg=FG, relief="flat",
                              font=("Segoe UI", 8), cursor="hand2"
                              ).pack(anchor="w", pady=(0, 8))
                return

            if doc.get("synthetic"):
                tk.Label(hourly_outer,
                         text="Preview data (not real activity yet)",
                         fg=DIM, bg="#141418",
                         font=("Segoe UI", 7, "italic")
                         ).pack(anchor="w", pady=(0, 2))
                if day_breakdown.has_real_activity(day_str):
                    tk.Button(hourly_outer,
                              text="Replace with Real Data",
                              command=lambda: (
                                  day_breakdown.build_day_from_activity(day_str),
                                  render_hourly()),
                              bg=BG2, fg=FG, relief="flat",
                              font=("Segoe UI", 8), cursor="hand2"
                              ).pack(anchor="w", pady=(0, 4))

            canvas = tk.Canvas(hourly_outer, bg="#141418", height=260,
                               highlightthickness=0)
            scrollbar = tk.Scrollbar(hourly_outer, orient="vertical",
                                     command=canvas.yview)
            rows_frame = tk.Frame(canvas, bg="#141418")
            rows_frame.bind("<Configure>", lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=rows_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Mouse-wheel scrolling -- a scrollbar alone doesn't make
            # the wheel do anything in tkinter, this has to be bound
            # explicitly. Only active while the cursor is actually
            # over this list, so it doesn't hijack scrolling anywhere
            # else in the window (or other windows) while this is open.
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            def _bind_wheel(_e):
                canvas.bind_all("<MouseWheel>", _on_mousewheel)

            def _unbind_wheel(_e):
                canvas.unbind_all("<MouseWheel>")

            canvas.bind("<Enter>", _bind_wheel)
            canvas.bind("<Leave>", _unbind_wheel)

            for h in doc["hours"]:
                row = tk.Frame(rows_frame, bg="#141418", cursor="hand2")
                row.pack(fill="x", pady=1)

                tk.Label(row, text=timeutil.to12(f"{h['hour']:02d}:00"),
                         fg=FG, bg="#141418", font=("Segoe UI", 9), width=8,
                         anchor="w").pack(side="left")

                bar = tk.Canvas(row, width=140, height=16, bg="#141418",
                                highlightthickness=0)
                bar.pack(side="left", padx=(4, 8))
                x = 0
                for seg in h["segments"]:
                    seg_w = 140 * seg["pct"] / 100
                    color = day_breakdown.CATEGORY_COLORS.get(
                        seg["category"], "#666670")
                    bar.create_rectangle(x, 1, x + seg_w, 15,
                                         fill=color, outline="")
                    x += seg_w

                if h.get("label"):
                    color = day_breakdown.CATEGORY_COLORS.get(
                        h["label"], BG2)
                    tk.Label(row, text=h["label"], bg=color, fg="#141418",
                             font=("Segoe UI", 7, "bold"), padx=6
                             ).pack(side="left")

                for widget in [row] + row.winfo_children():
                    widget.bind("<Button-1>",
                               lambda e, hd=h: self._hour_breakdown_popup(
                                   day_str, hd))

        render_hourly()

        # ── Daily notes ──────────────────────────────────────────────
        tk.Label(win, text="DAILY NOTES", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(12, 4))
        notes_frame = tk.Frame(win, bg="#141418")
        notes_frame.pack(fill="x", padx=16)

        def refresh_notes():
            for w in notes_frame.winfo_children():
                w.destroy()
            rows = db.notes_for_day(day_str)
            if not rows:
                tk.Label(notes_frame, text="No notes yet.", fg=DIM,
                         bg="#141418", font=("Segoe UI", 8)).pack(anchor="w")
                return
            for ts, text in rows[-5:]:
                try:
                    tlabel = datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")
                except Exception:
                    tlabel = ""
                tk.Label(notes_frame, text=f"{tlabel}  {text}", fg=FG,
                         bg="#141418", font=("Segoe UI", 8), anchor="w",
                         justify="left", wraplength=360).pack(fill="x", pady=1)

        note_row = tk.Frame(win, bg="#141418")
        note_row.pack(fill="x", padx=16, pady=(5, 2))
        note_entry = tk.Entry(note_row, bg=BG3, fg=FG, insertbackground=FG,
                              font=("Segoe UI", 8), relief="flat", borderwidth=0)
        note_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)

        def add_calendar_note(_=None):
            text = note_entry.get().strip()
            if not text:
                return
            db.log_note_for_day(day_str, text)
            note_entry.delete(0, "end")
            refresh_notes()
            if on_change:
                on_change()

        note_entry.bind("<Return>", add_calendar_note)
        tk.Button(note_row, text="Add Note", command=add_calendar_note,
                  bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 8),
                  cursor="hand2").pack(side="right")
        refresh_notes()

        # ── Videos ───────────────────────────────────────────────────
        tk.Label(win, text="VIDEOS", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(16, 4))

        list_frame = tk.Frame(win, bg="#141418")
        list_frame.pack(fill="both", expand=True, padx=16)

        status = tk.Label(win, text="", fg=DIM, bg="#141418",
                          font=("Segoe UI", 8))

        def refresh_video_list():
            for w in list_frame.winfo_children():
                w.destroy()
            vids = video_memories.videos_for_day(day_str)
            if not vids:
                tk.Label(list_frame, text="No videos yet.", fg=DIM,
                         bg="#141418", font=("Segoe UI", 9)).pack(pady=8)
            for fname in vids:
                vrow = tk.Frame(list_frame, bg="#141418")
                vrow.pack(fill="x", pady=2)
                tk.Label(vrow, text=fname, fg=FG, bg="#141418",
                         font=("Segoe UI", 9), anchor="w",
                         wraplength=220).pack(side="left", fill="x",
                                              expand=True)
                tk.Button(vrow, text="Open", bg=BG2, fg=FG, relief="flat",
                         font=("Segoe UI", 8), cursor="hand2",
                         command=lambda f=fname: video_memories.open_video(
                             video_memories.video_path(day_str, f))
                         ).pack(side="right")

        def add_video_dialog():
            path = filedialog.askopenfilename(
                title="Choose a video",
                filetypes=[("Video files",
                           "*.mp4 *.mov *.avi *.mkv *.webm *.m4v")])
            if not path:
                return
            try:
                video_memories.add_video(day_str, path)
                status.config(text="Added.")
                refresh_video_list()
                if on_change:
                    on_change()
            except Exception as e:
                status.config(text=f"Couldn't add: {e}")

        tk.Button(win, text="Add Video...", command=add_video_dialog,
                  bg=BG2, fg=FG, relief="flat", font=("Segoe UI", 9),
                  cursor="hand2").pack(pady=(8, 4))

        if DND_AVAILABLE:
            tk.Label(win, text="or drag a video file onto this window",
                     fg=DIM, bg="#141418",
                     font=("Segoe UI", 8, "italic")).pack(pady=(0, 4))

            def on_drop(event):
                paths = win.tk.splitlist(event.data)
                added, failed = 0, 0
                for p in paths:
                    try:
                        video_memories.add_video(day_str, p)
                        added += 1
                    except Exception:
                        failed += 1
                msg = f"Added {added}."
                if failed:
                    msg += f" {failed} skipped (not a recognized video file)."
                status.config(text=msg)
                refresh_video_list()
                if on_change and added:
                    on_change()

            win.drop_target_register(DND_FILES)
            win.dnd_bind("<<Drop>>", on_drop)

        status.pack(pady=(0, 8))
        refresh_video_list()

    def _hour_breakdown_popup(self, day_str, hour_data):
        """Detail view for a single hour -- summary + per-app
        proportional bars, opened by clicking an hour row in
        _day_detail_panel."""
        h = hour_data["hour"]
        h_label = timeutil.to12(f"{h:02d}:00")
        h_next_label = timeutil.to12(f"{(h + 1) % 24:02d}:00")
        win = tk.Toplevel(self.root)
        win.title(f"{h_label} \u2014 {day_str}")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("320x360")

        tk.Label(win, text=f"{h_label} \u2013 {h_next_label}",
                 fg=FG, bg="#141418", font=("Segoe UI", 13, "bold")
                 ).pack(pady=(16, 2))
        tk.Label(win, text=hour_data["summary"], fg=DIM, bg="#141418",
                 font=("Segoe UI", 9), wraplength=280
                 ).pack(pady=(0, 12))

        tk.Frame(win, bg="#2a2a32", height=1).pack(fill="x", padx=20)

        apps_frame = tk.Frame(win, bg="#141418")
        apps_frame.pack(fill="both", expand=True, padx=20, pady=(12, 12))

        for app in hour_data["apps"]:
            row = tk.Frame(apps_frame, bg="#141418")
            row.pack(fill="x", pady=6)

            top = tk.Frame(row, bg="#141418")
            top.pack(fill="x")
            tk.Label(top, text=app["name"], fg=FG, bg="#141418",
                     font=("Segoe UI", 9), anchor="w"
                     ).pack(side="left", fill="x", expand=True)
            tk.Label(top, text=f"{app['pct']}%", fg=DIM, bg="#141418",
                     font=("Segoe UI", 9)).pack(side="right")

            bar_bg = tk.Canvas(row, height=8, bg="#2a2a32",
                               highlightthickness=0)
            bar_bg.pack(fill="x", pady=(3, 1))
            color = day_breakdown.CATEGORY_COLORS.get(
                app.get("category"), "#8888a0")

            def draw_bar(canvas=bar_bg, pct=app["pct"], c=color):
                canvas.update_idletasks()
                w = canvas.winfo_width() or 260
                canvas.create_rectangle(0, 0, w * pct / 100, 8,
                                        fill=c, outline="")
            win.after(10, draw_bar)

            tk.Label(row, text=f"{app['duration_min']} min", fg=DIM,
                     bg="#141418", font=("Segoe UI", 7)
                     ).pack(anchor="w")

    def notes_panel(self):
        """Daily notes -- one-way input, no AI response. These feed the
        insight pipeline (insight/raw_stats.py picks them up per day)
        as qualitative data alongside the raw activity log. Nothing in
        here talks back.

        Each submission also triggers an immediate background rebuild
        of TODAY's colored document (distiller.build_daily), not just
        yesterday's -- insight_schedule only processes a day once it's
        "yesterday", and only checks once at app startup, so without
        this a logged sale wouldn't show up in the goal projection
        until the next day's launch. This makes it show up right
        after you hit Add instead."""
        win = tk.Toplevel(self.root)
        win.title("Daily Notes")
        win.attributes("-topmost", True)
        win.configure(bg="#141418")
        win.geometry("340x420")

        tk.Label(win, text="TODAY'S NOTES", fg=DIM, bg="#141418",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16,
                                                     pady=(12, 4))

        log = tk.Text(win, wrap="word", bg=BG2, fg=FG, state="disabled",
                      height=12, padx=10, pady=8, font=("Segoe UI", 9),
                      relief="flat", borderwidth=0)
        log.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        today = date.today().isoformat()
        status = tk.Label(win, text="", fg=DIM, bg="#141418",
                          font=("Segoe UI", 8))
        status.pack(anchor="w", padx=16)

        def refresh_log():
            log.config(state="normal")
            log.delete("1.0", "end")
            for ts, text in db.notes_for_day(today):
                t = datetime.fromtimestamp(ts).strftime("%H:%M")
                log.insert("end", f"{t}  {text}\n")
            log.config(state="disabled")
            log.see("end")

        refresh_log()

        row = tk.Frame(win, bg="#141418")
        row.pack(fill="x", padx=16, pady=(0, 12))
        entry = tk.Entry(row, bg=BG3, fg=FG, insertbackground=FG,
                          font=("Segoe UI", 9), relief="flat", borderwidth=0)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=4)
        entry.focus_set()

        def _rebuild_today():
            import distiller
            distiller.build_daily(today)
            return True

        def _rebuild_done(_result):
            status.config(text="")
            self.refresh_static()

        def submit(_=None):
            text = entry.get().strip()
            if not text:
                return
            db.log_note(text)
            entry.delete(0, "end")
            refresh_log()
            status.config(text="Checking for revenue / updating projection…")
            run_bg(_rebuild_today, _rebuild_done, self.root)

        entry.bind("<Return>", submit)
        tk.Button(row, text="Add", command=submit, bg=BG2, fg=FG,
                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                  width=6).pack(side="left")

    def recap(self):
        summary = db.today_summary()
        s = score_mod.today_score()
        streak, _, avg7 = score_mod.streak_info()
        db.save_score(summary["day"], s)

        def got(j):
            if isinstance(j, str):
                j = {"recap": j, "schedule": data.load()["schedule"],
                     "spoken": ""}
            os.makedirs(config.RECAP_DIR, exist_ok=True)
            path = os.path.join(config.RECAP_DIR, f"{summary['day']}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(j["recap"])
            d = data.load()
            d["schedule"] = j["schedule"]
            data.save(d); self.refresh_static()
            if j.get("spoken"):
                voice.speak(j["spoken"])
            win = tk.Toplevel(self.root)
            win.title(f"Daily Recap — {summary['day']}  ({s}%)")
            win.configure(bg="#17171d"); win.geometry("560x480")
            box = tk.Text(win, wrap="word", bg="#0d0d0f", fg=FG, padx=12,
                          pady=12)
            box.pack(fill="both", expand=True)
            m = data.load()["money"]
            proj = score_mod.projection_line(m, avg7)
            box.insert("1.0", j["recap"] +
                       f"\n\n— {proj}\n(saved to {path}; tomorrow's schedule "
                       "updated)")
            box.config(state="disabled")
        run_bg(lambda: ai.recap_and_new_schedule(summary, s, streak, avg7),
               got, self.root)

    # ── misc ────────────────────────────────────────────────────────────
    def show_chart(self):
        """Canonical XP performance chart: live score vs seven-day Ghost."""
        win = tk.Toplevel(self.root)
        win.title(f"WITNESS — XP Performance ({BUILD_TAG})")
        win.configure(bg="#0e0e12")
        win.geometry("700x460")
        win.attributes("-topmost", True)

        bar = tk.Frame(win, bg="#0e0e12")
        bar.pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(bar, text="XP PERFORMANCE — LIVE vs 7-DAY GHOST", fg=DIM,
                 bg="#0e0e12", font=("Segoe UI", 8, "bold")).pack(side="left")
        view_var = {"v": 30}
        canvas = tk.Canvas(win, bg="#0e0e12", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        def draw(days):
            view_var["v"] = days
            canvas.delete("all")
            canvas.update_idletasks()
            cw, ch = canvas.winfo_width(), canvas.winfo_height()
            if cw < 80 or ch < 80:
                return
            rows = game_engine.performance_series(days)
            margin_l, margin_r, margin_t, margin_b = 58, 18, 24, 42
            plot_w = cw - margin_l - margin_r
            plot_h = ch - margin_t - margin_b
            max_y = max([100] + [r["score_xp"] for r in rows] + [r["ghost_xp"] for r in rows])
            # round upper bound for readability
            magnitude = 10 ** max(0, len(str(int(max_y))) - 2)
            max_y = int(((max_y + magnitude - 1) // magnitude) * magnitude)

            def x_for(i):
                return margin_l + (plot_w * i / max(1, len(rows)-1))
            def y_for(v):
                return margin_t + plot_h * (1 - max(0, v) / max_y)

            for frac in (0, .25, .5, .75, 1):
                val = int(max_y * (1-frac))
                y = margin_t + plot_h * frac
                canvas.create_line(margin_l, y, cw-margin_r, y, fill="#292930")
                canvas.create_text(margin_l-7, y, text=f"{val:,}", fill="#666670",
                                   font=("Segoe UI", 7), anchor="e")

            live_pts, ghost_pts = [], []
            for i, row in enumerate(rows):
                live_pts += [x_for(i), y_for(row["score_xp"])]
                ghost_pts += [x_for(i), y_for(row["ghost_xp"])]
            if len(rows) > 1:
                canvas.create_line(*ghost_pts, fill="#6f6f7a", width=1,
                                   dash=(4, 3), smooth=True)
                canvas.create_line(*live_pts, fill="#57cc99", width=2,
                                   smooth=True)
            for i, row in enumerate(rows):
                if days <= 7 or i in (0, len(rows)-1) or i % (5 if days <= 30 else 10) == 0:
                    canvas.create_text(x_for(i), ch-18, text=row["day"][5:],
                                       fill="#666670", font=("Segoe UI", 7), anchor="s")
            canvas.create_text(margin_l, 8, text="LIVE XP", fill="#57cc99",
                               font=("Segoe UI", 7, "bold"), anchor="w")
            canvas.create_text(margin_l+70, 8, text="- - GHOST (7 days prior)",
                               fill="#777782", font=("Segoe UI", 7), anchor="w")
            latest = rows[-1] if rows else {"score_xp": 0, "ghost_xp": 0, "gap": 0}
            canvas.create_text(cw-margin_r, 8,
                               text=(f"Today {latest['score_xp']:,} vs Ghost {latest['ghost_xp']:,}  "
                                     f"Gap {'+' if latest['gap']>0 else ''}{latest['gap']:,}"),
                               fill=FG, font=("Segoe UI", 8, "bold"), anchor="e")

        for label, days in (("7 Days", 7), ("30 Days", 30), ("60 Days", 60)):
            tk.Button(bar, text=label, command=lambda d=days: draw(d), bg=BG2, fg=FG,
                      relief="flat", font=("Segoe UI", 7), cursor="hand2").pack(side="right", padx=2)
        canvas.bind("<Configure>", lambda e: draw(view_var["v"]))
        win.after(20, lambda: draw(30))

    def toggle_mute(self):
        state["muted"] = not state["muted"]
        if state["muted"]:
            self.mute_btn.config(text="🔇", bg="#8b2d30")
            self.convo_add("Witness", "(Voice muted — bubbles still on)",
                           speak_it=False)
        else:
            self.mute_btn.config(text="🔊", bg=BG2)
            self.convo_add("Witness", "Voice back on.", speak_it=True)

    def toggle_deep_work(self):
        if state["deep_work_until"] > time.time():
            state["deep_work_until"] = 0
            self.dw_btn.config(bg="#26262e")
            voice.speak("Deep work ended.")
        else:
            state["deep_work_until"] = time.time() + \
                config.DEEP_WORK_MINUTES * 60
            self.dw_btn.config(bg="#1d3557")
            voice.speak(f"Deep work. {config.DEEP_WORK_MINUTES} minutes. "
                        "No check-ins. Drift gets called out fast.")

    def _auto_export(self):
        """Send daily export if configured, then reschedule."""
        try:
            from datetime import datetime
            now = datetime.now()
            if now.hour >= 21 and export.is_configured():
                ok, msg = export.send_daily()
                if ok:
                    self.convo_add("Witness",
                                  "Daily report sent to your accountability "
                                  "partner.", speak_it=False)
        except Exception:
            pass
        self.root.after(60000 * 30, self._auto_export)

    def quit(self):
        state["stop"] = True
        self.root.destroy()


def _schedule_day_breakdown_refresh(root):
    """Keeps today's calendar hourly-breakdown continually up to date
    while the app runs -- the real aggregator (day_breakdown.py) is
    cheap (pure Python + SQL, no AI), so re-running it every 15
    minutes in the background is fine. Reschedules itself, so this
    keeps going for as long as the app is open."""
    def worker():
        try:
            import day_breakdown
            day_breakdown.refresh_today()
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()
    root.after(15 * 60 * 1000, lambda: _schedule_day_breakdown_refresh(root))


def _schedule_stripe_sync(root):
    """Pulls new Stripe payments into revenue_events every 15 minutes,
    if STRIPE_API_KEY is set -- see shared/stripe_sync.py. No-ops
    (cheaply, without even importing the stripe package) if not
    configured, so this is always safe to schedule unconditionally."""
    def worker():
        try:
            import stripe_sync
            if stripe_sync.is_configured():
                stripe_sync.sync()
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()
    root.after(15 * 60 * 1000, lambda: _schedule_stripe_sync(root))


def _schedule_xp_triggers(root):
    """Checks all active XP triggers every 5 minutes -- shorter
    interval than the other background jobs since this is all cheap
    local DB queries (no AI, no network), and fast feedback matters
    more here: the whole point is XP landing soon after you actually
    do the thing, not up to 15 minutes later."""
    def worker():
        try:
            import xp_triggers
            xp_triggers.check_all()
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()
    root.after(5 * 60 * 1000, lambda: _schedule_xp_triggers(root))


def main():
    try:
        import secrets_store
        secrets_store.load_all()
    except Exception:
        pass
    db.init()
    # Canonical V1 scoring/ghost/records/rolling-level backend. This also
    # migrates the transitional v7.41 manual checklist exactly once.
    try:
        game_engine.initialize()
    except Exception:
        pass
    os.makedirs(config.SOS_VIDEO_DIR, exist_ok=True)
    try:
        import insight_schedule
        threading.Thread(target=insight_schedule.run_if_due,
                          daemon=True).start()
    except Exception:
        pass
    voice.start(state)
    PresenceWatcher(state, events).start()
    WindowTracker(state, events).start()
    threading.Thread(target=scheduler, daemon=True).start()
    # TkinterDnD.Tk() (not plain tk.Tk()) is required for real
    # drag-and-drop to work anywhere in the app -- see the optional
    # tkinterdnd2 import near the top of this file. Falls back to
    # plain tk.Tk() if the package isn't installed; the video calendar
    # still works fully via its file-picker button either way.
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    ui = WitnessUI(root)
    # Today's Suggestions are no longer surfaced on the main page.
    # First real hourly-breakdown build happens quickly after startup,
    # then every 15 minutes for as long as the app runs -- see
    # _schedule_day_breakdown_refresh() above.
    root.after(5000, lambda: _schedule_day_breakdown_refresh(root))
    # Same cadence for Stripe sync -- no-ops if not configured.
    root.after(6000, lambda: _schedule_stripe_sync(root))
    # Automatic XP Triggers are retired from the active product path.
    # XP for configured Activities is awarded only by manual checkboxes.
    root.mainloop()


if __name__ == "__main__":
    main()
