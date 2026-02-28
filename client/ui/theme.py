"""Dark theme matching the Entropia Nexus website (nexus/src/lib/style.css)."""

import os as _os

_ASSETS_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(__file__)), "assets"
).replace("\\", "/")

# --- Color constants (mirror CSS custom properties) ---

# Backgrounds
PRIMARY = "#222222"        # --primary-color
SECONDARY = "#333333"      # --secondary-color
MAIN_DARK = "#1a1a1a"      # --main-color
HOVER = "#444444"           # --hover-color
DISABLED = "#555555"        # --disabled-color

# Borders
BORDER = "#555555"          # --border-color
BORDER_HOVER = "#666666"    # --border-hover

# Text
TEXT = "#ffffff"             # --text-color
TEXT_MUTED = "#aaaaaa"      # --text-muted

# Accent
ACCENT = "#60b0ff"           # --accent-color
ACCENT_HOVER = "#4a9eff"     # --accent-color-hover
ACCENT_LIGHT = "#253545"     # subtle accent tint for badge backgrounds

# Semantic
ERROR = "#ff6b6b"
ERROR_BG = "#4a2020"
SUCCESS = "#16a34a"
SUCCESS_BG = "#1a3a2a"
WARNING = "#fbbf24"
WARNING_BG = "#3a3020"

# Tables
TABLE_HEADER = "#222222"
TABLE_ROW = "#444444"
TABLE_ROW_ALT = "#3a3a3a"
TABLE_ROW_HOVER = "#333333"

# Font
FONT_FAMILY = "'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif"

# --- Layout constants ---

SIDEBAR_WIDTH = 48
SIDEBAR_INDICATOR_WIDTH = 3
TITLE_BAR_HEIGHT = 32
TITLE_BAR_CLOSE_HOVER = "#c42b1c"
STATUS_BAR_HEIGHT = 22

# --- Damage type colors (mirror CSS custom properties) ---

DAMAGE_COLORS = {
    "Impact": "#94a3b8",
    "Cut": "#e06060",
    "Stab": "#d48840",
    "Penetration": "#c8a830",
    "Shrapnel": "#88a040",
    "Burn": "#e07028",
    "Cold": "#38a8d8",
    "Acid": "#48b868",
    "Electric": "#9878c8",
}

# Tier-1 stats gradient (blue theme — weapons, attachments)
TIER1_BLUE_START = "#3a6d99"
TIER1_BLUE_END = "#2d5577"

# --- Object name constants (for targeted QSS rules) ---

PAGE_HEADER_OBJECT_NAME = "pageHeader"


