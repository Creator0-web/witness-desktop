from __future__ import annotations

import calendar as pycalendar
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QApplication, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QInputDialog,
    QScrollArea, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget,
)

import day_breakdown
import db
import demo_data
import game_analytics
import game_engine
import video_memories
import profile_runtime

from . import audio, onboarding, theme
from .protection_runtime import open_sos_folder, sos_videos
from .widgets import card, clear_layout
from .progression import ProgressionView


class SimplePage(QScrollArea):
    def __init__(self, title, parent=None, subtitle=""):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget(); self.setWidget(self.body)
        self.layout_ = QVBoxLayout(self.body)
        self.layout_.setContentsMargins(20, 18, 20, 22)
        self.layout_.setSpacing(12)
        hrow = QHBoxLayout()
        h = QLabel(title.upper())
        h.setObjectName("PageTitle")
        hrow.addWidget(h)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("Muted")
            hrow.addWidget(s)
        hrow.addStretch(1)
        self.layout_.addLayout(hrow)


def _table(columns, stretch_last=True):
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_last and columns:
        t.horizontalHeader().setSectionResizeMode(len(columns)-1, QHeaderView.ResizeMode.Stretch)
    return t


def _set_item(table, row, col, text, color=None, align=None):
    item = QTableWidgetItem(str(text))
    if color:
        from PySide6.QtGui import QColor
        item.setForeground(QColor(color))
    if align is not None:
        item.setTextAlignment(align)
    table.setItem(row, col, item)


