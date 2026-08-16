from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QToolTip, QVBoxLayout, QWidget,
)

import game_engine

from . import theme
from .widgets import card, clear_layout


class ProgressionChart(QWidget):
    """Stock-style Level Rating chart for current territory or all history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = None
        self.mode = "current"
        self._plot = None
        self._points = []
        self.setMouseTracking(True)
        self.setMinimumHeight(330)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, snapshot, mode):
        self.snapshot = snapshot or {}
        self.mode = "all" if mode == "all" else "current"
        self.update()

    @staticmethod
    def _fmt_xp(value):
        value = int(value or 0)
        if abs(value) >= 1000:
            return f"{value / 1000:.1f}K".replace(".0K", "K")
        return f"{value:,}"

    @staticmethod
    def _short_date(day):
        try:
            return datetime.strptime(day, "%Y-%m-%d").strftime("%b %d")
        except Exception:
            return str(day)

    def _series(self):
        if not self.snapshot:
            return []
        if self.mode == "all":
            return list(self.snapshot.get("all_time", {}).get("series", []))
        return list(self.snapshot.get("current_level", {}).get("series", []))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#0d1216"))

        rows = self._series()
        if not rows:
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(self.rect(), Qt.AlignCenter, "No progression history yet.")
            self._plot = None
            self._points = []
            return

        r = self.rect()
        ml, mr, mt, mb = 74, 24, 22, 42
        pw = max(20, r.width() - ml - mr)
        ph = max(20, r.height() - mt - mb)
        plot = QRectF(ml, mt, pw, ph)
        self._plot = plot

        ratings = [int(x.get("rating", 0)) for x in rows]
        status = self.snapshot.get("status", {})
        current = self.snapshot.get("current_level", {})
        levels = self.snapshot.get("levels", [])

        if self.mode == "current":
            floor = int(current.get("demotion_floor", 0) or 0)
            entry = int(current.get("entry_threshold", 0) or 0)
            next_threshold = current.get("next_threshold")
            observed_min = min(ratings + [floor])
            pad = max(100, int(max(1, entry - floor) * 0.08))
            y_min = max(0, min(floor, observed_min) - pad)
            if next_threshold is not None:
                y_max = max(int(next_threshold), max(ratings + [entry]) + 1)
            else:
                span = max(5000, int(max(ratings + [entry, 1]) * 0.20))
                y_max = max(ratings + [entry]) + span
            if y_max <= y_min:
                y_max = y_min + 1000
        else:
            y_min = 0
            next_threshold = status.get("next_threshold")
            candidates = ratings + [int(x.get("threshold", 0)) for x in levels]
            if next_threshold is not None:
                candidates.append(int(next_threshold))
            top = max(candidates + [1])
            # Keep the next visible tier in frame without letting distant future
            # tiers flatten the person's real history.
            current_level = int(status.get("current_level", 1) or 1)
            visible_levels = [x for x in levels if int(x.get("level", 1)) <= current_level + 1]
            top = max(ratings + [int(x.get("threshold", 0)) for x in visible_levels] + [1])
            y_max = int(top * 1.08) + 1

        def y(value):
            frac = (float(value) - y_min) / max(1.0, float(y_max - y_min))
            frac = max(0.0, min(1.0, frac))
            return plot.bottom() - frac * plot.height()

        def x(index):
            if len(rows) <= 1:
                return plot.left() + plot.width() / 2
            return plot.left() + plot.width() * index / (len(rows) - 1)

        # Subtle grid.
        p.setPen(QPen(QColor("#202930"), 1))
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            yy = plot.bottom() - plot.height() * frac
            p.drawLine(QPointF(plot.left(), yy), QPointF(plot.right(), yy))
            val = int(round(y_min + (y_max - y_min) * frac))
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(QRectF(2, yy - 9, ml - 10, 18), Qt.AlignRight | Qt.AlignVCenter,
                       self._fmt_xp(val))
            p.setPen(QPen(QColor("#202930"), 1))

        # Level territory / threshold overlays.
        if self.mode == "current":
            entry = int(current.get("entry_threshold", 0) or 0)
            floor = int(current.get("demotion_floor", 0) or 0)
            # At-risk zone under the entry threshold.
            if entry > floor:
                danger = QRectF(plot.left(), y(entry), plot.width(), max(1, y(floor) - y(entry)))
                p.fillRect(danger, QColor(183, 67, 73, 22))

            floor_pen = QPen(QColor(theme.RED), 1)
            floor_pen.setStyle(Qt.DashLine)
            p.setPen(floor_pen)
            p.drawLine(QPointF(plot.left(), y(floor)), QPointF(plot.right(), y(floor)))
            p.setPen(QColor(theme.RED))
            p.drawText(QRectF(plot.left() + 6, y(floor) - 19, 220, 18),
                       Qt.AlignLeft, f"DEMOTION FLOOR  {floor:,}")

            p.setPen(QPen(QColor("#72808a"), 1.3))
            p.drawLine(QPointF(plot.left(), y(entry)), QPointF(plot.right(), y(entry)))
            p.setPen(QColor(theme.TEXT_2))
            p.drawText(QRectF(plot.left() + 6, y(entry) - 19, 270, 18),
                       Qt.AlignLeft,
                       f"LV.{current.get('level', 1)} ENTRY  {entry:,}")

            nxt = current.get("next_threshold")
            if nxt is not None:
                p.setPen(QPen(QColor(theme.GREEN), 1.3))
                p.drawLine(QPointF(plot.left(), y(int(nxt))), QPointF(plot.right(), y(int(nxt))))
                next_level = int(current.get("level", 1)) + 1
                next_name = next((z.get("name") for z in levels if int(z.get("level", 0)) == next_level), "NEXT")
                p.setPen(QColor(theme.GREEN))
                p.drawText(QRectF(plot.left() + 6, y(int(nxt)) + 2, 310, 18),
                           Qt.AlignLeft, f"LV.{next_level} {str(next_name).upper()}  {int(nxt):,}")
        else:
            current_level = int(status.get("current_level", 1) or 1)
            for tier in levels:
                lvl = int(tier.get("level", 1))
                threshold = int(tier.get("threshold", 0))
                if lvl == 1 or lvl > current_level + 1 or threshold > y_max:
                    continue
                pen = QPen(QColor("#49545d"), 1)
                pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(plot.left(), y(threshold)), QPointF(plot.right(), y(threshold)))
                p.setPen(QColor(theme.MUTED if lvl > current_level else theme.TEXT_2))
                p.drawText(QRectF(plot.left() + 6, y(threshold) - 18, 300, 17),
                           Qt.AlignLeft,
                           f"LV.{lvl} {str(tier.get('name', '')).upper()}  {threshold:,}")

        # Filled area under the rating line.
        points = [QPointF(x(i), y(v)) for i, v in enumerate(ratings)]
        self._points = points
        if len(points) > 1:
            area = QPainterPath(points[0])
            for pt in points[1:]:
                area.lineTo(pt)
            area.lineTo(QPointF(points[-1].x(), plot.bottom()))
            area.lineTo(QPointF(points[0].x(), plot.bottom()))
            area.closeSubpath()
            grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
            grad.setColorAt(0, QColor(83, 220, 129, 58))
            grad.setColorAt(1, QColor(83, 220, 129, 4))
            p.fillPath(area, grad)

            line = QPainterPath(points[0])
            for pt in points[1:]:
                line.lineTo(pt)
            p.setPen(QPen(QColor(theme.GREEN), 2.6))
            p.drawPath(line)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.GREEN))
            p.drawEllipse(points[0], 4, 4)

        # All-time milestone dots. Reconstructed crossings are enough for old
        # history; explicit demotion/reclaim events are preserved in SQLite.
        if self.mode == "all":
            index_by_day = {row.get("day"): i for i, row in enumerate(rows)}
            for milestone in self.snapshot.get("all_time", {}).get("milestones", []):
                idx = index_by_day.get(milestone.get("day"))
                if idx is None:
                    continue
                pt = points[idx]
                kind = milestone.get("event_type")
                color = theme.RED if kind == "demotion" else theme.GOLD
                p.setPen(QPen(QColor("#0d1216"), 2))
                p.setBrush(QColor(color))
                p.drawEllipse(pt, 5, 5)

        # Current point marker.
        current_pt = points[-1]
        p.setPen(QPen(QColor("#0d1216"), 2))
        p.setBrush(QColor(theme.GREEN))
        p.drawEllipse(current_pt, 5.5, 5.5)
        p.setPen(QColor(theme.TEXT))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.drawText(QRectF(max(plot.left(), current_pt.x() - 105),
                          max(plot.top(), current_pt.y() - 28), 100, 20),
                   Qt.AlignRight | Qt.AlignVCenter,
                   f"{ratings[-1]:,}")

        # X-axis dates.
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(theme.MUTED))
        for idx in sorted({0, len(rows) // 2, len(rows) - 1}):
            xx = x(idx)
            p.drawText(QRectF(xx - 42, plot.bottom() + 10, 84, 20),
                       Qt.AlignCenter, self._short_date(rows[idx].get("day")))

    def mouseMoveEvent(self, event):
        rows = self._series()
        if not rows or not self._plot or not self._points:
            return
        pos = event.position()
        if not self._plot.contains(pos):
            QToolTip.hideText()
            return
        nearest = min(range(len(self._points)), key=lambda i: abs(self._points[i].x() - pos.x()))
        row = rows[nearest]
        try:
            pretty = datetime.strptime(row["day"], "%Y-%m-%d").strftime("%A, %b %d, %Y")
        except Exception:
            pretty = row.get("day", "")
        text = (f"{pretty}\n"
                f"Level Rating: {int(row.get('rating', 0)):,}\n"
                f"Daily XP: {int(row.get('daily_score_xp', 0)):,}\n"
                f"Natural tier: Lv.{row.get('natural_level', 1)} {row.get('level_name', '')}")
        QToolTip.showText(event.globalPosition().toPoint(), text, self)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)


class ProgressionView(QWidget):
    """History's second lens: current territory vs full evolution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "current"
        self.snapshot = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        switch = QHBoxLayout()
        label = QLabel("PROGRESSION")
        label.setObjectName("SectionTitle")
        switch.addWidget(label)
        switch.addStretch(1)
        self.current_btn = QPushButton("CURRENT LEVEL")
        self.all_btn = QPushButton("ALL TIME")
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for btn in (self.current_btn, self.all_btn):
            btn.setObjectName("Tab")
            btn.setCheckable(True)
            self.group.addButton(btn)
            switch.addWidget(btn)
        self.current_btn.setChecked(True)
        self.current_btn.clicked.connect(lambda: self.set_mode("current"))
        self.all_btn.clicked.connect(lambda: self.set_mode("all"))
        outer.addLayout(switch)

        self.summary = QHBoxLayout()
        self.summary.setSpacing(10)
        outer.addLayout(self.summary)

        chart_card = card(strong=True)
        chart_l = QVBoxLayout(chart_card)
        chart_l.setContentsMargins(15, 13, 15, 14)
        chart_l.setSpacing(7)
        self.chart_title = QLabel("")
        self.chart_title.setObjectName("SectionTitle")
        self.chart_sub = QLabel("")
        self.chart_sub.setObjectName("Secondary")
        self.chart_sub.setWordWrap(True)
        self.chart = ProgressionChart()
        chart_l.addWidget(self.chart_title)
        chart_l.addWidget(self.chart_sub)
        chart_l.addWidget(self.chart)
        outer.addWidget(chart_card)

        self.milestone_card = card()
        ml = QVBoxLayout(self.milestone_card)
        ml.setContentsMargins(15, 12, 15, 13)
        ml.setSpacing(6)
        mh = QLabel("LEVEL MILESTONES")
        mh.setObjectName("SectionTitle")
        ml.addWidget(mh)
        self.milestone_list = QVBoxLayout()
        self.milestone_list.setSpacing(4)
        ml.addLayout(self.milestone_list)
        outer.addWidget(self.milestone_card)
        outer.addStretch(1)
        self.refresh()

    def _metric(self, title, value, accent=None, detail=""):
        f = QFrame()
        f.setObjectName("MetricTile")
        l = QVBoxLayout(f)
        l.setContentsMargins(13, 9, 13, 9)
        l.setSpacing(2)
        a = QLabel(str(title).upper())
        a.setObjectName("Eyebrow")
        b = QLabel(str(value))
        b.setStyleSheet(f"font-size:20px;font-weight:900;color:{accent or theme.TEXT};")
        l.addWidget(a)
        l.addWidget(b)
        if detail:
            d = QLabel(detail)
            d.setObjectName("Muted")
            l.addWidget(d)
        return f

    def set_mode(self, mode):
        self.mode = "all" if mode == "all" else "current"
        self.current_btn.setChecked(self.mode == "current")
        self.all_btn.setChecked(self.mode == "all")
        self._render()

    def refresh(self):
        self.snapshot = game_engine.progression_snapshot()
        self._render()

    def _render(self):
        if not self.snapshot:
            return
        clear_layout(self.summary)
        status = self.snapshot.get("status", {})
        current = self.snapshot.get("current_level", {})
        all_time = self.snapshot.get("all_time", {})
        level = int(status.get("current_level", 1))
        rating = int(status.get("rating", 0))
        progress = float(current.get("progress", 0) or 0)

        self.summary.addWidget(self._metric(
            "Current Tier", f"LV. {level} {str(status.get('name', '')).upper()}",
            theme.GREEN), 2)
        self.summary.addWidget(self._metric("Rating", f"{rating:,} XP"), 1)
        self.summary.addWidget(self._metric(
            "Territory", f"{progress * 100:.0f}%",
            theme.GREEN, f"Entered {current.get('entry_day', '—')}"), 1)
        self.summary.addWidget(self._metric(
            "All-Time Peak", f"{int(all_time.get('peak_rating', 0)):,}",
            theme.GOLD, all_time.get("peak_day", "—")), 1)

        if self.mode == "current":
            nxt = current.get("next_threshold")
            if nxt is not None:
                remaining = max(0, int(nxt) - rating)
                target = f"Next tier at {int(nxt):,} · {remaining:,} rating to conquer."
            else:
                target = "Highest configured tier reached. Keep raising the all-time peak."
            self.chart_title.setText("CURRENT LEVEL TERRITORY")
            self.chart_sub.setText(
                f"The graph starts where this level became yours. LV.{level} entry "
                f"({int(current.get('entry_threshold', 0)):,}) is the new baseline; "
                f"the red zone below protects against coasting. {target}")
        else:
            self.chart_title.setText("ALL-TIME EVOLUTION")
            self.chart_sub.setText(
                "Your complete rolling Level Rating from the beginning. Level lines show "
                "territory you have crossed; hover the chart to inspect dates, daily XP and plateaus.")
        self.chart.set_data(self.snapshot, self.mode)

        clear_layout(self.milestone_list)
        milestones = list(all_time.get("milestones", []))
        if not milestones:
            msg = QLabel("No level milestones yet. Your first threshold crossing will appear here.")
            msg.setObjectName("Muted")
            self.milestone_list.addWidget(msg)
            return
        for m in milestones[-8:]:
            kind = m.get("event_type", "threshold_crossed")
            to_level = int(m.get("to_level") or 1)
            name = str(m.get("name", ""))
            if kind == "demotion":
                verb = f"DEMOTED → LV.{to_level} {name.upper()}"
                color = theme.RED
            elif kind == "reclaim":
                verb = f"RECLAIMED LV.{to_level} {name.upper()}"
                color = theme.GREEN
            else:
                verb = f"REACHED LV.{to_level} {name.upper()}"
                color = theme.GOLD
            row = QHBoxLayout()
            day = QLabel(str(m.get("day", "")))
            day.setObjectName("Muted")
            text = QLabel(verb)
            text.setStyleSheet(f"font-weight:800;color:{color};")
            rating_lbl = QLabel(f"{int(m.get('rating', 0)):,}")
            rating_lbl.setObjectName("Secondary")
            row.addWidget(day)
            row.addWidget(text)
            row.addStretch(1)
            row.addWidget(rating_lbl)
            self.milestone_list.addLayout(row)