def get_stylesheet() -> str:
    """Return the complete global QSS stylesheet for the application."""
    return f"""
/* ===== Base ===== */

QWidget {{
    background-color: {PRIMARY};
    color: {TEXT};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

/* Dark frame bars — ID selectors override QWidget type selector */
#iconSidebar {{
    background-color: {MAIN_DARK};
    border-right: 1px solid {BORDER};
}}

#statusBar {{
    background-color: {MAIN_DARK};
    border-top: 1px solid {BORDER};
}}

/* ===== Labels ===== */

QLabel {{
    background-color: transparent;
}}

QLabel#pageHeader {{
    font-size: 18px;
    font-weight: bold;
    padding: 4px 0px;
    margin-bottom: 4px;
}}

QLabel#summaryValue {{
    font-size: 16px;
    font-weight: bold;
}}

QLabel#mutedText {{
    color: {TEXT_MUTED};
    font-style: italic;
}}

/* ===== Buttons ===== */

QPushButton {{
    background-color: {SECONDARY};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {HOVER};
    border-color: {BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: {MAIN_DARK};
}}

QPushButton:disabled {{
    background-color: {SECONDARY};
    color: {DISABLED};
    border-color: {BORDER};
}}

QPushButton#accentButton {{
    background-color: {ACCENT};
    color: {MAIN_DARK};
    border: none;
    font-weight: bold;
}}

QPushButton#accentButton:hover {{
    background-color: {ACCENT_HOVER};
}}

/* ===== Text Inputs ===== */

QLineEdit, QSpinBox, QDoubleSpinBox, QKeySequenceEdit {{
    background-color: {MAIN_DARK};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 20px;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QKeySequenceEdit:focus {{
    border-color: {ACCENT};
}}

QLineEdit:read-only {{
    color: {TEXT_MUTED};
    background-color: {SECONDARY};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    background-color: {SECONDARY};
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    width: 16px;
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: {SECONDARY};
    border-left: 1px solid {BORDER};
    width: 16px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {HOVER};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_ASSETS_DIR}/arrow-up.svg);
    width: 8px;
    height: 8px;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_ASSETS_DIR}/arrow-down.svg);
    width: 8px;
    height: 8px;
}}

/* ===== ComboBox ===== */

QComboBox {{
    background-color: {MAIN_DARK};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 20px;
}}

QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    background-color: {SECONDARY};
    border-left: 1px solid {BORDER};
    width: 20px;
}}

QComboBox::down-arrow {{
    image: url({_ASSETS_DIR}/arrow-down.svg);
    width: 8px;
    height: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {SECONDARY};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: {HOVER};
    selection-color: {TEXT};
    outline: none;
}}

/* ===== GroupBox ===== */

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding: 16px 8px 8px 8px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {TEXT};
    background-color: {PRIMARY};
}}

/* ===== Table ===== */

QTableWidget {{
    background-color: {PRIMARY};
    gridline-color: {BORDER};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
}}

QTableWidget::item {{
    padding: 4px 8px;
}}

QTableWidget::item:selected {{
    background-color: {ACCENT};
    color: {TEXT};
}}

QTableWidget::item:hover {{
    background-color: {TABLE_ROW_HOVER};
}}

QHeaderView::section {{
    background-color: {TABLE_HEADER};
    color: {TEXT};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 4px 8px;
    font-weight: bold;
}}

/* ===== ScrollBar ===== */

QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {DISABLED};
    border-radius: 5px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {BORDER_HOVER};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {DISABLED};
    border-radius: 5px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {BORDER_HOVER};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* ===== Slider ===== */

QSlider::groove:horizontal {{
    height: 4px;
    background-color: {BORDER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {ACCENT_HOVER};
}}

/* ===== ProgressBar ===== */

QProgressBar {{
    background-color: {MAIN_DARK};
    border: 1px solid {BORDER};
    border-radius: 4px;
    text-align: center;
    color: {TEXT};
    min-height: 18px;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 3px;
}}

/* ===== TextEdit ===== */

QTextEdit {{
    background-color: {MAIN_DARK};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}

/* ===== ScrollArea ===== */

QScrollArea {{
    background-color: transparent;
    border: none;
}}

/* ===== Splitter ===== */

QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

/* ===== TabWidget (inner tabs, e.g. loadout page) ===== */

QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {PRIMARY};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {SECONDARY};
    color: {TEXT_MUTED};
    padding: 6px 16px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {PRIMARY};
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: {HOVER};
    color: {TEXT};
}}

/* ===== ToolTip ===== */

QToolTip {{
    background-color: {MAIN_DARK};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}

/* ===== Menu (system tray context menu) ===== */

QMenu {{
    background-color: {SECONDARY};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 24px;
}}

QMenu::item:selected {{
    background-color: {HOVER};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

/* ===== Splash Screen ===== */

QPushButton#splashLoginBtn {{
    background-color: {ACCENT};
    color: {TEXT};
    border: 1px solid {ACCENT};
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 24px;
    min-height: 36px;
}}

QPushButton#splashLoginBtn:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QPushButton#splashLoginBtn:pressed {{
    background-color: #3a8edf;
    border-color: #3a8edf;
}}

QPushButton#splashLoginBtn:disabled {{
    background-color: {DISABLED};
    border-color: {DISABLED};
    color: {TEXT_MUTED};
}}

QPushButton#splashOfflineBtn {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: 1px solid transparent;
    border-radius: 6px;
    font-size: 13px;
    padding: 8px 24px;
}}

QPushButton#splashOfflineBtn:hover {{
    color: {TEXT};
    background-color: {HOVER};
    border-color: {BORDER};
}}

QLabel#splashTitle {{
    font-size: 20px;
    font-weight: bold;
    color: {TEXT};
    background-color: transparent;
}}

QLabel#splashStatus {{
    font-size: 12px;
    color: {TEXT_MUTED};
    background-color: transparent;
}}

QPushButton#splashCloseBtn {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-radius: 4px;
    font-family: Arial, sans-serif;
    font-size: 18px;
    padding: 0px;
    margin: 0px;
}}

QPushButton#splashCloseBtn:hover {{
    background-color: {TITLE_BAR_CLOSE_HOVER};
    color: {TEXT};
}}
"""