class DayDetailPanel(QFrame):
    """Rich Qt view of one calendar day using existing local storage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CardStrong")
        self.day = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(10)

        head = QHBoxLayout()
        titles = QVBoxLayout(); titles.setSpacing(2)
        self.day_title = QLabel("SELECT A DAY")
        self.day_title.setStyleSheet("font-size:18px; font-weight:900;")
        self.day_sub = QLabel("Score, computer history, notes and videos live together here.")
        self.day_sub.setObjectName("Muted")
        titles.addWidget(self.day_title); titles.addWidget(self.day_sub)
        head.addLayout(titles, 1)
        self.day_score = QLabel("0 XP")
        self.day_score.setStyleSheet("font-size:26px; font-weight:900;")
        head.addWidget(self.day_score, 0, Qt.AlignRight | Qt.AlignVCenter)
        outer.addLayout(head)

        self.tabs = QTabWidget()
        self.overview_tab = QWidget(); self.computer_tab = QWidget()
        self.notes_tab = QWidget(); self.videos_tab = QWidget()
        self.tabs.addTab(self.overview_tab, "OVERVIEW")
        self.tabs.addTab(self.computer_tab, "COMPUTER")
        self.tabs.addTab(self.notes_tab, "NOTES")
        self.tabs.addTab(self.videos_tab, "VIDEOS")
        outer.addWidget(self.tabs)

        self._build_overview()
        self._build_computer()
        self._build_notes()
        self._build_videos()
        self.setEnabled(False)

    def _build_overview(self):
        lay = QVBoxLayout(self.overview_tab)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(10)
        self.metric_row = QHBoxLayout(); lay.addLayout(self.metric_row)

        split = QHBoxLayout(); split.setSpacing(10)
        left = QVBoxLayout(); right = QVBoxLayout()
        a = QLabel("ACTIVITY BREAKDOWN"); a.setObjectName("SectionTitle")
        self.activity_table = _table(["ACTIVITY", "UNITS", "XP"])
        self.activity_table.setMinimumHeight(185)
        left.addWidget(a); left.addWidget(self.activity_table)
        t = QLabel("XP TIMELINE"); t.setObjectName("SectionTitle")
        self.timeline_table = _table(["TIME", "ACTION", "XP", "RUNNING"])
        self.timeline_table.setMinimumHeight(185)
        right.addWidget(t); right.addWidget(self.timeline_table)
        split.addLayout(left, 2); split.addLayout(right, 3)
        lay.addLayout(split)

    def _build_computer(self):
        lay = QVBoxLayout(self.computer_tab)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)
        top = QHBoxLayout()
        self.computer_status = QLabel("No day selected.")
        self.computer_status.setObjectName("Secondary")
        top.addWidget(self.computer_status); top.addStretch(1)
        self.build_computer_btn = QPushButton("Build from Activity Log")
        self.build_computer_btn.clicked.connect(self.build_computer_history)
        self.build_computer_btn.hide()
        top.addWidget(self.build_computer_btn)
        lay.addLayout(top)
        self.computer_table = _table(["TIME", "DOMINANT", "SUMMARY", "TOP APPS"])
        self.computer_table.setMinimumHeight(300)
        lay.addWidget(self.computer_table)

    def _build_notes(self):
        lay = QVBoxLayout(self.notes_tab)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(9)
        intro = QLabel("Notes belong to the selected calendar day. Add context you will want when you look back later.")
        intro.setObjectName("Secondary"); intro.setWordWrap(True)
        lay.addWidget(intro)
        self.note_list = QVBoxLayout(); self.note_list.setSpacing(7)
        lay.addLayout(self.note_list)
        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Write a note for this day…")
        self.note_input.setMinimumHeight(88); self.note_input.setMaximumHeight(120)
        lay.addWidget(self.note_input)
        row = QHBoxLayout(); row.addStretch(1)
        save = QPushButton("ADD NOTE"); save.setObjectName("Primary")
        save.clicked.connect(self.add_note)
        row.addWidget(save); lay.addLayout(row)

    def _build_videos(self):
        lay = QVBoxLayout(self.videos_tab)
        lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(9)
        top = QHBoxLayout()
        intro = QLabel("Attach real videos to this day. Files stay local inside WITNESS history.")
        intro.setObjectName("Secondary"); intro.setWordWrap(True)
        top.addWidget(intro, 1)
        add = QPushButton("+ ADD VIDEO"); add.setObjectName("Primary")
        add.clicked.connect(self.add_video)
        top.addWidget(add)
        lay.addLayout(top)
        self.video_list = QVBoxLayout(); self.video_list.setSpacing(7)
        lay.addLayout(self.video_list)
        lay.addStretch(1)

    def _metric(self, title, value, accent=None):
        f = QFrame(); f.setObjectName("MetricTile")
        l = QVBoxLayout(f); l.setContentsMargins(12, 9, 12, 9); l.setSpacing(2)
        a = QLabel(title.upper()); a.setObjectName("Eyebrow")
        b = QLabel(value); b.setStyleSheet(
            f"font-size:18px; font-weight:900; color:{accent or theme.TEXT};")
        l.addWidget(a); l.addWidget(b)
        return f

    def set_day(self, d):
        self.day = d if isinstance(d, date) else date.fromisoformat(str(d))
        self.setEnabled(True)
        self.refresh()

    def refresh(self):
        if not self.day:
            return
        dstr = self.day.isoformat()
        g = game_engine.day_summary(self.day)
        notes = db.notes_for_day(dstr)
        videos = video_memories.videos_for_day(dstr)
        winning = int(g["gap_final"]) >= 0
        accent = theme.GREEN if winning else theme.RED
        self.day_title.setText(self.day.strftime("%A, %B %d, %Y").upper())
        flags = []
        if g.get("was_record_day"): flags.append("DAILY RECORD")
        if g.get("was_record_week"): flags.append("RECORD WEEK")
        if notes: flags.append(f"{len(notes)} NOTE{'S' if len(notes)!=1 else ''}")
        if videos: flags.append(f"{len(videos)} VIDEO{'S' if len(videos)!=1 else ''}")
        self.day_sub.setText("  ·  ".join(flags) if flags else "Saved daily history")
        self.day_score.setText(f"{g['score_xp']:,} XP")
        self.day_score.setStyleSheet(f"font-size:26px; font-weight:900; color:{accent};")

        clear_layout(self.metric_row)
        self.metric_row.addWidget(self._metric("Score", f"{g['score_xp']:,} XP", accent), 1)
        self.metric_row.addWidget(self._metric("Ghost", f"{g['ghost_final_xp']:,} XP", theme.GHOST), 1)
        self.metric_row.addWidget(self._metric(
            "Final Gap", f"{g['gap_final']:+,} XP", accent), 1)
        record_text = "YES" if g.get("was_record_day") else "—"
        self.metric_row.addWidget(self._metric("Record Day", record_text,
                                                theme.GOLD if g.get("was_record_day") else theme.MUTED), 1)

        breakdown = g.get("activity_breakdown", [])
        self.activity_table.clearSpans()
        self.activity_table.setRowCount(len(breakdown))
        for row, x in enumerate(breakdown):
            units = float(x.get("units", 0) or 0)
            _set_item(self.activity_table, row, 0, x.get("name", ""))
            _set_item(self.activity_table, row, 1,
                      f"{int(units) if units.is_integer() else units:g}", align=Qt.AlignCenter)
            _set_item(self.activity_table, row, 2, f"{int(x.get('score_xp', 0)):,} XP",
                      theme.GREEN, Qt.AlignRight | Qt.AlignVCenter)
        if not breakdown:
            self.activity_table.setRowCount(1)
            _set_item(self.activity_table, 0, 0, "No scored Activities")
            self.activity_table.setSpan(0, 0, 1, 3)

        timeline = g.get("timeline", [])
        self.timeline_table.clearSpans()
        self.timeline_table.setRowCount(len(timeline))
        for row, x in enumerate(timeline):
            xp = int(x.get("score_xp", 0))
            _set_item(self.timeline_table, row, 0, x.get("clock", ""))
            _set_item(self.timeline_table, row, 1, x.get("activity_name", ""))
            _set_item(self.timeline_table, row, 2, f"{xp:+,}", theme.GREEN if xp >= 0 else theme.RED,
                      Qt.AlignRight | Qt.AlignVCenter)
            _set_item(self.timeline_table, row, 3, f"{int(x.get('running_score', 0)):,}",
                      None, Qt.AlignRight | Qt.AlignVCenter)
        if not timeline:
            self.timeline_table.setRowCount(1)
            _set_item(self.timeline_table, 0, 0, "No XP events")
            self.timeline_table.setSpan(0, 0, 1, 4)

        self._refresh_computer()
        self._refresh_notes(notes)
        self._refresh_videos(videos)

    def _refresh_computer(self):
        dstr = self.day.isoformat()
        doc = day_breakdown.load_day(dstr)
        if not doc and day_breakdown.has_real_activity(dstr):
            self.computer_status.setText("Tracked activity exists, but this day's hourly summary has not been built yet.")
            self.build_computer_btn.show()
            self.computer_table.setRowCount(0)
            return
        self.build_computer_btn.hide()
        if not doc:
            self.computer_status.setText("No computer history was tracked for this day.")
            self.computer_table.setRowCount(0)
            return
        source = "SYNTHETIC PREVIEW" if doc.get("synthetic") else "TRACKED COMPUTER HISTORY"
        self.computer_status.setText(source + " · hour-by-hour activity summary")
        hours = [h for h in doc.get("hours", []) if h.get("segments") or h.get("apps")]
        self.computer_table.setRowCount(len(hours))
        for row, h in enumerate(hours):
            hour = int(h.get("hour", 0))
            start = datetime(2000, 1, 1, hour, 0).strftime("%I:%M %p").lstrip("0")
            dominant = "—"
            segments = h.get("segments", [])
            if segments:
                top_seg = max(segments, key=lambda x: x.get("pct", 0))
                dominant = f"{top_seg.get('category','Other')}  {top_seg.get('pct',0)}%"
            apps = h.get("apps", [])[:3]
            app_text = " · ".join(
                f"{a.get('name','Unknown')} ({a.get('duration_min',0)}m)" for a in apps) or "—"
            _set_item(self.computer_table, row, 0, start)
            _set_item(self.computer_table, row, 1, dominant)
            _set_item(self.computer_table, row, 2, h.get("summary", ""))
            _set_item(self.computer_table, row, 3, app_text)

    def build_computer_history(self):
        if not self.day:
            return
        try:
            day_breakdown.build_day_from_activity(self.day.isoformat())
            self._refresh_computer()
        except Exception as ex:
            QMessageBox.critical(self, "History error", str(ex))

    def _refresh_notes(self, notes=None):
        clear_layout(self.note_list)
        notes = db.notes_for_day(self.day.isoformat()) if notes is None else notes
        if not notes:
            empty = QLabel("No notes yet. Add the context that numbers cannot remember.")
            empty.setObjectName("Muted")
            self.note_list.addWidget(empty)
            return
        for ts, text in notes:
            f = QFrame(); f.setObjectName("MetricTile")
            l = QVBoxLayout(f); l.setContentsMargins(11, 8, 11, 8); l.setSpacing(3)
            clock = datetime.fromtimestamp(ts).strftime("%I:%M %p").lstrip("0")
            time_lbl = QLabel(clock); time_lbl.setObjectName("Eyebrow")
            body = QLabel(str(text)); body.setWordWrap(True)
            l.addWidget(time_lbl); l.addWidget(body)
            self.note_list.addWidget(f)

    def add_note(self):
        if not self.day:
            return
        text = self.note_input.toPlainText().strip()
        if not text:
            return
        try:
            db.log_note_for_day(self.day.isoformat(), text)
            self.note_input.clear()
            self.refresh()
        except Exception as ex:
            QMessageBox.critical(self, "Note error", str(ex))

    def _refresh_videos(self, videos=None):
        clear_layout(self.video_list)
        videos = video_memories.videos_for_day(self.day.isoformat()) if videos is None else videos
        if not videos:
            empty = QLabel("No videos attached to this day.")
            empty.setObjectName("Muted")
            self.video_list.addWidget(empty)
            return
        for filename in videos:
            f = QFrame(); f.setObjectName("MetricTile")
            l = QHBoxLayout(f); l.setContentsMargins(11, 8, 11, 8)
            name = QLabel(filename); name.setStyleSheet("font-weight:750;")
            l.addWidget(name, 1)
            open_btn = QPushButton("OPEN")
            path = video_memories.video_path(self.day.isoformat(), filename)
            open_btn.clicked.connect(lambda _=False, p=path: self.open_video(p))
            l.addWidget(open_btn)
            self.video_list.addWidget(f)

    def add_video(self):
        if not self.day:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Add Video to History", "",
            "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.m4v);;All Files (*)")
        if not path:
            return
        try:
            video_memories.add_video(self.day.isoformat(), path)
            self.refresh()
        except Exception as ex:
            QMessageBox.critical(self, "Video error", str(ex))

    def open_video(self, path):
        try:
            video_memories.open_video(path)
        except Exception as ex:
            QMessageBox.critical(self, "Open video", str(ex))


class CalendarPage(SimplePage):
    def __init__(self, parent=None):
        super().__init__("History", parent,
                         "Open a day like a save file, or zoom out to see your progression over time.")
        self.mode = "calendar"
        self.cursor = date.today().replace(day=1)
        self.selected_day = None

        mode_row = QHBoxLayout()
        mode_row.addStretch(1)
        self.calendar_btn = QPushButton("CALENDAR")
        self.progression_btn = QPushButton("PROGRESSION")
        self.mode_group = QButtonGroup(self); self.mode_group.setExclusive(True)
        for b in (self.calendar_btn, self.progression_btn):
            b.setObjectName("Tab"); b.setCheckable(True); self.mode_group.addButton(b)
            mode_row.addWidget(b)
        self.calendar_btn.setChecked(True)
        self.calendar_btn.clicked.connect(lambda: self.set_mode("calendar"))
        self.progression_btn.clicked.connect(lambda: self.set_mode("progression"))
        self.layout_.addLayout(mode_row)

        self.calendar_container = QWidget()
        cal = QVBoxLayout(self.calendar_container)
        cal.setContentsMargins(0, 0, 0, 0); cal.setSpacing(12)

        nav = QHBoxLayout()
        prev = QPushButton("‹ PREVIOUS")
        nxt = QPushButton("NEXT ›")
        self.month_lbl = QLabel("")
        self.month_lbl.setAlignment(Qt.AlignCenter)
        self.month_lbl.setStyleSheet("font-size:18px; font-weight:850;")
        prev.clicked.connect(lambda: self.shift(-1)); nxt.clicked.connect(lambda: self.shift(1))
        nav.addWidget(prev); nav.addWidget(self.month_lbl, 1); nav.addWidget(nxt)
        cal.addLayout(nav)

        legend = QLabel("★ daily record   ·   W record week   ·   N note   ·   V video")
        legend.setObjectName("Muted"); legend.setAlignment(Qt.AlignRight)
        cal.addWidget(legend)

        self.grid_card = card()
        self.grid = QGridLayout(self.grid_card)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setHorizontalSpacing(6); self.grid.setVerticalSpacing(6)
        cal.addWidget(self.grid_card)

        self.detail = DayDetailPanel()
        cal.addWidget(self.detail)
        cal.addStretch(1)
        self.layout_.addWidget(self.calendar_container)

        self.progression = ProgressionView()
        self.progression.hide()
        self.layout_.addWidget(self.progression)
        self.layout_.addStretch(1)
        self.refresh()

    def set_mode(self, mode):
        self.mode = "progression" if mode == "progression" else "calendar"
        is_cal = self.mode == "calendar"
        self.calendar_btn.setChecked(is_cal)
        self.progression_btn.setChecked(not is_cal)
        self.calendar_container.setVisible(is_cal)
        self.progression.setVisible(not is_cal)
        self.refresh()

    def shift(self, delta):
        y, m = self.cursor.year, self.cursor.month + delta
        if m < 1: y, m = y-1, 12
        if m > 12: y, m = y+1, 1
        self.cursor = date(y, m, 1)
        self.refresh()

    def refresh(self):
        if self.mode == "progression":
            self.progression.refresh()
            return
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        y, m = self.cursor.year, self.cursor.month
        self.month_lbl.setText(self.cursor.strftime("%B %Y").upper())
        summary = game_engine.calendar_month_summary(y, m)
        by_num = {x["day_number"]: x for x in summary["days"]}
        note_days = db.days_with_notes_in_month(y, m)
        video_days = video_memories.days_with_videos_in_month(y, m)
        for col, wd in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
            lab = QLabel(wd); lab.setAlignment(Qt.AlignCenter); lab.setObjectName("Eyebrow")
            self.grid.addWidget(lab, 0, col)
            self.grid.setColumnStretch(col, 1)
        weeks = pycalendar.Calendar(firstweekday=0).monthdayscalendar(y, m)
        for r, week in enumerate(weeks, 1):
            self.grid.setRowStretch(r, 1)
            for c, num in enumerate(week):
                if not num:
                    self.grid.addWidget(QLabel(""), r, c)
                    continue
                info = by_num.get(num, {})
                score = int(info.get("score_xp", 0) or 0)
                markers = []
                if info.get("is_record_day"): markers.append("★")
                if info.get("is_record_week"): markers.append("W")
                if num in note_days: markers.append("N")
                if num in video_days: markers.append("V")
                marker_text = "  ·  ".join(markers)
                text = f"{num}"
                if score:
                    text += f"\n{score:,} XP"
                if marker_text:
                    text += f"\n{marker_text}"
                b = QPushButton(text)
                b.setObjectName("CalendarDay")
                b.setMinimumHeight(72)
                if markers:
                    b.setToolTip("★ record day · W record week · N note · V video")
                this_day = date(y, m, num)
                border = theme.BORDER
                color = theme.TEXT_2
                if info.get("is_record_day"):
                    border, color = theme.GOLD, theme.GOLD
                elif this_day == date.today():
                    border, color = theme.GREEN, theme.TEXT
                elif this_day == self.selected_day:
                    border, color = theme.BORDER_STRONG, theme.TEXT
                b.setStyleSheet(
                    f"QPushButton#CalendarDay {{text-align:left;background:#0d1216;"
                    f"border:1px solid {border};border-radius:10px;padding:7px 9px;color:{color};}}"
                    f"QPushButton#CalendarDay:hover {{background:#12191e;border-color:{theme.BORDER_STRONG};color:{theme.TEXT};}}")
                b.clicked.connect(lambda _=False, d=this_day: self.show_day(d))
                self.grid.addWidget(b, r, c)
        if self.selected_day:
            self.detail.set_day(self.selected_day)

    def show_day(self, d):
        self.selected_day = d
        self.detail.set_day(d)
        self.refresh()
        try:
            self.ensureWidgetVisible(self.detail, 0, 16)
        except Exception:
            pass


class RecordsPage(SimplePage):
    def __init__(self, parent=None):
        super().__init__("Records", parent, "High scores keep every day worth fighting for.")
        self.card = card(); self.card_l = QVBoxLayout(self.card)
        self.card_l.setContentsMargins(16, 14, 16, 16); self.card_l.setSpacing(8)
        self.layout_.addWidget(self.card); self.layout_.addStretch(1)
        self.refresh()

    def refresh(self):
        clear_layout(self.card_l)
        hof = game_engine.hall_of_fame()
        best_day = hof.get("best_day")
        best_week = hof.get("best_week")
        title = QLabel("HALL OF FAME"); title.setObjectName("SectionTitle"); self.card_l.addWidget(title)
        top = QHBoxLayout()
        if best_day:
            f = QFrame(); f.setObjectName("MetricTile"); l=QVBoxLayout(f)
            a=QLabel("★ BEST DAY"); a.setObjectName("Eyebrow")
            b=QLabel(f"{best_day['score_xp']:,} XP"); b.setStyleSheet(f"font-size:22px;font-weight:900;color:{theme.GOLD};")
            c=QLabel(best_day['day']); c.setObjectName("Muted")
            l.addWidget(a); l.addWidget(b); l.addWidget(c); top.addWidget(f,1)
        if best_week:
            f = QFrame(); f.setObjectName("MetricTile"); l=QVBoxLayout(f)
            a=QLabel("BEST WEEK"); a.setObjectName("Eyebrow")
            b=QLabel(f"{best_week['score_xp']:,} XP"); b.setStyleSheet("font-size:22px;font-weight:900;")
            c=QLabel(f"Week of {best_week['week_start']}"); c.setObjectName("Muted")
            l.addWidget(a); l.addWidget(b); l.addWidget(c); top.addWidget(f,1)
        self.card_l.addLayout(top)

        self.card_l.addWidget(QLabel("WEEKDAY RECORDS"))
        weekdays = _table(["DAY", "SCORE", "DATE"])
        rows = hof.get("weekday_records", [])
        weekdays.setRowCount(len(rows)); weekdays.setMaximumHeight(260)
        for r,x in enumerate(rows):
            _set_item(weekdays,r,0,x['weekday'])
            _set_item(weekdays,r,1,f"{x['score_xp']:,} XP",theme.GOLD)
            _set_item(weekdays,r,2,x['day'])
        self.card_l.addWidget(weekdays)

        self.card_l.addWidget(QLabel("ACTIVITY RECORDS"))
        acts = _table(["ACTIVITY", "BEST UNITS", "XP", "DATE"])
        rows = hof.get("activity_records", [])
        acts.setRowCount(len(rows)); acts.setMaximumHeight(300)
        for r,x in enumerate(rows):
            _set_item(acts,r,0,x['name'])
            _set_item(acts,r,1,f"{x['best_units']:g}")
            _set_item(acts,r,2,f"{x['best_score_xp']:,} XP",theme.GOLD)
            _set_item(acts,r,3,x['best_day'])
        self.card_l.addWidget(acts)


class InsightsPage(SimplePage):
    def __init__(self, parent=None):
        super().__init__("Behavior → Score Insights", parent,
                         "WITNESS studies what seems to predict the outcomes you chose to reward.")
        top = QHBoxLayout()
        top.addWidget(QLabel("Analyze against:"))
        self.target = QComboBox()
        self.target.addItem("Total Score")
        for a in game_engine.list_activities(True):
            self.target.addItem(a["name"])
        self.target.currentIndexChanged.connect(self.refresh)
        top.addWidget(self.target); top.addStretch(1)
        self.layout_.addLayout(top)
        self.results = QVBoxLayout(); self.layout_.addLayout(self.results); self.layout_.addStretch(1)
        self.refresh()

    def refresh(self):
        clear_layout(self.results)
        name = self.target.currentText() if self.target.count() else "Total Score"
        out = game_analytics.correlations(days=60, target_activity=None if name == "Total Score" else name)
        if not out.get("ready"):
            self.results.addWidget(QLabel(
                f"Need more history: {out.get('tracked_days', 0)}/{out.get('minimum_days', 7)} days."))
            return
        corr = out.get("correlations", [])
        if not corr:
            self.results.addWidget(QLabel("No sufficiently varying signals to rank yet.")); return
        for idx, x in enumerate(corr[:8], 1):
            c=card(); l=QVBoxLayout(c); l.setContentsMargins(14,11,14,11)
            h=QLabel(f"{idx}. {x['label']}"); h.setStyleSheet("font-size:16px;font-weight:850;")
            d=QLabel(f"{x['association']} · {x['strength']} · r={x['spearman_r']:+.2f} · {x['sample_days']} days")
            d.setObjectName("Secondary")
            l.addWidget(h); l.addWidget(d); self.results.addWidget(c)


class SettingsPage(SimplePage):
    preview_protection = Signal()
    test_redline = Signal()

    def __init__(self, parent=None):
        super().__init__("Settings", parent,
                         "Protection, data safety and scoring controls. Score stays manual and explicit.")
        self.status = QLabel(""); self.status.setObjectName("Secondary")
        self.layout_.addWidget(self.status)

        profile = card(); pl = QVBoxLayout(profile)
        ph = QLabel("LOCAL PROFILE"); ph.setObjectName("SectionTitle")
        pd = QLabel("No login required. This Windows account owns one isolated local WITNESS profile; updates can replace app code without touching this folder.")
        pd.setWordWrap(True); pd.setObjectName("Secondary")
        self.profile_id_label = QLabel("")
        self.profile_id_label.setStyleSheet("font-weight:800;")
        self.profile_path_label = QLabel("")
        self.profile_path_label.setObjectName("Secondary"); self.profile_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.profile_pending_label = QLabel("")
        self.profile_pending_label.setObjectName("Secondary"); self.profile_pending_label.setWordWrap(True)
        prow = QHBoxLayout()
        open_profile = QPushButton("Open Data Folder")
        open_profile.clicked.connect(self.open_profile_folder)
        import_profile = QPushButton("Import Existing WITNESS Folder")
        import_profile.clicked.connect(self.import_existing_profile)
        prow.addWidget(open_profile); prow.addWidget(import_profile); prow.addStretch(1)
        pl.addWidget(ph); pl.addWidget(pd); pl.addWidget(self.profile_id_label)
        pl.addWidget(self.profile_path_label); pl.addWidget(self.profile_pending_label); pl.addLayout(prow)
        self.layout_.addWidget(profile)

        safety = card(); sl = QVBoxLayout(safety)
        sh = QLabel("DATA SAFETY"); sh.setObjectName("SectionTitle")
        sd = QLabel("WITNESS keeps rotating local backups of critical profile state. Full exports can also include your local media. API secrets are never included.")
        sd.setWordWrap(True); sd.setObjectName("Secondary")
        self.backup_status_label = QLabel(""); self.backup_status_label.setObjectName("Muted")
        srow = QHBoxLayout()
        backup_now = QPushButton("Create Backup Now"); backup_now.clicked.connect(self.create_backup_now)
        export_btn = QPushButton("Export Profile"); export_btn.clicked.connect(self.export_profile)
        restore_btn = QPushButton("Restore Backup"); restore_btn.clicked.connect(self.restore_backup)
        backups_btn = QPushButton("Open Backups"); backups_btn.clicked.connect(self.open_backups_folder)
        srow.addWidget(backup_now); srow.addWidget(export_btn); srow.addWidget(restore_btn); srow.addWidget(backups_btn); srow.addStretch(1)
        sl.addWidget(sh); sl.addWidget(sd); sl.addWidget(self.backup_status_label); sl.addLayout(srow)
        self.layout_.addWidget(safety)

        getting = card(); gl = QVBoxLayout(getting)
        gh = QLabel("GETTING STARTED"); gh.setObjectName("SectionTitle")
        gd = QLabel("Reopen the local first-run guide without changing your existing score/history.")
        gd.setWordWrap(True); gd.setObjectName("Secondary")
        guide = QPushButton("Run Setup Guide"); guide.clicked.connect(self.run_onboarding)
        gl.addWidget(gh); gl.addWidget(gd); gl.addWidget(guide, 0, Qt.AlignmentFlag.AlignLeft)
        self.layout_.addWidget(getting)

        feedback = card(); fl = QVBoxLayout(feedback)
        fh = QLabel("FEEDBACK"); fh.setObjectName("SectionTitle")
        fd = QLabel("Keep WITNESS responsive while adding restrained audio feedback for scoring and milestones.")
        fd.setWordWrap(True); fd.setObjectName("Secondary")
        self.sound_btn = QPushButton("")
        self.sound_btn.setCheckable(True)
        self.sound_btn.setChecked(audio.enabled())
        self.sound_btn.clicked.connect(self.toggle_sound)
        fl.addWidget(fh); fl.addWidget(fd); fl.addWidget(self.sound_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.layout_.addWidget(feedback)

        protection = card(); prl = QVBoxLayout(protection)
        prh = QLabel("PROTECTION"); prh.setObjectName("SectionTitle")
        prd = QLabel(
            "Rapid Screen Guard watches the pixels of any supported foreground browser rather than trusting the site title. "
            "It scans on a fast cadence and confirms a visual FLAG within seconds; a confirmed red line force-closes supported "
            "browsers and attempts a 120-minute site lock. SOS video starts automatically in the intervention screen."
        )
        prd.setWordWrap(True); prd.setObjectName("Secondary")
        self.protection_status_label = QLabel(""); self.protection_status_label.setObjectName("Muted")
        prrow = QHBoxLayout()
        open_sos = QPushButton("Open SOS Video Folder"); open_sos.clicked.connect(self.open_sos_videos)
        preview = QPushButton("Preview Intervention"); preview.clicked.connect(self.preview_protection.emit)
        test_kill = QPushButton("Test Browser Shutdown"); test_kill.setObjectName("Danger"); test_kill.clicked.connect(self.test_redline.emit)
        prrow.addWidget(open_sos); prrow.addWidget(preview); prrow.addWidget(test_kill); prrow.addStretch(1)
        prl.addWidget(prh); prl.addWidget(prd); prl.addWidget(self.protection_status_label); prl.addLayout(prrow)
        self.layout_.addWidget(protection)

        danger = card(); dgl = QVBoxLayout(danger)
        dgh = QLabel("FACTORY RESET"); dgh.setObjectName("SectionTitle")
        dgd = QLabel(
            "Return WITNESS progress to a brand-new state: XP, Ghost history, Levels, records, Character/Core/Shield state, "
            "computer/drift history, notes and demo data reset to zero. Your installed app, integration secrets, SOS videos "
            "and safety backups are preserved."
        )
        dgd.setWordWrap(True); dgd.setObjectName("Secondary")
        reset_btn = QPushButton("Factory Reset Progress"); reset_btn.setObjectName("Danger")
        reset_btn.clicked.connect(self.factory_reset_progress)
        dgl.addWidget(dgh); dgl.addWidget(dgd); dgl.addWidget(reset_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.layout_.addWidget(danger)

        demo = card(); dl=QVBoxLayout(demo)
        h=QLabel("SYNTHETIC HISTORY"); h.setObjectName("SectionTitle")
        d=QLabel("Safe test history uses the same XP ledger shape as real actions and can be removed without deleting real XP.")
        d.setWordWrap(True); d.setObjectName("Secondary")
        buttons=QHBoxLayout(); seed=QPushButton("Seed / Reset 28-Day Demo"); seed.setObjectName("Primary")
        clear=QPushButton("Clear Synthetic Demo"); clear.setObjectName("Danger")
        seed.clicked.connect(self.seed_demo); clear.clicked.connect(self.clear_demo)
        buttons.addWidget(seed); buttons.addWidget(clear); buttons.addStretch(1)
        dl.addWidget(h); dl.addWidget(d); dl.addLayout(buttons); self.layout_.addWidget(demo)

        acts = card(); al=QVBoxLayout(acts)
        ah=QLabel("ACTIVITIES"); ah.setObjectName("SectionTitle"); al.addWidget(ah)
        self.activities = QVBoxLayout(); al.addLayout(self.activities)
        add=QPushButton("+ Add Activity"); add.clicked.connect(self.add_activity); al.addWidget(add)
        self.layout_.addWidget(acts); self.layout_.addStretch(1); self.refresh()

    def refresh(self):
        st=demo_data.status()
        self.status.setText(
            f"Synthetic demo: {'ON · '+str(st.get('days',0))+' days' if st.get('active') else 'OFF'}")
        prof = profile_runtime.current_profile()
        pid = str(prof.get("profile_id", ""))
        self.profile_id_label.setText(f"PROFILE · {pid[:12] if pid else 'initializing'}")
        self.profile_path_label.setText(f"Data: {prof.get('data_dir', '')}")
        pending = prof.get("pending_import")
        if pending:
            self.profile_pending_label.setText(
                "IMPORT PENDING · restart WITNESS to import: " + str(pending.get("source", "")))
        else:
            self.profile_pending_label.setText("All personal history stays in this local profile folder.")
        backup = prof.get("backup") or profile_runtime.backup_status()
        if backup.get("latest_name"):
            self.backup_status_label.setText(
                f"{int(backup.get('count',0))} rotating backup(s) · latest {backup.get('latest_name')} · {backup.get('latest_at','')}")
        else:
            self.backup_status_label.setText("No rotating backup yet. WITNESS will create one after profile data exists.")
        self.sound_btn.setChecked(audio.enabled())
        self.sound_btn.setText("SOUND FEEDBACK · ON" if audio.enabled() else "SOUND FEEDBACK · OFF")
        self.sound_btn.setObjectName("Primary" if audio.enabled() else "")
        self.sound_btn.style().unpolish(self.sound_btn); self.sound_btn.style().polish(self.sound_btn)
        try:
            vids = len(sos_videos())
            if not self.protection_status_label.text():
                self.protection_status_label.setText(
                    f"Protection runs while WITNESS is open · {vids} SOS video{'s' if vids != 1 else ''} ready")
        except Exception:
            if not self.protection_status_label.text():
                self.protection_status_label.setText("Protection + rapid screen scanning run while WITNESS is open.")
        clear_layout(self.activities)
        for a in game_engine.list_activities(True):
            row=QFrame(); row.setObjectName("MetricTile")
            lay=QHBoxLayout(row); lay.setContentsMargins(11,7,11,7)
            name=QLabel(a['name']); name.setStyleSheet("font-weight:750;")
            lay.addWidget(name, 1)
            meta=QLabel(f"{a['xp_value']} XP · {a['kind']}"); meta.setObjectName("Secondary")
            lay.addWidget(meta)
            edit=QPushButton("Edit"); edit.clicked.connect(lambda _=False, x=a: self.edit_activity(x))
            lay.addWidget(edit); self.activities.addWidget(row)

    def set_protection_diagnostics(self, info: dict) -> None:
        if not info.get("screen_guard"):
            self.protection_status_label.setText(
                "TITLE ONLY · Screen Guard is not running. Check the Anthropic integration before relying on visual detection.")
            return
        status = str(info.get("status", "WAITING"))
        result = str(info.get("last_result", "WAITING"))
        scans = int(info.get("scans_today", 0) or 0)
        last_scan = float(info.get("last_scan", 0.0) or 0.0)
        err = str(info.get("last_error", "") or "")
        if err:
            self.protection_status_label.setText(
                f"SCREEN GUARD ERROR · {result} · {err[:140]}")
            return
        if last_scan > 0:
            import time as _time
            age = max(0, int(_time.time() - last_scan))
            self.protection_status_label.setText(
                f"RAPID SCREEN GUARD · {status} · last scan {age}s ago · {result} · {scans} scan(s) today")
        else:
            self.protection_status_label.setText(
                f"RAPID SCREEN GUARD · {status} · waiting for a supported browser to be foreground")

    def open_sos_videos(self):
        try:
            open_sos_folder()
        except Exception as ex:
            QMessageBox.critical(self, "SOS videos", str(ex))
        self.refresh()

    def factory_reset_progress(self):
        answer = QMessageBox.warning(
            self, "Factory reset WITNESS progress?",
            "This resets ALL progress/history to zero on the next launch.\n\n"
            "A safety backup will be created first. Integration secrets, SOS videos and existing backups are preserved.\n\n"
            "This cannot be undone from the app except by restoring that backup.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        typed, ok = QInputDialog.getText(
            self, "Confirm factory reset",
            "Type RESET to confirm that XP, Levels, records and history should return to zero:")
        if not ok or typed.strip().upper() != "RESET":
            return
        try:
            result = profile_runtime.stage_factory_reset()
            restart_ready = profile_runtime.schedule_app_restart(delay_seconds=2)
            msg = (
                "Factory reset is staged and the safety backup was created. "
                "WITNESS will now fully close first; only after this process exits will the reset launch start, "
                "and the old profile must be cleared before the database can open again."
            )
            if not restart_ready:
                msg += "\n\nOpen WITNESS again manually to finish the reset."
            QMessageBox.information(self, "Reset staged", msg)
            QApplication.quit()
        except Exception as ex:
            QMessageBox.critical(self, "Factory reset", str(ex))

    def open_profile_folder(self):
        try:
            profile_runtime.open_data_folder()
        except Exception as ex:
            QMessageBox.critical(self, "Profile folder", str(ex))

    def import_existing_profile(self):
        start = str(profile_runtime.app_dir() or profile_runtime.data_dir())
        folder = QFileDialog.getExistingDirectory(
            self, "Select your existing WITNESS folder", start)
        if not folder:
            return
        entries = profile_runtime.legacy_entries(folder)
        if not entries:
            QMessageBox.warning(
                self, "No WITNESS data found",
                "That folder does not contain recognized WITNESS user data.")
            return
        answer = QMessageBox.question(
            self, "Import existing WITNESS data?",
            "WITNESS found:\n\n" + "\n".join(entries[:18]) +
            "\n\nThe import will run on the NEXT launch, before the database opens. "
            "Conflicting profile data will be replaced by the selected existing data. "
            "Your program files are never modified.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            profile_runtime.stage_legacy_import(folder)
            QMessageBox.information(
                self, "Import staged",
                "Import is ready. Close WITNESS and open it again. Your selected history "
                "will be moved into this Windows user's isolated local profile before startup.")
        except Exception as ex:
            QMessageBox.critical(self, "Import error", str(ex))
        self.refresh()

    def create_backup_now(self):
        try:
            out = profile_runtime.create_backup(reason="manual", force=True)
            if out.get("created"):
                QMessageBox.information(self, "Backup created", "Critical WITNESS profile state was backed up locally.\n\n" + str(out.get("path", "")))
            else:
                QMessageBox.information(self, "Backup", str(out.get("reason", "No backup was needed.")))
        except Exception as ex:
            QMessageBox.critical(self, "Backup error", str(ex))
        self.refresh()

    def open_backups_folder(self):
        try:
            profile_runtime.open_backups_folder()
        except Exception as ex:
            QMessageBox.critical(self, "Backups", str(ex))

    def export_profile(self):
        docs = Path.home() / "Documents"
        start_dir = docs if docs.exists() else Path.home()
        default = start_dir / f"WITNESS-profile-{date.today().isoformat()}.zip"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export WITNESS Profile", str(default), "ZIP archive (*.zip)")
        if not filename:
            return
        answer = QMessageBox.question(
            self, "Export profile?",
            "This export includes your local WITNESS profile and media, but intentionally excludes API secrets. "
            "Large video history can make the ZIP take longer to create.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            out = profile_runtime.export_profile(filename, include_media=True)
            QMessageBox.information(self, "Profile exported", "WITNESS profile export created.\n\n" + str(out.get("path", filename)))
        except Exception as ex:
            QMessageBox.critical(self, "Export error", str(ex))

    def restore_backup(self):
        folder = profile_runtime.backup_status().get("folder") or str(profile_runtime.data_dir())
        filename, _ = QFileDialog.getOpenFileName(
            self, "Restore WITNESS Backup", str(folder), "ZIP archive (*.zip)")
        if not filename:
            return
        answer = QMessageBox.question(
            self, "Stage backup restore?",
            "Restore is applied on the NEXT WITNESS launch before the database opens. Existing conflicting profile state will be replaced. "
            "WITNESS will not restore API secrets from an archive.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            profile_runtime.create_backup(reason="pre-restore", force=True)
            profile_runtime.stage_backup_restore(filename)
            QMessageBox.information(
                self, "Restore staged",
                "A safety backup was created and the restore is staged. Close WITNESS and open it again to apply the backup.")
        except Exception as ex:
            QMessageBox.critical(self, "Restore error", str(ex))
        self.refresh()

    def run_onboarding(self):
        dlg = onboarding.OnboardingDialog(self)
        if dlg.exec():
            QMessageBox.information(self, "Setup saved", "Your local setup was updated. Existing XP/history was not changed.")
        self.refresh()

    def toggle_sound(self, checked=False):
        audio.set_enabled(bool(checked))
        if checked:
            audio.play("xp")
        self.refresh()

    def seed_demo(self):
        try:
            out=demo_data.seed(28)
            QMessageBox.information(self,"Demo seeded",f"{out['days']} days · {out['events']} XP events")
        except Exception as ex:
            QMessageBox.critical(self,"Demo error",str(ex))
        self.refresh()

    def clear_demo(self):
        try:
            out=demo_data.clear()
            QMessageBox.information(self,"Demo cleared",f"Removed {out.get('removed_events',0)} synthetic XP events.")
        except Exception as ex:
            QMessageBox.critical(self,"Demo error",str(ex))
        self.refresh()

    def add_activity(self): self._activity_dialog(None)
    def edit_activity(self, a): self._activity_dialog(a)

    def _activity_dialog(self, a):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox
        dlg=QDialog(self); dlg.setWindowTitle("Activity")
        form=QFormLayout(dlg)
        name=QLineEdit(a['name'] if a else '')
        xp=QSpinBox(); xp.setMaximum(1000000); xp.setValue(int(a['xp_value']) if a else 10)
        kind=QComboBox(); kind.addItems(["repeatable","once_daily","timed"])
        if a: kind.setCurrentText(a['kind'])
        form.addRow("Name",name); form.addRow("XP",xp); form.addRow("Type",kind)
        buttons=QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            try:
                if a:
                    game_engine.update_activity(
                        a['id'],name=name.text(),xp_value=xp.value(),kind=kind.currentText())
                else:
                    game_engine.create_activity(name.text(),xp.value(),kind.currentText(),True,999)
            except Exception as ex:
                QMessageBox.critical(self,"Activity error",str(ex))
            self.refresh()
