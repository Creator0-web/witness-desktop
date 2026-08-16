from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from . import onboarding, theme
from .arena import ArenaPage
from .character_page import CharacterPage
from .pages import CalendarPage, InsightsPage, RecordsPage, SettingsPage
from .update_service import UpdateService
from app_version import BUILD_TAG, DISPLAY_VERSION
import update_manager
import profile_runtime
import game_engine


class WitnessMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"WITNESS · {DISPLAY_VERSION} · build {BUILD_TAG}")
        self.resize(1320, 860)
        self.setMinimumSize(1080, 720)
        try:
            initial_level = int(game_engine.level_status().get("current_level", 1) or 1)
        except Exception:
            initial_level = 1
        self._theme_tokens = theme.set_active_level(initial_level)
        self._theme_era = str(self._theme_tokens.get("id", "wild"))
        self.setStyleSheet(theme.APP_STYLESHEET)
        self._page_anim = None
        self._available_update = None

        central = QWidget(); self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        top = QWidget()
        top.setObjectName("TopBar")
        th = QHBoxLayout(top); th.setContentsMargins(18, 9, 18, 9); th.setSpacing(8)
        brand = QLabel("WITNESS"); brand.setObjectName("Brand")
        sub = QLabel("SELF-COMPETITION ARENA"); sub.setObjectName("Eyebrow")
        self.era_badge = QLabel(str(self._theme_tokens.get("label", "WILD ERA")))
        self.era_badge.setObjectName("EraBadge")
        th.addWidget(brand); th.addWidget(sub); th.addSpacing(4); th.addWidget(self.era_badge); th.addStretch(1)
        self.update_btn = QPushButton("")
        self.update_btn.setObjectName("Primary")
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(self._start_update)
        th.addWidget(self.update_btn)
        self.updated_badge = QLabel(f"✓ UPDATED TO {DISPLAY_VERSION}")
        self.updated_badge.setObjectName("UpdatedBadge")
        self.updated_badge.setVisible("/updated" in sys.argv)
        th.addWidget(self.updated_badge)
        if self.updated_badge.isVisible():
            QTimer.singleShot(12000, lambda: self.updated_badge.setVisible(False))
        self.live = QLabel("●  LIVE"); self.live.setObjectName("LiveBadge")
        th.addWidget(self.live); outer.addWidget(top)

        self.stack = QStackedWidget(); outer.addWidget(self.stack, 1)
        self.pages = {
            "arena": ArenaPage(),
            "character": CharacterPage(),
            "calendar": CalendarPage(),
            "records": RecordsPage(),
            "insights": InsightsPage(),
            "settings": SettingsPage(),
        }
        for p in self.pages.values():
            self.stack.addWidget(p)
        self.pages["arena"].request_page.connect(self.show_page)
        self.pages["arena"].changed.connect(self._on_arena_changed)

        nav = QWidget()
        nav.setObjectName("BottomNav")
        nl = QHBoxLayout(nav); nl.setContentsMargins(18, 7, 18, 7); nl.setSpacing(8)
        group = QButtonGroup(self); group.setExclusive(True); self.nav = {}
        for key, text in (
            ("arena", "ARENA"), ("character", "CHARACTER"),
            ("calendar", "HISTORY"), ("records", "RECORDS"),
            ("insights", "INSIGHTS"), ("settings", "SETTINGS")):
            b = QPushButton(text); b.setObjectName("Nav"); b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.show_page(k))
            group.addButton(b); self.nav[key] = b; nl.addWidget(b)
        nl.addStretch(1)
        outer.addWidget(nav)
        self.show_page("arena", animate=False)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_current)
        self.timer.start(2000)

        # Update work is intentionally off the GUI thread. Development/source
        # builds have no release repository configured, so this is a silent no-op
        # until the Windows release workflow embeds the real GitHub repository.
        self.update_service = UpdateService(self)
        self.update_service.available.connect(self._on_update_available)
        self.update_service.progress.connect(self._on_update_progress)
        self.update_service.downloaded.connect(self._on_update_downloaded)
        self.update_service.error.connect(self._on_update_error)
        QTimer.singleShot(3500, lambda: self.update_service.check(silent=True))
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(lambda: self.update_service.check(silent=True))
        self.update_timer.start(update_manager.channel_config()["check_hours"] * 60 * 60 * 1000)

        # First-run setup is local-only and never interrupts an established account.
        if onboarding.should_show():
            QTimer.singleShot(650, self._show_onboarding)
        if profile_runtime.current_profile().get("previous_unclean_shutdown"):
            QTimer.singleShot(1100, self._show_recovery_notice)

    def _show_onboarding(self):
        dlg = onboarding.OnboardingDialog(self)
        if dlg.exec():
            try:
                self.pages["arena"].refresh(include_slow=True)
            except TypeError:
                self.pages["arena"].refresh()
            self.pages["settings"].refresh()

    def _show_recovery_notice(self):
        prof = profile_runtime.current_profile()
        backup = prof.get("backup") or {}
        latest = str(backup.get("latest_name") or "")
        extra = f"\n\nLatest local backup: {latest}" if latest else ""
        QMessageBox.information(
            self, "WITNESS recovered safely",
            "The previous WITNESS session did not close normally. Your local profile was not reset. "
            "WITNESS created/checked a recovery backup before opening the database." + extra +
            "\n\nUse SETTINGS → DATA SAFETY if you want to create, export, or restore a backup.")

    def _fade_in(self, page):
        if self._page_anim is not None:
            try:
                self._page_anim.stop()
            except Exception:
                pass
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.35)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(190)
        anim.setStartValue(0.35)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_anim = anim
        anim.start()

    def show_page(self, key, animate=True):
        if key not in self.pages:
            return
        page = self.pages[key]
        changed_page = self.stack.currentWidget() is not page
        self.stack.setCurrentWidget(page)
        self.nav[key].setChecked(True)
        if hasattr(page, "refresh"):
            page.refresh()
        if animate and changed_page:
            self._fade_in(page)

    def refresh_current(self):
        self._sync_theme()
        page = self.stack.currentWidget()
        # The Arena has a lightweight live-refresh path so the 2-second timer
        # never rebuilds cards, charts, insights, or hidden pages. This keeps
        # score/ghost motion live without blocking Qt's paint/animation loop.
        if hasattr(page, "live_refresh"):
            page.live_refresh()
        elif hasattr(page, "refresh"):
            page.refresh()

    def _sync_theme(self, force=False):
        """Follow the canonical current Level with a broad app-wide visual era."""
        try:
            level = int(game_engine.level_status().get("current_level", 1) or 1)
        except Exception:
            level = 1
        incoming = theme.era_for_level(level)
        era_id = str(incoming.get("id", "wild"))
        if not force and era_id == getattr(self, "_theme_era", None):
            return
        self._theme_tokens = theme.set_active_level(level)
        self._theme_era = str(self._theme_tokens.get("id", "wild"))
        self.setStyleSheet(theme.APP_STYLESHEET)
        if hasattr(self, "era_badge"):
            self.era_badge.setText(str(self._theme_tokens.get("label", "WILD ERA")))
        # Re-polish the current page only. Hidden pages keep their data lazy and
        # inherit the new app stylesheet when they are next shown.
        page = self.stack.currentWidget() if hasattr(self, "stack") else None
        if page is not None:
            page.style().unpolish(page); page.style().polish(page); page.update()

    def _on_arena_changed(self):
        # Do NOT synchronously refresh every hidden page after an Activity
        # click. Calendar/Records/Insights can be expensive to rebuild and the
        # old behavior blocked the UI thread before XP animations could paint.
        # Each page already refreshes itself when it is opened. Theme sync is
        # lightweight and may react immediately if an action caused evolution.
        QTimer.singleShot(0, self._sync_theme)
        return


    def _on_update_available(self, release):
        self._available_update = dict(release)
        version = str(release.get("latest_version") or "NEW")
        self.update_btn.setText(f"UPDATE v{version}")
        self.update_btn.setEnabled(True)
        self.update_btn.setVisible(True)

    def _start_update(self):
        release = self._available_update
        if not release:
            return
        version = str(release.get("latest_version") or "new version")
        answer = QMessageBox.question(
            self,
            "Update WITNESS",
            f"WITNESS v{version} is ready.\n\n"
            "WITNESS will download the verified installer, close, update its program files, "
            "and reopen. Your local profile/data folder is not replaced.\n\n"
            "Update & Restart now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.update_btn.setEnabled(False)
        self.update_btn.setText("DOWNLOADING · 0%")
        self.update_service.download(release)

    def _on_update_progress(self, pct):
        if self._available_update:
            self.update_btn.setText(f"DOWNLOADING · {int(pct)}%")

    def _on_update_downloaded(self, installer_path, release):
        try:
            update_manager.launch_update_and_restart(installer_path)
        except Exception as ex:
            self._on_update_error(str(ex))
            return
        self.update_btn.setText("INSTALLING…")
        # The helper waits two seconds before starting setup; quit immediately so
        # the installed executable is no longer locked when Inno Setup replaces it.
        QTimer.singleShot(100, QApplication.quit)

    def _on_update_error(self, message):
        if self._available_update:
            version = str(self._available_update.get("latest_version") or "")
            self.update_btn.setText(f"UPDATE v{version}" if version else "UPDATE")
            self.update_btn.setEnabled(True)
            self.update_btn.setVisible(True)
        QMessageBox.warning(
            self,
            "WITNESS Update",
            "The update was not installed. WITNESS and your personal data are unchanged.\n\n"
            + str(message),
        )

    def refresh_all(self):
        """Explicit maintenance hook; never used on the Activity click path."""
        for p in self.pages.values():
            if hasattr(p, "refresh"):
                try:
                    p.refresh()
                except Exception:
                    pass
