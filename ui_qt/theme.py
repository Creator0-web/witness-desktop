"""Visual tokens for the PySide6 WITNESS interface.

v7.49 keeps the palette deliberately restrained: charcoal neutrals, one
primary green, red only for losing/danger, and gold only for records/major
victories. Most of the polish comes from hierarchy, spacing, transparency,
and surface depth rather than adding more colors.
"""

BG = "#080b0e"
BG_2 = "#0b0f13"
SURFACE = "#10151a"
SURFACE_2 = "#151b21"
SURFACE_3 = "#1a2229"
BORDER = "#242d35"
BORDER_STRONG = "#33414b"
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

APP_STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QMainWindow {{ background: {BG}; }}
QLabel {{ background: transparent; border: none; }}
QFrame {{ background: transparent; border: none; }}
QToolTip {{
    background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    padding: 6px 8px;
}}
QFrame#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #11171c, stop:1 #0e1317);
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#CardStrong {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #12191e, stop:1 #0d1216);
    border: 1px solid {BORDER_STRONG};
    border-radius: 16px;
}}
QFrame#ActivityCard {{
    background: #10151a;
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#ActivityCard:hover {{
    background: #12191e;
    border-color: {BORDER_STRONG};
}}
QFrame#MetricTile {{
    background: #0d1216;
    border: 1px solid #202831;
    border-radius: 10px;
}}
QLabel#Eyebrow {{
    color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
}}
QLabel#SectionTitle {{
    color: {TEXT}; font-size: 15px; font-weight: 800;
}}
QLabel#PageTitle {{
    color: {TEXT}; font-size: 23px; font-weight: 900;
}}
QLabel#HugeScore {{
    color: {TEXT}; font-size: 37px; font-weight: 900;
}}
QLabel#LargeScore {{
    color: {TEXT}; font-size: 27px; font-weight: 900;
}}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Secondary {{ color: {TEXT_2}; }}
QLabel#Green {{ color: {GREEN}; }}
QLabel#Gold {{ color: {GOLD}; }}
QLabel#Red {{ color: {RED}; }}
QPushButton {{
    background: {SURFACE_2};
    color: {TEXT_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 650;
}}
QPushButton:hover {{
    background: {SURFACE_3}; color: {TEXT}; border-color: {BORDER_STRONG};
}}
QPushButton:focus {{ border-color: #3d7e50; }}
QPushButton:pressed {{ background: #0c1115; }}
QPushButton:disabled {{ color: #56616a; background: #101419; border-color: #1c2329; }}
QPushButton#Primary {{
    color: {GREEN}; background: {GREEN_DARK}; border-color: #2d7241;
}}
QPushButton#Primary:hover {{
    background: {GREEN_SOFT}; border-color: {GREEN};
}}
QPushButton#Primary:pressed {{
    background: #102b1a; border-color: #8cf0a6;
    padding-top: 9px; padding-bottom: 7px;
}}
QPushButton#Danger {{
    color: #ffdede; background: {RED_DARK}; border-color: #79353a;
}}
QPushButton#Gold {{
    color: {GOLD}; background: {GOLD_DARK}; border-color: #715c26;
}}
QPushButton#Tab {{
    background: transparent; border: 1px solid transparent; color: {MUTED};
    border-radius: 8px; padding: 8px 18px;
}}
QPushButton#Tab:hover {{ color: {TEXT}; background: #10161a; }}
QPushButton#Tab:checked {{
    color: {GREEN}; background: {GREEN_DARK}; border-color: #2d7241;
}}
QPushButton#Nav {{
    background: transparent; border: none; border-radius: 9px;
    color: {MUTED}; padding: 10px 16px;
}}
QPushButton#Nav:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QPushButton#Nav:checked {{ color: {GREEN}; background: {GREEN_DARK}; }}
QPushButton#CalendarDay {{
    text-align: left;
    background: #0d1216;
    border: 1px solid #202831;
    border-radius: 10px;
    padding: 7px 9px;
    color: {TEXT_2};
}}
QPushButton#CalendarDay:hover {{ border-color: {BORDER_STRONG}; background: #12191e; color: {TEXT}; }}
QProgressBar {{
    background: #1d252c; border: 1px solid #202830; border-radius: 5px;
    min-height: 10px; max-height: 10px; color: transparent;
}}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 4px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{ background: #27313a; min-height: 34px; border-radius: 4px; }}
QScrollBar::handle:vertical:hover {{ background: #34414b; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #27313a; min-width: 34px; border-radius: 4px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QComboBox, QLineEdit, QSpinBox, QTextEdit {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER_STRONG};
    border-radius: 8px; padding: 7px 9px; selection-background-color: {GREEN_DARK};
}}
QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: #397c4d; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; color: {TEXT}; selection-background-color: {GREEN_DARK};
    border: 1px solid {BORDER_STRONG};
}}
QTableWidget {{
    background: #0d1216; alternate-background-color: #10171c;
    color: {TEXT}; border: 1px solid {BORDER}; gridline-color: #1d252c;
    selection-background-color: {GREEN_DARK}; selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 6px; border: none; }}
QHeaderView::section {{
    background: {SURFACE_2}; color: {TEXT_2}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 8px; font-weight: 750;
}}
QTableCornerButton::section {{ background: {SURFACE_2}; border: none; }}
QTabWidget::pane {{
    border: 1px solid {BORDER}; border-radius: 10px; background: #0d1216;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {MUTED}; border: none;
    padding: 9px 16px; margin-right: 3px; font-weight: 700;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {GREEN}; border-bottom: 2px solid {GREEN}; }}
QMessageBox {{ background: {SURFACE}; }}
"""
