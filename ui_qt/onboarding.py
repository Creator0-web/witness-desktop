"""First-run onboarding for the installed Qt WITNESS app.

This is intentionally local-only. It creates no account and does not infer XP.
The person chooses their own starter Activities; the canonical game engine still
owns all scoring after setup.
"""
from __future__ import annotations

import db
import game_engine

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from . import theme
from .widgets import card

ONBOARDING_KEY = "onboarding_complete_v1"
PLAYER_NAME_KEY = "player_name_v1"
PLAYER_MISSION_KEY = "player_mission_v1"


def should_show() -> bool:
    if db.game_state_get(ONBOARDING_KEY, "0") == "1":
        return False
    # Existing accounts should not suddenly be forced through first-run setup.
    if game_engine.list_activities(False):
        db.game_state_set(ONBOARDING_KEY, "1")
        return False
    return True


def mark_incomplete():
    db.game_state_set(ONBOARDING_KEY, "0")


class OnboardingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to WITNESS")
        self.setMinimumSize(760, 590)
        self.resize(820, 630)
        self.setStyleSheet(theme.APP_STYLESHEET)
        self._step = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 22)
        outer.setSpacing(14)

        top = QHBoxLayout()
        brand = QLabel("WITNESS")
        brand.setStyleSheet("font-size:25px;font-weight:900;letter-spacing:2px;")
        self.step_label = QLabel("1 / 3")
        self.step_label.setObjectName("Eyebrow")
        top.addWidget(brand); top.addStretch(1); top.addWidget(self.step_label)
        outer.addLayout(top)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._identity_page())
        self.stack.addWidget(self._activities_page())
        self.stack.addWidget(self._ghost_page())
        outer.addWidget(self.stack, 1)

        nav = QHBoxLayout()
        self.back_btn = QPushButton("BACK")
        self.back_btn.clicked.connect(self._back)
        self.skip_btn = QPushButton("SKIP FOR NOW")
        self.skip_btn.clicked.connect(self.reject)
        self.next_btn = QPushButton("NEXT")
        self.next_btn.setObjectName("Primary")
        self.next_btn.clicked.connect(self._next)
        nav.addWidget(self.back_btn); nav.addStretch(1); nav.addWidget(self.skip_btn); nav.addWidget(self.next_btn)
        outer.addLayout(nav)
        self._sync_nav()

    def _title(self, title: str, subtitle: str, layout: QVBoxLayout):
        h = QLabel(title)
        h.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("Muted"); s.setWordWrap(True)
        layout.addWidget(h); layout.addWidget(s)

    def _identity_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(4, 12, 4, 4); lay.setSpacing(14)
        self._title("Who are you becoming?",
                    "No account is created. These words stay inside this Windows user's local WITNESS profile.", lay)
        c = card(strong=True); cl = QVBoxLayout(c); cl.setContentsMargins(18, 16, 18, 18); cl.setSpacing(8)
        n = QLabel("NAME / CALLSIGN"); n.setObjectName("Eyebrow")
        self.name_edit = QLineEdit(str(db.game_state_get(PLAYER_NAME_KEY, "") or ""))
        self.name_edit.setPlaceholderText("Your name")
        m = QLabel("MISSION"); m.setObjectName("Eyebrow")
        self.mission_edit = QTextEdit()
        self.mission_edit.setMaximumHeight(110)
        self.mission_edit.setPlaceholderText("What are you trying to become or build?")
        self.mission_edit.setPlainText(str(db.game_state_get(PLAYER_MISSION_KEY, "") or ""))
        cl.addWidget(n); cl.addWidget(self.name_edit); cl.addSpacing(8); cl.addWidget(m); cl.addWidget(self.mission_edit)
        lay.addWidget(c); lay.addStretch(1)
        return page

    def _activities_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(4, 12, 4, 4); lay.setSpacing(12)
        self._title("Build your first score",
                    "You decide what deserves XP. Repeatable = each completion, once daily = one win per day, timed = XP per hour.", lay)
        self.activity_rows = []
        defaults = [
            ("Primary Work", 100, "repeatable"),
            ("Focus Work", 100, "timed"),
            ("Workout Complete", 200, "once_daily"),
        ]
        for idx, (name, xp, kind) in enumerate(defaults, 1):
            c = card(); row = QHBoxLayout(c); row.setContentsMargins(14, 11, 14, 11); row.setSpacing(8)
            num = QLabel(str(idx)); num.setObjectName("Eyebrow"); num.setFixedWidth(20)
            edit = QLineEdit(name); edit.setMinimumWidth(250)
            spin = QSpinBox(); spin.setRange(0, 1000000); spin.setValue(xp); spin.setSuffix(" XP")
            combo = QComboBox(); combo.addItems(["repeatable", "once_daily", "timed"]); combo.setCurrentText(kind)
            row.addWidget(num); row.addWidget(edit, 1); row.addWidget(spin); row.addWidget(combo)
            lay.addWidget(c); self.activity_rows.append((edit, spin, combo))
        note = QLabel("You can edit or delete these later in SETTINGS. Leave a name blank to skip that row.")
        note.setObjectName("Muted"); note.setWordWrap(True); lay.addWidget(note); lay.addStretch(1)
        return page

    def _ghost_page(self):
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(4, 12, 4, 4); lay.setSpacing(14)
        self._title("You versus you",
                    "WITNESS is a self-competition game. Your actions create the score; your past performance becomes the opponent.", lay)
        c = card(strong=True); cl = QVBoxLayout(c); cl.setContentsMargins(20, 18, 20, 18); cl.setSpacing(12)
        for head, body in (
            ("DAILY FIGHT", "Today's XP races the same weekday from one week ago at the same clock time."),
            ("WEEKLY CAMPAIGN", "This Monday-through-now races the equivalent part of last week."),
            ("LEVEL", "Your 14-day rolling performance evolves the Character from Wanderer toward Sovereign."),
            ("CHARACTER", "Level is who you've become. Daily Charge is today's output. Core Reserve and Shield are separate current-state systems."),
        ):
            h = QLabel(head); h.setObjectName("SectionTitle")
            b = QLabel(body); b.setObjectName("Secondary"); b.setWordWrap(True)
            cl.addWidget(h); cl.addWidget(b)
        lay.addWidget(c); lay.addStretch(1)
        return page

    def _sync_nav(self):
        self.stack.setCurrentIndex(self._step)
        self.step_label.setText(f"{self._step + 1} / 3")
        self.back_btn.setEnabled(self._step > 0)
        self.next_btn.setText("ENTER ARENA" if self._step == 2 else "NEXT")
        self.skip_btn.setVisible(self._step < 2)

    def _back(self):
        self._step = max(0, self._step - 1); self._sync_nav()

    def _next(self):
        if self._step < 2:
            self._step += 1; self._sync_nav(); return
        self._finish()

    def _finish(self):
        db.game_state_set(PLAYER_NAME_KEY, self.name_edit.text().strip())
        db.game_state_set(PLAYER_MISSION_KEY, self.mission_edit.toPlainText().strip()[:1200])
        existing = {a["name"].casefold(): a for a in game_engine.list_activities(False)}
        order = len(existing)
        for edit, spin, combo in self.activity_rows:
            name = edit.text().strip()
            if not name:
                continue
            old = existing.get(name.casefold())
            if old:
                game_engine.update_activity(old["id"], name=name, xp_value=spin.value(),
                                            kind=combo.currentText(), active=True)
            else:
                game_engine.create_activity(name, spin.value(), combo.currentText(), True, order)
                order += 1
        db.game_state_set(ONBOARDING_KEY, "1")
        self.accept()
