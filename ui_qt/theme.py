"""Dynamic visual tokens for the PySide6 WITNESS interface.

v7.56 introduces *visual eras* tied to the canonical current Level.  This is
presentation-only: it never changes XP, Ghost, progression math, records, Core,
or Shield state.

The eras are deliberately broad so the product evolves without becoming eight
unrelated skins:

- Levels 1-2: WILD ERA — deep jungle blacks, moss, organic softness.
- Levels 3-4: FORGED ERA — stone/charcoal surfaces, tighter geometry, bronze edge.
- Levels 5-8: NOIR ERA — sleek near-black/steel surfaces, minimal radii, quiet gold.

Semantic colors remain stable across every era: green still means action/winning,
red still means danger/losing, and gold still means records/major milestones.
"""
from __future__ import annotations

# Stable semantic colors used by existing inline UI code.
TEXT = "#f1f4f6"
TEXT_2 = "#adb6bd"
MUTED = "#6f7b84"
GREEN = "#61df83"
GREEN_DARK = "#153722"
GREEN_SOFT = "#1d452b"
RED = "#ef6868"
RED_DARK = "#3a1d20"
GOLD = "#e7b84b"
GOLD_DARK = "#3a3018"
GHOST = "#87919a"

ERA_DEFS = {
    "wild": {
        "id": "wild", "label": "WILD ERA", "levels": (1, 2),
        "bg": "#07100b", "bg_2": "#0a1510", "surface": "#0e1812",
        "surface_2": "#132019", "surface_3": "#18271f",
        "border": "#24382b", "border_strong": "#365342",
        "accent": "#75b887", "accent_soft": "#14291b", "accent_hover": "#1a3422",
        "selection": "#183523", "radius": 14, "radius_strong": 16,
        "card_top": "#101b14", "card_bottom": "#0b130f",
        "metric": "#0b1510", "table": "#0b1510", "table_alt": "#0e1913",
        "grid": "#1a2a20", "scroll": "#2b4234", "scroll_hover": "#395747",
        "input": "#122019", "focus": "#4f8061",
        "chrome_top": "#09140e", "chrome_bottom": "#0a120e",
    },
    "forged": {
        "id": "forged", "label": "FORGED ERA", "levels": (3, 4),
        "bg": "#090a0a", "bg_2": "#0d0f0f", "surface": "#121414",
        "surface_2": "#181a19", "surface_3": "#1d201f",
        "border": "#322f29", "border_strong": "#4b4539",
        "accent": "#ad9568", "accent_soft": "#292319", "accent_hover": "#342c1f",
        "selection": "#30271b", "radius": 10, "radius_strong": 12,
        "card_top": "#151716", "card_bottom": "#0f1110",
        "metric": "#101211", "table": "#101211", "table_alt": "#141615",
        "grid": "#262621", "scroll": "#383832", "scroll_hover": "#4a4940",
        "input": "#171918", "focus": "#7e6c4f",
        "chrome_top": "#0e100f", "chrome_bottom": "#0c0e0d",
    },
    "noir": {
        "id": "noir", "label": "NOIR ERA", "levels": (5, 6, 7, 8),
        "bg": "#05070a", "bg_2": "#080b0f", "surface": "#0c1014",
        "surface_2": "#11161b", "surface_3": "#171d23",
        "border": "#242b33", "border_strong": "#3b4651",
        "accent": "#bfa36b", "accent_soft": "#242015", "accent_hover": "#30291a",
        "selection": "#2c2518", "radius": 7, "radius_strong": 9,
        "card_top": "#0f1419", "card_bottom": "#090d11",
        "metric": "#090e12", "table": "#090e12", "table_alt": "#0d1217",
        "grid": "#1b232b", "scroll": "#28333d", "scroll_hover": "#374550",
        "input": "#10161b", "focus": "#7d704f",
        "chrome_top": "#070a0e", "chrome_bottom": "#070a0d",
    },
}


def era_for_level(level: int | float | str | None) -> dict:
    try:
        n = int(level or 1)
    except (TypeError, ValueError):
        n = 1
    if n <= 2:
        return dict(ERA_DEFS["wild"])
    if n <= 4:
        return dict(ERA_DEFS["forged"])
    return dict(ERA_DEFS["noir"])


_ACTIVE_LEVEL = 1
_ACTIVE = era_for_level(1)


def current_tokens() -> dict:
    return dict(_ACTIVE)


def active_era_id() -> str:
    return str(_ACTIVE["id"])


