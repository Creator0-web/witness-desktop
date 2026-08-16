from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPoint, QParallelAnimationGroup, QPauseAnimation,
    QPropertyAnimation, QSequentialAnimationGroup, QTimer, Qt, Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import game_analytics
import game_engine

from . import audio, theme
from .widgets import (
    ActivityCard, AnimatedNumberLabel, Badge, BattleBar, RankAvatar, SmoothProgressBar,
    Sparkline, card,
)


class ArenaPage(QScrollArea):
    request_page = Signal(str)
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mode = "daily"
        self._snap = None
        self._activity_widgets = []
        self._activity_by_id = {}
        self._activity_signature = None
        self._battle_state = None
        self._banner = None

        root = QWidget()
        self.setWidget(root)
        self.root_layout = QVBoxLayout(root)
        self.root_layout.setContentsMargins(18, 16, 18, 18)
        self.root_layout.setSpacing(12)

        self._build_header()
        self._build_battle()
        self._build_activities()
        self._build_lower()
        self.root_layout.addStretch(1)
        self.refresh()

    # ── visual structure ──────────────────────────────────────────────
    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        player = card()
        pl = QHBoxLayout(player)
        pl.setContentsMargins(14, 10, 16, 10)
        pl.setSpacing(11)
        self.avatar = RankAvatar()
        self.avatar.clicked.connect(lambda: self.request_page.emit("character"))
        pl.addWidget(self.avatar)
        identity = QVBoxLayout(); identity.setSpacing(2)
        e = QLabel("PLAYER")
        e.setObjectName("Eyebrow")
        self.user_lbl = QLabel("WITNESS")
        self.user_lbl.setStyleSheet("font-size:16px; font-weight:850;")
        mode = QLabel("SELF-COMPETITION MODE")
        mode.setObjectName("Muted")
        identity.addWidget(e); identity.addWidget(self.user_lbl); identity.addWidget(mode)
        pl.addLayout(identity)
        row.addWidget(player, 2)

        level = card(strong=True)
        ll = QVBoxLayout(level)
        ll.setContentsMargins(18, 9, 18, 9)
        ll.setSpacing(4)
        self.level_lbl = QLabel("LV. 1  RECRUIT")
        self.level_lbl.setStyleSheet("font-size:20px; font-weight:900;")
        self.level_detail = QLabel("Rolling rating")
        self.level_detail.setObjectName("Secondary")
        self.level_progress = SmoothProgressBar()
        self.level_progress.setRange(0, 1000)
        self.level_progress.setTextVisible(False)
        ll.addWidget(self.level_lbl)
        ll.addWidget(self.level_detail)
        ll.addWidget(self.level_progress)
        row.addWidget(level, 4)

        self.rating_badge = Badge("RATING", "0 XP", theme.GOLD)
        self.streak_badge = Badge("DAY STREAK", "0", theme.GREEN)
        self.week_badge = Badge("WEEK STREAK", "0", theme.TEXT)
        row.addWidget(self.rating_badge, 1)
        row.addWidget(self.streak_badge, 1)
        row.addWidget(self.week_badge, 1)
        self.root_layout.addLayout(row)

    def _build_battle(self):
        box = card(strong=True)
        self.battle_box = box
        lay = QVBoxLayout(box)
        lay.setContentsMargins(18, 14, 18, 15)
        lay.setSpacing(9)

        top = QHBoxLayout()
        self.battle_title = QLabel("DAILY FIGHT")
        self.battle_title.setObjectName("SectionTitle")
        top.addWidget(self.battle_title)
        sub = QLabel("Race the exact pace of your past self.")
        sub.setObjectName("Muted")
        top.addWidget(sub)
        top.addStretch(1)

        self.daily_btn = QPushButton("DAILY FIGHT")
        self.weekly_btn = QPushButton("WEEKLY CAMPAIGN")
        for b in (self.daily_btn, self.weekly_btn):
            b.setObjectName("Tab")
            b.setCheckable(True)
        self.daily_btn.setChecked(True)
        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self.daily_btn)
        group.addButton(self.weekly_btn)
        self.daily_btn.clicked.connect(lambda: self.set_mode("daily"))
        self.weekly_btn.clicked.connect(lambda: self.set_mode("weekly"))
        top.addWidget(self.daily_btn)
        top.addWidget(self.weekly_btn)
        history = QPushButton("HISTORY")
        history.clicked.connect(lambda: self.request_page.emit("calendar"))
        top.addWidget(history)
        lay.addLayout(top)

        scores = QHBoxLayout()
        scores.setSpacing(24)
        left = QVBoxLayout(); left.setSpacing(0)
        you_e = QLabel("YOU · LIVE")
        you_e.setStyleSheet(f"color:{theme.GREEN}; font-weight:800;")
        self.you_lbl = AnimatedNumberLabel("0 XP")
        self.you_lbl.setObjectName("HugeScore")
        left.addWidget(you_e); left.addWidget(self.you_lbl)
        scores.addLayout(left, 3)

        center = QVBoxLayout(); center.setSpacing(0)
        self.gap_lbl = AnimatedNumberLabel("0 XP")
        self.gap_lbl.setAlignment(Qt.AlignCenter)
        self.gap_lbl.setStyleSheet(f"font-size:33px; font-weight:900; color:{theme.GREEN};")
        self.status_lbl = QLabel("TIED")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("font-size:12px; font-weight:800;")
        center.addWidget(self.gap_lbl); center.addWidget(self.status_lbl)
        scores.addLayout(center, 2)

        right = QVBoxLayout(); right.setSpacing(0)
        ge = QLabel("GHOST · PAST SELF")
        ge.setAlignment(Qt.AlignRight)
        ge.setObjectName("Eyebrow")
        self.ghost_lbl = AnimatedNumberLabel("0 XP")
        self.ghost_lbl.setAlignment(Qt.AlignRight)
        self.ghost_lbl.setStyleSheet(
            f"color:{theme.TEXT_2}; font-size:37px; font-weight:900;")
        right.addWidget(ge); right.addWidget(self.ghost_lbl)
        scores.addLayout(right, 3)
        lay.addLayout(scores)

        self.battle_bar = BattleBar()
        lay.addWidget(self.battle_bar)
        self.battle_meta = QLabel("")
        self.battle_meta.setObjectName("Muted")
        self.battle_meta.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.battle_meta)
        self.root_layout.addWidget(box)

    def _build_activities(self):
        self.activity_box = card()
        lay = QVBoxLayout(self.activity_box)
        lay.setContentsMargins(16, 14, 16, 15)
        lay.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("ACTIVITY FORGE")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        sub = QLabel("Score real actions. Build momentum.")
        sub.setObjectName("Muted")
        header.addWidget(sub)
        header.addStretch(1)
        self.activity_xp_lbl = QLabel("TODAY 0 XP")
        self.activity_xp_lbl.setStyleSheet(f"color:{theme.GREEN}; font-weight:850;")
        header.addWidget(self.activity_xp_lbl)
        lay.addLayout(header)
        self.activity_grid = QGridLayout()
        self.activity_grid.setHorizontalSpacing(9)
        self.activity_grid.setVerticalSpacing(9)
        lay.addLayout(self.activity_grid)
        self.root_layout.addWidget(self.activity_box)

    def _build_lower(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        trend = card()
        trend.setMinimumHeight(225)
        tl = QVBoxLayout(trend)
        tl.setContentsMargins(14, 12, 14, 12)
        t = QLabel("PERFORMANCE TREND")
        t.setObjectName("SectionTitle")
        self.spark = Sparkline()
        leg = QLabel("Green = you  ·  dashed gray = same weekday last week")
        leg.setObjectName("Muted")
        tl.addWidget(t); tl.addWidget(self.spark); tl.addWidget(leg)
        row.addWidget(trend, 4)

        insight = card()
        insight.setMinimumHeight(225)
        il = QVBoxLayout(insight)
        il.setContentsMargins(14, 12, 14, 12)
        i = QLabel("INSIGHT")
        i.setObjectName("SectionTitle")
        self.insight_lbl = QLabel("Building enough history to find patterns.")
        self.insight_lbl.setWordWrap(True)
        self.insight_lbl.setAlignment(Qt.AlignTop)
        self.insight_lbl.setStyleSheet(f"color:{theme.TEXT_2}; font-size:13px;")
        more = QPushButton("EXPLORE INSIGHTS")
        more.clicked.connect(lambda: self.request_page.emit("insights"))
        il.addWidget(i); il.addWidget(self.insight_lbl); il.addStretch(1); il.addWidget(more)
        row.addWidget(insight, 3)

        record = card()
        record.setMinimumHeight(225)
        rl = QVBoxLayout(record)
        rl.setContentsMargins(14, 12, 14, 12)
        r = QLabel("RECORD CHASE")
        r.setStyleSheet(f"color:{theme.GOLD}; font-size:15px; font-weight:850;")
        self.record_nums = QLabel("0 / 0 XP")
        self.record_nums.setStyleSheet("font-size:22px; font-weight:900;")
        self.record_progress = SmoothProgressBar(); self.record_progress.setRange(0, 1000)
        self.record_progress.setTextVisible(False)
        self.record_progress.setStyleSheet(
            f"QProgressBar::chunk {{ background:{theme.GOLD}; border-radius:4px; }}")
        self.record_text = QLabel("")
        self.record_text.setObjectName("Secondary")
        self.record_text.setWordWrap(True)
        self.record_plan = QLabel("")
        self.record_plan.setWordWrap(True)
        self.record_plan.setStyleSheet(f"color:{theme.MUTED};")
        rl.addWidget(r); rl.addWidget(self.record_nums); rl.addWidget(self.record_progress)
        rl.addWidget(self.record_text); rl.addWidget(self.record_plan); rl.addStretch(1)
        row.addWidget(record, 3)
        self.root_layout.addLayout(row)

    # ── interaction ───────────────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._activity_widgets:
            self._reflow_activities()

    def set_mode(self, mode):
        self.mode = "weekly" if mode == "weekly" else "daily"
        self.daily_btn.setChecked(self.mode == "daily")
        self.weekly_btn.setChecked(self.mode == "weekly")
        self.battle_title.setText("WEEKLY CAMPAIGN" if self.mode == "weekly" else "DAILY FIGHT")
        self.refresh()

    def _activity_columns(self):
        width = max(0, self.viewport().width() - 72)
        count = max(1, len(self._activity_widgets))
        if width >= 1120:
            return min(5, count)
        if width >= 900:
            return min(4, count)
        if width >= 690:
            return min(3, count)
        return min(2, count)

    def _reflow_activities(self):
        # Remove layout ownership only; the widgets remain alive and get re-added.
        while self.activity_grid.count():
            self.activity_grid.takeAt(0)
        cols = self._activity_columns()
        for idx, widget in enumerate(self._activity_widgets):
            self.activity_grid.addWidget(widget, idx // cols, idx % cols)
        for c in range(cols):
            self.activity_grid.setColumnStretch(c, 1)

    def _clear_activities(self):
        while self.activity_grid.count():
            item = self.activity_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._activity_widgets = []
        self._activity_by_id = {}

    def _activity_anchor(self, aid):
        widget = self._activity_by_id.get(int(aid))
        if widget is not None:
            try:
                return widget.mapTo(self.viewport(), widget.rect().center())
            except Exception:
                pass
        try:
            return self.activity_box.mapTo(self.viewport(), self.activity_box.rect().center())
        except Exception:
            return QPoint(max(40, self.viewport().width() // 2), 320)

    def _show_xp_flyup(self, score_xp, anchor=None, accent=None, text=None):
        score_xp = int(score_xp or 0)
        if score_xp == 0:
            return
        anchor = anchor or QPoint(max(40, self.viewport().width() // 2), 320)
        good = score_xp > 0
        accent = accent or (theme.GREEN if good else theme.RED)
        text = text or f"{score_xp:+,} XP"
        lbl = QLabel(text, self.viewport())
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setStyleSheet(
            f"background:rgba(8,11,14,220); color:{accent}; border:1px solid {accent}; "
            "border-radius:10px; padding:7px 11px; font-size:14px; font-weight:900;")
        lbl.adjustSize()
        start = QPoint(int(anchor.x() - lbl.width()/2), int(anchor.y() - lbl.height()/2))
        end = start + QPoint(0, -58 if good else -42)
        lbl.move(start); lbl.show(); lbl.raise_()

        effect = QGraphicsOpacityEffect(lbl); effect.setOpacity(1.0); lbl.setGraphicsEffect(effect)
        group = QParallelAnimationGroup(lbl)
        move = QPropertyAnimation(lbl, b"pos", group)
        move.setDuration(760); move.setStartValue(start); move.setEndValue(end)
        move.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade = QPropertyAnimation(effect, b"opacity", group)
        fade.setDuration(760); fade.setStartValue(1.0); fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InCubic)
        group.finished.connect(lbl.deleteLater)
        lbl._feedback_anim = group
        group.start()

    def _show_banner(self, text, accent=None, kind="win", subtitle=""):
        if self._banner is not None:
            try:
                self._banner.deleteLater()
            except Exception:
                pass
        accent = accent or theme.GREEN
        bg = theme.GOLD_DARK if kind in ("record", "level") else (theme.RED_DARK if kind == "danger" else theme.GREEN_DARK)
        body = str(text).upper()
        if subtitle:
            body += "\n" + str(subtitle).upper()
        lbl = QLabel(body, self.viewport())
        self._banner = lbl
        lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size = 16 if kind in ("record", "level") else 14
        pad_v = 13 if kind in ("record", "level") else 10
        lbl.setStyleSheet(
            f"background:{bg}; color:{accent}; border:1px solid {accent}; "
            f"border-radius:12px; padding:{pad_v}px 24px; font-size:{size}px; "
            "font-weight:900; letter-spacing:0.6px;")
        lbl.adjustSize()
        try:
            top = self.battle_box.mapTo(self.viewport(), QPoint(0, 0)).y() + 18
        except Exception:
            top = 135
        final_pos = QPoint(max(10, int((self.viewport().width()-lbl.width())/2)), max(10, top))
        start_pos = final_pos + QPoint(0, -9)
        lbl.move(start_pos)
        effect = QGraphicsOpacityEffect(lbl); effect.setOpacity(0.0); lbl.setGraphicsEffect(effect)
        lbl.show(); lbl.raise_()

        seq = QSequentialAnimationGroup(lbl)
        intro = QParallelAnimationGroup(seq)
        fade_in = QPropertyAnimation(effect, b"opacity", intro)
        fade_in.setDuration(150); fade_in.setStartValue(0.0); fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        settle = QPropertyAnimation(lbl, b"pos", intro)
        settle.setDuration(190); settle.setStartValue(start_pos); settle.setEndValue(final_pos)
        settle.setEasingCurve(QEasingCurve.Type.OutCubic)
        intro.addAnimation(fade_in); intro.addAnimation(settle)
        pause = QPauseAnimation(1250 if kind in ("record", "level") else 900, seq)
        fade_out = QPropertyAnimation(effect, b"opacity", seq)
        fade_out.setDuration(340); fade_out.setStartValue(1.0); fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        seq.addAnimation(intro); seq.addAnimation(pause); seq.addAnimation(fade_out)
        seq.finished.connect(lbl.deleteLater)
        lbl._feedback_anim = seq
        seq.start()

    def _show_milestone_if_needed(self, before, after):
        if not before or not after:
            return
        blevel, alevel = before.get("level", {}), after.get("level", {})
        if int(alevel.get("current_level", 1)) > int(blevel.get("current_level", 1)):
            self.avatar.celebrate()
            audio.play("level")
            self._show_banner(
                "LEVEL UP", theme.GOLD, "level",
                f"LV. {alevel.get('current_level')} {str(alevel.get('name', '')).upper()}")
            return
        brec, arec = before.get("records", {}), after.get("records", {})
        if not brec.get("daily_record_broken") and arec.get("daily_record_broken"):
            audio.play("record")
            self._show_banner("NEW DAILY RECORD", theme.GOLD, "record",
                              f"{int(arec.get('current_daily', 0)):,} XP")
            return
        bd, ad = before.get("daily_battle", {}), after.get("daily_battle", {})
        if int(bd.get("gap", 0)) <= 0 < int(ad.get("gap", 0)):
            audio.play("overtake")
            self._show_banner("GHOST OVERTAKEN", theme.GREEN, "win", "YOU HAVE THE LEAD")
            return
        bw, aw = before.get("weekly_campaign", {}), after.get("weekly_campaign", {})
        if int(bw.get("gap", 0)) <= 0 < int(aw.get("gap", 0)):
            audio.play("overtake")
            self._show_banner("WEEKLY LEAD TAKEN", theme.GREEN, "win")

    def _apply_battle_state(self, status):
        state = str(status or "tied").lower()
        if state == self._battle_state:
            return
        self._battle_state = state
        if state in ("ahead", "won"):
            border = "#2d7241"
        elif state in ("behind", "lost"):
            border = "#71363b"
        else:
            border = theme.BORDER_STRONG
        self.battle_box.setStyleSheet(
            "QFrame#CardStrong {"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #12191e,stop:1 #0d1216);"
            f"border:1px solid {border}; border-radius:16px;"
            "}")

    def _act(self, aid, action):
        before = self._snap
        anchor = self._activity_anchor(aid)
        try:
            if action == "minutes":
                event = game_engine.record_activity(aid, minutes=15)
            else:
                event = game_engine.record_activity(aid)
        except game_engine.ActivityAlreadyCompleted:
            return

        # Feedback is created BEFORE any dashboard recalculation. Then the slot
        # returns to Qt so the paint/animation loop gets a frame immediately.
        if event:
            score_xp = int(event.get("score_xp", 0) or 0)
            self._show_xp_flyup(score_xp, anchor)
            self.battle_bar.impact(theme.GREEN if score_xp >= 0 else theme.RED)
            if score_xp > 0:
                audio.play("xp")
        card_widget = self._activity_by_id.get(int(aid))
        if card_widget is not None:
            card_widget.flash_success()
        self.changed.emit()
        QTimer.singleShot(0, lambda b=before: self._finish_action_refresh(b))

    def _undo(self, aid):
        before = self._snap
        anchor = self._activity_anchor(aid)
        try:
            event = game_engine.undo_last_activity(aid)
        except game_engine.NothingToUndo:
            return
        if event:
            score_xp = int(event.get("score_xp", 0) or 0)
            self._show_xp_flyup(score_xp, anchor)
            self.battle_bar.impact(theme.RED)
        self.changed.emit()
        QTimer.singleShot(0, lambda b=before: self._finish_action_refresh(b))

    def _finish_action_refresh(self, before):
        # Fast refresh updates battle/level/activity numbers only. Hidden pages
        # refresh lazily when opened; expensive correlation text is not recomputed
        # for every click.
        self.refresh(include_slow=False)
        self._show_milestone_if_needed(before, self._snap)

    def live_refresh(self):
        """Cheap timer path used by the shell every two seconds."""
        self.refresh(include_slow=False)

    def _top_insight(self):
        try:
            out = game_analytics.correlations(days=60)
            if not out.get("ready"):
                return f"{out.get('tracked_days', 0)}/{out.get('minimum_days', 7)} days collected."
            corr = out.get("correlations", [])
            if not corr:
                return "Enough history exists, but no useful varying signal ranks yet."
            x = corr[0]
            return (f"{x['label']}: {x['association']}.\n\n"
                    f"Observed over {x['sample_days']} days · {x['strength']} association.")
        except Exception as ex:
            return f"Insights unavailable: {ex}"

    def _record_plan_text(self, remaining, activities):
        """A small, non-prescriptive translation of XP remaining into actions.

        This does not change score math. It only uses configured Activity values so
        the record card can answer 'what would close this gap?' in human terms.
        """
        remaining = max(0, int(remaining or 0))
        if remaining <= 0:
            return "Record secured. Keep widening the margin."

        options = []
        for a in activities:
            xp = int(a.get("xp_value", 0) or 0)
            if xp <= 0:
                continue
            kind = a.get("kind")
            today = a.get("today", {})
            if kind == "once_daily" and today.get("complete"):
                continue
            step_xp = max(1, int(round(xp / 4))) if kind == "timed" else xp
            label = f"15m {a['name']}" if kind == "timed" else a["name"]
            options.append((step_xp, label, kind))
        if not options:
            return "Configure an Activity to translate the remaining XP into a next action."

        options.sort(reverse=True)
        scalable = [x for x in options if x[2] != "once_daily"]
        high_xp, high_name, high_kind = options[0]

        # Once-daily Activities can only appear once in a suggested path.
        if not scalable:
            if high_xp >= remaining:
                return f"Example path: complete {high_name}."
            return (f"Complete {high_name} for +{high_xp:,} XP; a repeatable or timed "
                    "Activity would make the rest of the record chase actionable.")

        # Prefer the largest scalable action as the main lever.
        high_xp, high_name, high_kind = scalable[0]
        high_count = max(1, math.ceil(remaining / high_xp))
        if len(scalable) == 1:
            return f"Example path: {high_count} × {high_name}."

        # Prefer one large action plus enough of the smallest scalable step to
        # close the remainder; this tends to read naturally (booking + calls).
        low_xp, low_name, _ = min(scalable, key=lambda x: x[0])
        if high_xp < remaining and low_xp < high_xp:
            rest = max(0, remaining - high_xp)
            low_count = math.ceil(rest / low_xp)
            if low_count > 0:
                return f"Example path: 1 × {high_name} + {low_count} × {low_name}."
        return f"Example path: {high_count} × {high_name}."

    # ── backend binding ────────────────────────────────────────────────
    def refresh(self, include_slow=True):
        previous_snap = self._snap
        try:
            snap = game_engine.dashboard_snapshot()
        except Exception as ex:
            self.battle_meta.setText(f"Backend error: {ex}")
            return
        self._snap = snap
        battle = snap["daily_battle"] if self.mode == "daily" else snap["weekly_campaign"]
        you, ghost, gap = int(battle["you"]), int(battle["ghost"]), int(battle["gap"])
        status = str(battle.get("status", "tied")).lower()
        fight = theme.GREEN if gap > 0 else (theme.RED if gap < 0 else theme.TEXT_2)
        self.you_lbl.set_number(you, " XP")
        self.you_lbl.setStyleSheet(f"color:{fight}; font-size:37px; font-weight:900;")
        self.ghost_lbl.set_number(ghost, " XP")
        self.gap_lbl.set_number(gap, " XP", signed=True)
        self.gap_lbl.setStyleSheet(f"font-size:33px; font-weight:900; color:{fight};")
        self.status_lbl.setText(status.upper())
        self.status_lbl.setStyleSheet(f"font-size:12px; font-weight:850; color:{fight};")
        self._apply_battle_state(status)

        # The Ghost is a replay, not a static target. When a historical event
        # reaches the same clock time, surface it as a quiet gray score event.
        if previous_snap is not None:
            old_daily = previous_snap.get("daily_battle", {})
            new_daily = snap.get("daily_battle", {})
            old_ghost = int(old_daily.get("ghost", 0) or 0)
            new_ghost = int(new_daily.get("ghost", 0) or 0)
            if new_ghost > old_ghost:
                try:
                    anchor = self.ghost_lbl.mapTo(self.viewport(), self.ghost_lbl.rect().center())
                except Exception:
                    anchor = QPoint(max(40, self.viewport().width()-180), 220)
                delta = new_ghost - old_ghost
                self._show_xp_flyup(delta, anchor, theme.GHOST, f"GHOST +{delta:,} XP")
            old_gap = int(old_daily.get("gap", 0) or 0)
            new_gap = int(new_daily.get("gap", 0) or 0)
            if old_gap >= 0 > new_gap:
                # Passive Ghost replay may advance while the person is not touching
                # the app. Keep the visual warning, but never make unsolicited
                # periodic noise from a timer refresh.
                self._show_banner("GHOST TOOK THE LEAD", theme.RED, "danger")

        if self.mode == "daily":
            meta = f"Same clock vs {battle.get('ghost_day', 'last week')} · {battle.get('same_clock', '')}"
            ghost_final = battle.get("ghost_final", 0)
        else:
            meta = f"Current week to now vs week of {battle.get('ghost_week_start', '')}"
            ghost_final = battle.get("ghost", 0)
        self.battle_meta.setText(meta)

        rec = snap["records"]
        record_target = int(rec.get("daily_all_time_before", 0))
        self.battle_bar.set_values(
            you, ghost, ghost_final, record_target if self.mode == "daily" else 0)

        lvl = snap["level"]
        self.avatar.set_level(lvl["current_level"], lvl["name"])
        self.level_lbl.setText(f"LV. {lvl['current_level']}  {lvl['name'].upper()}")
        if lvl.get("next_threshold"):
            start = int(lvl.get("entry_threshold", 0))
            end = int(lvl["next_threshold"])
            val = int(lvl["rating"])
            frac = (val-start) / max(1, end-start)
            pct = max(0, min(100, int(round(frac * 100))))
            self.level_progress.set_target_value(max(0, min(1000, int(frac*1000))))
            self.level_detail.setText(
                f"{val:,} rolling XP · {pct}% conquered · {lvl['xp_to_next']:,} to next level")
        else:
            self.level_progress.set_target_value(1000)
            self.level_detail.setText(f"{lvl['rating']:,} rolling XP · Sovereign tier")
        if lvl.get("at_risk"):
            self.level_detail.setStyleSheet(f"color:{theme.RED};")
        elif lvl.get("comeback_active"):
            self.level_detail.setStyleSheet(f"color:{theme.GREEN};")
        else:
            self.level_detail.setStyleSheet(f"color:{theme.TEXT_2};")
        self.rating_badge.set_values("RATING", f"{lvl['rating']:,} XP", theme.GOLD)
        ds = snap["streaks"]["daily"]
        live_extra = 1 if ds.get("live_ahead") else 0
        self.streak_badge.set_values(
            "DAY STREAK", str(int(ds.get("completed", 0)) + live_extra), theme.GREEN)
        self.week_badge.set_values(
            "WEEK STREAK", str(snap["streaks"].get("weekly_completed", 0)), theme.TEXT)

        self.activity_xp_lbl.setText(f"TODAY {rec['current_daily']:,} XP")
        record_map = {r["activity_id"]: r for r in rec.get("activity_records", [])}
        acts = snap.get("activities", [])
        signature = tuple(
            (int(a["id"]), str(a.get("name", "")), int(a.get("xp_value", 0) or 0),
             str(a.get("kind", "repeatable"))) for a in acts)
        if signature != self._activity_signature:
            self._clear_activities()
            for a in acts:
                w = ActivityCard(a, record_map.get(a["id"]))
                w.action.connect(self._act)
                w.undo.connect(self._undo)
                self._activity_widgets.append(w)
                self._activity_by_id[int(a["id"])] = w
            self._activity_signature = signature
            self._reflow_activities()
        else:
            for a in acts:
                w = self._activity_by_id.get(int(a["id"]))
                if w is not None:
                    w.update_data(a, record_map.get(a["id"]))

        # The line chart is inexpensive and should reflect today's score live.
        self.spark.set_rows(game_engine.performance_series(14))
        # Correlation analysis is useful but does not need to rerun every two
        # seconds or on every +1. Refresh it on page entry/full refresh only.
        if include_slow:
            self.insight_lbl.setText(self._top_insight())

        if rec.get("daily_record_broken"):
            self.record_nums.setText(f"{rec['current_daily']:,} XP · NEW RECORD")
            self.record_progress.set_target_value(1000)
            self.record_text.setText("You are above the previous all-time daily high.")
            self.record_plan.setText("Keep scoring to make tomorrow's Ghost harder to beat.")
        elif record_target > 0:
            frac = rec["current_daily"] / max(1, record_target)
            self.record_progress.set_target_value(max(0, min(1000, int(frac*1000))))
            self.record_nums.setText(f"{rec['current_daily']:,} / {record_target:,} XP")
            self.record_text.setText(f"{rec['daily_remaining']:,} XP to beat your daily record.")
            self.record_plan.setText(self._record_plan_text(rec["daily_remaining"], acts))
        else:
            self.record_progress.set_target_value(0)
            self.record_nums.setText(f"{rec['current_daily']:,} XP")
            self.record_text.setText("Your first scored day will establish the record.")
            self.record_plan.setText("")
