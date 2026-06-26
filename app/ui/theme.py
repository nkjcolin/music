"""Dark theme stylesheet and small icon helpers."""

import qtawesome as qta

# Palette
BG = "#16181d"
BG_ALT = "#1e2128"
CARD = "#23272f"
CARD_HOVER = "#2a2f38"
BORDER = "#2f343d"
TEXT = "#e6e8ec"
TEXT_DIM = "#9aa0aa"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#8d72ff"
ACCENT_DIM = "#5b43c4"
GOOD = "#3ecf8e"
WARN = "#ffb454"
BAD = "#ff5c69"

STATUS_COLORS = {
    "Pending": TEXT_DIM,
    "Queued": TEXT_DIM,
    "Checking": WARN,
    "Downloading": ACCENT,
    "Processing": WARN,
    "Fetching lyrics": WARN,
    "Tagging": WARN,
    "Done": GOOD,
    "Skipped": WARN,
    "Error": BAD,
    "Cancelled": TEXT_DIM,
}


def icon(name: str, color: str = TEXT):
    """Return a qtawesome icon by Font Awesome name."""
    return qta.icon(name, color=color)


STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QWidget#root {{ background: {BG}; }}

/* Sidebar */
QWidget#sidebar {{
    background: {BG_ALT};
    border-right: 1px solid {BORDER};
}}
QLabel#logo {{
    font-size: 18px;
    font-weight: 700;
    padding: 18px 16px 12px 16px;
    color: {TEXT};
}}
QPushButton#navButton {{
    text-align: left;
    padding: 11px 16px;
    border: none;
    border-radius: 8px;
    margin: 2px 10px;
    color: {TEXT_DIM};
    background: transparent;
}}
QPushButton#navButton:hover {{ background: {CARD_HOVER}; color: {TEXT}; }}
QPushButton#navButton:checked {{ background: {ACCENT}; color: white; font-weight: 600; }}

/* Headings */
QLabel#pageTitle {{ font-size: 22px; font-weight: 700; }}
QLabel#sectionLabel {{ color: {TEXT_DIM}; font-weight: 600; }}

/* Inputs */
QLineEdit, QComboBox, QSpinBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 12px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: none;
}}

/* Buttons */
QPushButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {CARD_HOVER}; }}
QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {ACCENT_DIM}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; background: {BG_ALT}; }}

/* Segmented toggle */
QPushButton#segment {{ border-radius: 8px; padding: 9px 18px; }}
QPushButton#segment:checked {{ background: {ACCENT}; border: none; color: white; font-weight: 600; }}

/* Inline option pills (bitrate / codec / resolution) — all choices visible */
QPushButton#segOption {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 12px;
    color: {TEXT};
}}
QPushButton#segOption:hover {{ border: 1px solid {ACCENT}; }}
QPushButton#segOption:checked {{
    background: {ACCENT}; border: 1px solid {ACCENT}; color: white; font-weight: 600;
}}

/* Labeled "chips" on the Download page (reflow with the window) */
QFrame#chip {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#chipLabel {{ color: {TEXT_DIM}; font-weight: 600; }}
/* Combos inside chips read as obvious, clickable dropdowns. */
QFrame#chip QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 5px 10px;
}}
QFrame#chip QComboBox:hover {{ border: 1px solid {ACCENT}; }}
QFrame#chip QComboBox:focus {{ border: 1px solid {ACCENT}; }}
QFrame#chip QComboBox::drop-down {{ border: none; width: 22px; }}
QFrame#chip QComboBox::down-arrow {{ width: 10px; height: 10px; }}

/* Cards / queue rows */
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#queueRow {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#queueRow:hover {{ background: {CARD_HOVER}; }}
QFrame#clickableRow {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QFrame#clickableRow:hover {{ background: {CARD_HOVER}; border: 1px solid {ACCENT}; }}

/* Progress */
QProgressBar {{
    background: {BG_ALT};
    border: none;
    border-radius: 5px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

/* Log */
QTextEdit {{
    background: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    color: {TEXT_DIM};
}}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollArea {{ border: none; }}

/* Mini-player bar */
QFrame#miniBar {{
    background: {BG_ALT};
    border-top: 1px solid {BORDER};
}}

/* Player */
QLabel#cover {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QListWidget#lyrics {{
    background: transparent;
    border: none;
    font-size: 15px;
    outline: none;
}}
QListWidget#lyrics::item {{ padding: 6px 4px; }}
QListWidget#songList {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 4px;
    outline: none;
}}
QListWidget#songList::item {{ padding: 8px; border-radius: 6px; }}
QListWidget#songList::item:hover {{ background: {CARD_HOVER}; }}
QListWidget#songList::item:selected {{ background: {ACCENT}; color: white; }}

QSlider::groove:horizontal {{
    height: 6px; background: {BG_ALT}; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 14px; margin: -5px 0; border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {BORDER}; border-radius: 5px; background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; }}
"""