def set_active_level(level) -> dict:
    """Set presentation era and update compatibility token globals."""
    global _ACTIVE_LEVEL, _ACTIVE, BG, BG_2, SURFACE, SURFACE_2, SURFACE_3, BORDER, BORDER_STRONG, APP_STYLESHEET
    try:
        _ACTIVE_LEVEL = max(1, min(8, int(level or 1)))
    except (TypeError, ValueError):
        _ACTIVE_LEVEL = 1
    _ACTIVE = era_for_level(_ACTIVE_LEVEL)
    BG = _ACTIVE["bg"]
    BG_2 = _ACTIVE["bg_2"]
    SURFACE = _ACTIVE["surface"]
    SURFACE_2 = _ACTIVE["surface_2"]
    SURFACE_3 = _ACTIVE["surface_3"]
    BORDER = _ACTIVE["border"]
    BORDER_STRONG = _ACTIVE["border_strong"]
    APP_STYLESHEET = _stylesheet(_ACTIVE)
    return dict(_ACTIVE)


def stylesheet_for_level(level) -> str:
    return _stylesheet(era_for_level(level))


def _stylesheet(t: dict) -> str:
    r = int(t["radius"]); rs = int(t["radius_strong"])
    accent = t["accent"]
    return f"""
QWidget {{
    background: {t['bg']};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QMainWindow {{ background: {t['bg']}; }}
QStackedWidget {{ background: {t['bg']}; }}
QLabel {{ background: transparent; border: none; }}
QFrame {{ background: transparent; border: none; }}
QWidget#TopBar {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {t['chrome_top']}, stop:1 {t['bg_2']});
    border-bottom: 1px solid {accent};
}}
QWidget#BottomNav {{
    background: {t['chrome_bottom']};
    border-top: 1px solid {t['border']};
}}
QLabel#BrandMark {{ font-size:25px; font-weight:950; color:{accent}; padding:0px 2px 1px 0px; }}
QLabel#Brand {{ font-size:22px; font-weight:900; letter-spacing:2px; color:{TEXT}; }}
QLabel#EraBadge {{
    color:{accent}; font-size:10px; font-weight:850; letter-spacing:1px;
    border:1px solid {t['border_strong']}; border-radius:{max(5, r-2)}px; padding:4px 8px;
}}
QLabel#LiveBadge {{ color:{GREEN}; font-weight:850; }}
QLabel#ProtectionBadge {{ color:{MUTED}; font-size:10px; font-weight:800; padding:4px 8px; border:1px solid {t['border']}; border-radius:6px; }}
QLabel#ProtectionBadge[active="true"] {{ color:{GREEN}; border-color:#2d7241; background:{GREEN_DARK}; }}
QLabel#UpdatedBadge {{
    color:{GREEN}; font-weight:900; padding:5px 9px;
    border:1px solid {GREEN}; border-radius:{max(5, r-2)}px;
}}
QToolTip {{
    background: {t['surface_3']}; color: {TEXT}; border: 1px solid {t['border_strong']};
    padding: 6px 8px;
}}
QFrame#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['card_top']}, stop:1 {t['card_bottom']});
    border: 1px solid {t['border']};
    border-radius: {r}px;
}}
QFrame#CardStrong {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 {t['card_top']}, stop:1 {t['bg_2']});
    border: 1px solid {t['border_strong']};
    border-radius: {rs}px;
}}
QFrame#ActivityCard {{
    background: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: {max(7, r-2)}px;
}}
QFrame#ActivityCard:hover {{
    background: {t['surface_2']};
    border-color: {t['border_strong']};
}}
QFrame#MetricTile {{
    background: {t['metric']};
    border: 1px solid {t['border']};
    border-radius: {max(6, r-4)}px;
}}
QLabel#Eyebrow {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; }}
QLabel#SectionTitle {{ color: {TEXT}; font-size: 15px; font-weight: 800; }}
QLabel#PageTitle {{ color: {TEXT}; font-size: 23px; font-weight: 900; }}
QLabel#HugeScore {{ color: {TEXT}; font-size: 37px; font-weight: 900; }}
QLabel#LargeScore {{ color: {TEXT}; font-size: 27px; font-weight: 900; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Secondary {{ color: {TEXT_2}; }}
QLabel#Green {{ color: {GREEN}; }}
QLabel#Gold {{ color: {GOLD}; }}
QLabel#Red {{ color: {RED}; }}
QPushButton {{
    background: {t['surface_2']}; color: {TEXT_2}; border: 1px solid {t['border']};
    border-radius: {max(6, r-3)}px; padding: 8px 14px; font-weight: 650;
}}
QPushButton:hover {{ background: {t['surface_3']}; color: {TEXT}; border-color: {t['border_strong']}; }}
QPushButton:focus {{ border-color: {t['focus']}; }}
QPushButton:pressed {{ background: {t['bg_2']}; }}
QPushButton:disabled {{ color:#56616a; background:{t['surface']}; border-color:{t['border']}; }}
QPushButton#Primary {{ color:{GREEN}; background:{GREEN_DARK}; border-color:#2d7241; }}
QPushButton#Primary:hover {{ background:{GREEN_SOFT}; border-color:{GREEN}; }}
QPushButton#Primary:pressed {{ background:#102b1a; border-color:#8cf0a6; padding-top:9px; padding-bottom:7px; }}
QPushButton#Danger {{ color:#ffdede; background:{RED_DARK}; border-color:#79353a; }}
QPushButton#Gold {{ color:{GOLD}; background:{GOLD_DARK}; border-color:#715c26; }}
QPushButton#Tab {{
    background:transparent; border:1px solid transparent; color:{MUTED};
    border-radius:{max(5, r-3)}px; padding:8px 18px;
}}
QPushButton#Tab:hover {{ color:{TEXT}; background:{t['surface']}; }}
QPushButton#Tab:checked {{ color:{accent}; background:{t['accent_soft']}; border-color:{t['border_strong']}; }}
QPushButton#Nav {{ background:transparent; border:none; border-radius:{max(5, r-3)}px; color:{MUTED}; padding:10px 16px; }}
QPushButton#Nav:hover {{ color:{TEXT}; background:{t['surface_2']}; }}
QPushButton#Nav:checked {{ color:{accent}; background:{t['accent_soft']}; }}
QToolButton#JourneyStage {{
    background:{t['metric']}; color:#89949c; border:1px solid {t['border']};
    border-radius:{max(5, r-3)}px; padding:5px; font-size:9px; font-weight:750;
}}
QToolButton#JourneyStage:hover {{ background:{t['surface_2']}; color:{TEXT}; border-color:{t['border_strong']}; }}
QToolButton#JourneyStage:checked {{ color:{accent}; border-color:{accent}; background:{t['accent_soft']}; }}
QToolButton#JourneyStage:disabled {{ color:#49545c; background:{t['bg_2']}; border-color:{t['border']}; }}
QPushButton#CalendarDay {{
    text-align:left; background:{t['metric']}; border:1px solid {t['border']};
    border-radius:{max(6, r-3)}px; padding:7px 9px; color:{TEXT_2};
}}
QPushButton#CalendarDay:hover {{ border-color:{t['border_strong']}; background:{t['surface_2']}; color:{TEXT}; }}
QProgressBar {{
    background:{t['surface_3']}; border:1px solid {t['border']}; border-radius:5px;
    min-height:10px; max-height:10px; color:transparent;
}}
QProgressBar::chunk {{ background:{accent}; border-radius:4px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:2px; }}
QScrollBar::handle:vertical {{ background:{t['scroll']}; min-height:34px; border-radius:4px; }}
QScrollBar::handle:vertical:hover {{ background:{t['scroll_hover']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0px; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{t['scroll']}; min-width:34px; border-radius:4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0px; }}
QComboBox, QLineEdit, QSpinBox, QTextEdit {{
    background:{t['input']}; color:{TEXT}; border:1px solid {t['border_strong']};
    border-radius:{max(5, r-3)}px; padding:7px 9px; selection-background-color:{t['selection']};
}}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color:{t['focus']}; }}
QComboBox QAbstractItemView {{ background:{t['surface_2']}; color:{TEXT}; selection-background-color:{t['selection']}; border:1px solid {t['border_strong']}; }}
QTableWidget {{
    background:{t['table']}; alternate-background-color:{t['table_alt']}; color:{TEXT};
    border:1px solid {t['border']}; gridline-color:{t['grid']};
    selection-background-color:{t['selection']}; selection-color:{TEXT};
}}
QTableWidget::item {{ padding:6px; border:none; }}
QHeaderView::section {{ background:{t['surface_2']}; color:{TEXT_2}; border:none; border-bottom:1px solid {t['border']}; padding:8px; font-weight:750; }}
QTableCornerButton::section {{ background:{t['surface_2']}; border:none; }}
QTabWidget::pane {{ border:1px solid {t['border']}; border-radius:{max(6, r-2)}px; background:{t['table']}; top:-1px; }}
QTabBar::tab {{ background:transparent; color:{MUTED}; border:none; padding:9px 16px; margin-right:3px; font-weight:700; }}
QTabBar::tab:hover {{ color:{TEXT}; }}
QTabBar::tab:selected {{ color:{accent}; border-bottom:2px solid {accent}; }}
QMessageBox {{ background:{t['surface']}; }}
"""


# Compatibility defaults for modules that build small inline style strings.
BG = ERA_DEFS["wild"]["bg"]
BG_2 = ERA_DEFS["wild"]["bg_2"]
SURFACE = ERA_DEFS["wild"]["surface"]
SURFACE_2 = ERA_DEFS["wild"]["surface_2"]
SURFACE_3 = ERA_DEFS["wild"]["surface_3"]
BORDER = ERA_DEFS["wild"]["border"]
BORDER_STRONG = ERA_DEFS["wild"]["border_strong"]
APP_STYLESHEET = _stylesheet(ERA_DEFS["wild"])
