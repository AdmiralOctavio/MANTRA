"""
Looks of the app: Qt's Fusion style with a light or a dark palette, 'Aero', a stylesheet after Windows Vista / 7 and the
Frutiger Aero look: sky gradient, glassy panels, glossy buttons and aqua highlights, and 'LCARS', the consoles of a 24th century
starship: black, with elbows, pill buttons and blocks of orange, peach, lilac and lavender, and condensed capitals (see lcars.py).
"""

import os

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QStyleFactory

DEFAULT = "Light"


def _palette(colors):
    p = QPalette()
    for role, color in colors.items():
        p.setColor(role, QColor(color))
    return p


R = QPalette.ColorRole

LIGHT = {R.Window: "#f3f4f6", R.WindowText: "#1d2330", R.Base: "#ffffff", R.AlternateBase: "#eef1f5", R.Text: "#1d2330",
         R.Button: "#e9ecf1", R.ButtonText: "#1d2330", R.Highlight: "#2f6fd6", R.HighlightedText: "#ffffff", R.ToolTipBase: "#ffffe8",
         R.ToolTipText: "#1d2330", R.PlaceholderText: "#8a93a3"}

DARK = {R.Window: "#1f232b", R.WindowText: "#d8dde8", R.Base: "#161a20", R.AlternateBase: "#22262e", R.Text: "#d8dde8",
        R.Button: "#2a2f39", R.ButtonText: "#d8dde8", R.Highlight: "#4a8ff0", R.HighlightedText: "#ffffff", R.ToolTipBase: "#2a2f39",
        R.ToolTipText: "#d8dde8", R.PlaceholderText: "#7b8496", R.BrightText: "#ff6b6b"}

AERO_PALETTE = {R.Window: "#dcecf8", R.WindowText: "#0b2a45", R.Base: "#ffffff", R.AlternateBase: "#eef7fd", R.Text: "#0b2a45",
                R.Button: "#e6f3fc", R.ButtonText: "#0b2a45", R.Highlight: "#3d9be9", R.HighlightedText: "#ffffff",
                R.ToolTipBase: "#f7fcff", R.ToolTipText: "#0b2a45", R.PlaceholderText: "#7d97ad"}

LCARS_PALETTE = {R.Window: "#000000", R.WindowText: "#ffcc99", R.Base: "#000000", R.AlternateBase: "#0c0c16", R.Text: "#ffcc99",
                 R.Button: "#ff9966", R.ButtonText: "#000000", R.Highlight: "#ff9900", R.HighlightedText: "#000000",
                 R.ToolTipBase: "#000000", R.ToolTipText: "#ffcc99", R.PlaceholderText: "#8a6a55", R.BrightText: "#ff5555",
                 R.Link: "#9999ff", R.Light: "#9999cc", R.Midlight: "#7a7aa6", R.Mid: "#444466", R.Dark: "#222233",
                 R.Shadow: "#000000"}

LCARS_QSS = """
QMainWindow, QDialog { background: #000000; }
QMenuBar { background: #000000; padding: 6px 8px 0 8px; spacing: 5px; }
QMenuBar::item { background: #ff9966; color: #000000; padding: 3px 16px 3px 20px; border-radius: 9px; }
QMenuBar::item:selected { background: #ffcc99; }
QMenuBar::item:pressed { background: #ff9900; }
QMenu { background: #000000; border: 2px solid #ff9900; padding: 6px 4px; }
QMenu::item { color: #ff9966; padding: 5px 26px 5px 26px; border-radius: 10px; margin: 1px 2px; }
QMenu::item:selected { background: #ff9900; color: #000000; }
QMenu::item:disabled { color: #664433; }
QMenu::separator { height: 3px; background: #cc99cc; margin: 5px 8px; }
QMenu::indicator { width: 10px; height: 10px; left: 9px; border-radius: 5px; }
QMenu::indicator:checked { background: #cc99cc; }
QStatusBar { background: #000000; color: #ff9966; }
QStatusBar::item { border: none; }

QTabWidget::pane { border: none; border-top: 4px solid #9999cc; top: -1px; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab { background: #9999cc; color: #000000; padding: 4px 18px 4px 22px; margin: 0 4px 5px 0; min-width: 50px; }
QTabBar::tab:first { border-top-left-radius: 12px; border-bottom-left-radius: 12px; }
QTabBar::tab:last { border-top-right-radius: 12px; border-bottom-right-radius: 12px; }
QTabBar::tab:only-one { border-radius: 12px; }
QTabBar::tab:selected { background: #ff9900; }
QTabBar::tab:hover:!selected { background: #ccccff; }

QGroupBox {
    /* a small elbow: a thick bar on the left bent into a thin one along the top, the title breaks the top bar */
    background: #000000; border: none; border-left: 10px solid #cc99cc; border-top: 4px solid #cc99cc;
    border-top-left-radius: 18px; margin-top: 12px; padding: 16px 4px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 30px; top: 3px; padding: 0 8px; color: #cc99cc;
    background: #000000; font-weight: bold;
}
QGroupBox::indicator { width: 18px; height: 11px; border: 2px solid #cc99cc; border-radius: 7px; background: #000000; }
QGroupBox::indicator:checked { background: #ff9900; border-color: #ff9900; }

QPushButton {
    background: #ff9966; color: #000000; border: none; border-radius: 11px; padding: 4px 12px 4px 18px; min-height: 14px;
    text-align: right;
}
QPushButton:hover { background: #ffcc99; }
QPushButton:pressed { background: #ffffff; }
QPushButton:checked { background: #ff9900; }
QPushButton:disabled { background: #4d3326; color: #000000; }
QPushButton#primary { background: #ff9900; font-weight: bold; padding: 5px 12px 5px 20px; }
QPushButton#primary:hover { background: #ffbb44; }
QPushButton#primary:pressed { background: #ffffff; }
QPushButton#primary:disabled { background: #5c3d00; }
QToolButton { background: transparent; border: none; border-radius: 9px; padding: 3px; color: #ffcc99; }
QToolButton:hover { background: #333355; }
QToolButton:checked, QToolButton:pressed { background: #9999cc; }
QToolBar { background: #000000; border: none; spacing: 3px; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    /* a field with a peach cap on the left, the steppers or the drop down are the round cap on the right */
    background: #140c06; color: #ffcc99; border: none; border-left: 6px solid #ff9966; border-radius: 0;
    border-top-right-radius: 10px; border-bottom-right-radius: 10px; padding: 3px 6px; min-height: 16px;
    selection-background-color: #ff9900; selection-color: #000000;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-left-color: #ff9900; background: #2a1808; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled { color: #6b5545; border-left-color: #4d3326;
    background: #0a0604; }
QLineEdit { border-radius: 0; }
QAbstractSpinBox QLineEdit, QComboBox QLineEdit { border: none; background: transparent; padding: 0; }
QAbstractSpinBox { padding-right: 22px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { subcontrol-origin: border; width: 20px; background: #ff9966; border: none; }
QAbstractSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 10px; border-bottom: 1px solid #000000; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 10px; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover { background: #ffcc99; }
QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed { background: #ffffff; }
QAbstractSpinBox::up-button:disabled, QAbstractSpinBox::down-button:disabled { background: #4d3326; }
QAbstractSpinBox::up-arrow { image: url(ICONS/lcars_arrow_up.svg); width: 7px; height: 7px; }
QAbstractSpinBox::down-arrow { image: url(ICONS/lcars_arrow_down.svg); width: 7px; height: 7px; }
QComboBox { padding-right: 28px; }
QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right; width: 24px; border: none; background: #ff9966;
    border-top-right-radius: 10px; border-bottom-right-radius: 10px; }
QComboBox::drop-down:hover { background: #ffcc99; }
QComboBox::down-arrow { image: url(ICONS/lcars_arrow_down.svg); width: 8px; height: 8px; }
QComboBox QAbstractItemView { background: #000000; color: #ffcc99; border: 2px solid #ff9900; outline: none;
    selection-background-color: #ff9900; selection-color: #000000; }

QPlainTextEdit, QTextEdit, QTableView, QTableWidget, QListView, QListWidget {
    background: #000000; color: #ffcc99; border: none; border-left: 6px solid #9999cc;
    selection-background-color: #ff9900; selection-color: #000000; gridline-color: #2a2a40;
}
QTableView, QListView { alternate-background-color: #0c0c16; }
QTableView::item:selected, QListView::item:selected { background: #ff9900; color: #000000; }
QTableView::item:hover, QListView::item:hover { background: #1c1c33; }
QHeaderView { background: #000000; border: none; }
QHeaderView::section { background: #cc99cc; color: #000000; border: none; border-right: 3px solid #000000;
    border-bottom: 3px solid #000000; padding: 3px 8px; }
QHeaderView::section:last { border-right: none; border-top-right-radius: 10px; }
QTableCornerButton::section { background: #cc99cc; border: none; }

QProgressBar { background: #000000; border: 2px solid #9999cc; border-radius: 0; color: #ffffff; font-weight: bold;
    text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #ff9900; width: 12px; margin: 2px 1px; }

QScrollArea, QScrollArea > QWidget > QWidget { background: #000000; }
QScrollBar:vertical { background: #0c0c16; width: 12px; margin: 0; border: none; }
QScrollBar:horizontal { background: #0c0c16; height: 12px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #9999cc; min-height: 30px; border-radius: 5px; margin: 1px; }
QScrollBar::handle:horizontal { background: #9999cc; min-width: 30px; border-radius: 5px; margin: 1px; }
QScrollBar::handle:hover { background: #ff9966; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: none; background: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QSplitter::handle { background: #000000; }
QSplitter::handle:vertical { height: 6px; border-top: 2px solid #000000; border-bottom: 2px solid #000000; background: #333355; }
QSplitter::handle:horizontal { width: 6px; border-left: 2px solid #000000; border-right: 2px solid #000000; background: #333355; }

QSlider::groove:horizontal { height: 8px; border-radius: 4px; background: #222233; }
QSlider::sub-page:horizontal { background: #9999cc; border-radius: 4px; }
QSlider::handle:horizontal { width: 14px; margin: -7px 0; border-radius: 4px; background: #ff9900; }
QSlider::handle:horizontal:hover { background: #ffcc99; }
QSlider::groove:horizontal:disabled { background: #14141f; }
QSlider::sub-page:horizontal:disabled { background: #333355; }
QSlider::handle:horizontal:disabled { background: #4d3326; }

QCheckBox, QRadioButton, QLabel { background: transparent; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 20px; height: 11px; border: 2px solid #9999cc; border-radius: 7px; background: #000000; }
QCheckBox::indicator:hover { border-color: #ffcc99; }
QCheckBox::indicator:checked { background: #ff9900; border-color: #ff9900; }
QCheckBox::indicator:disabled { border-color: #333355; background: #000000; }
QCheckBox::indicator:checked:disabled { background: #5c3d00; border-color: #5c3d00; }
QRadioButton::indicator { width: 11px; height: 11px; border: 2px solid #9999cc; border-radius: 7px; background: #000000; }
QRadioButton::indicator:hover { border-color: #ffcc99; }
QRadioButton::indicator:checked { background: #ff9900; border-color: #ff9900; }
QRadioButton::indicator:disabled { border-color: #333355; }

QToolTip { background: #000000; color: #ffcc99; border: 2px solid #ff9900; padding: 4px; }
QLabel#warning { color: #ff5555; }
"""

# widgets whose text is set in capitals in the LCARS theme. Not the labels and fields: their units (mm, MPa, mN) need their case
LCARS_CAPITALS = ("QPushButton", "QTabBar", "QHeaderView", "QMenuBar", "QMenu", "QToolButton")

COMMON_QSS = """
QPushButton#primary { font-weight: bold; padding: 6px 14px; }
QLabel#warning { color: #b8641a; }
"""

AERO_QSS = """
QMainWindow, QDialog {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #bfe3fb, stop:0.35 #e4f4fe, stop:0.75 #f5fbff, stop:1 #d6f0d2);
}
QMenuBar {
    /* top edge of the window: a glass bar from sky blue into a hint of green, like the frames of Vista / 7 */
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f4faff, stop:0.35 #dcefff, stop:0.7 #cfe8f9, stop:1 #d6f1e2);
    border-bottom: 1px solid #8cc0e4;
}
QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 3px; }
QMenuBar::item:selected { background: rgba(255, 255, 255, 170); border: 1px solid #8cc4ef; }
QMenu { background: #f8fcff; border: 1px solid #8fb7da; }
QMenu::item { padding: 5px 22px; }
QMenu::item:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e5f3fd, stop:1 #c5e3fa); color: #0b2a45;
                       border: 1px solid #8cc4ef; border-radius: 3px; }
QStatusBar {
    /* bottom edge of the window, the same glass as the menu bar */
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d3eafb, stop:0.6 #d8eef9, stop:1 #d4f0de);
    border-top: 1px solid #8cc0e4; color: #123a5e;
}
QTabWidget::pane { border: 1px solid #9ec3e2; border-radius: 6px; background: rgba(255, 255, 255, 120); top: -1px; }
QTabBar::tab {
    /* faint blue glass, the same as a selected row of a table */
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f2f9ff, stop:0.48 #ddeefc, stop:0.5 #cfe6f8, stop:1 #e1f0fc);
    border: 1px solid #9cc6e6; border-bottom: none; border-top-left-radius: 7px; border-top-right-radius: 7px;
    padding: 6px 16px; margin-right: 2px; color: #0b2a45;
}
QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e3f2fe, stop:0.5 #f1f9ff, stop:1 #ffffff);
    border: 1px solid #5aa7e6; border-top: 2px solid #3d9be9; border-bottom: none; font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f4fbff, stop:0.48 #d3edfd, stop:0.5 #b9e0fa, stop:1 #d6effd);
    border-color: #6db6ea;
}
QTableView, QListView { alternate-background-color: #f3f9fe; gridline-color: #d6e7f4; }
QTableView::item:selected, QListView::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f1f8fe, stop:1 #d3e8f9);
    color: #0b2a45; border-top: 1px solid #a9d1f0; border-bottom: 1px solid #a9d1f0;
}
QTableView::item:hover, QListView::item:hover { background: rgba(203, 230, 250, 110); }
QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,215), stop:1 rgba(240,248,255,170));
    border: 1px solid #a8cbe6; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 12px; padding: 1px 8px; color: #0f4c81; font-weight: bold;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #dff0fd); border: 1px solid #a8cbe6; border-radius: 6px;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fdfeff, stop:0.45 #e9f4fd, stop:0.46 #d4e9fa, stop:1 #e2f1fd);
    border: 1px solid #7fa9cf; border-radius: 4px; padding: 5px 12px; color: #0b2a45;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f4fbff, stop:0.45 #d9f0fe, stop:0.46 #b7e1fc, stop:1 #d0ecfd);
    border-color: #3c95db;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c6e5fa, stop:0.45 #a9d8f7, stop:0.46 #8ecbf3, stop:1 #b3dcf6);
    border-color: #2c6fae;
}
QPushButton:disabled { color: #8ba4b8; border-color: #b8cfe2; background: #eef5fb; }
QPushButton#primary {
    color: white; font-weight: bold; border: 1px solid #2a7a2a;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b9f08a, stop:0.45 #6fcf3d, stop:0.46 #4cb521, stop:1 #6fd440);
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #cff7a8, stop:0.45 #83dc52, stop:0.46 #5cc52f, stop:1 #84e256);
}
QPushButton#primary:disabled { color: #e5f2dc; border-color: #9cc48c; background: #a9d394; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTableWidget, QListWidget {
    background: white; border: 1px solid #9ec3e2; border-radius: 3px; padding: 2px 4px;
    selection-background-color: #3d9be9;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #3c95db; }
QComboBox::drop-down { border-left: 1px solid #9ec3e2; width: 18px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fdfeff, stop:0.5 #e3f1fc, stop:0.51 #d3e8f9, stop:1 #e6f3fd); }
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:0.5 #eef6fd, stop:0.51 #e1effb, stop:1 #f2f8fe);
    border: none; border-right: 1px solid #c3dbef; border-bottom: 1px solid #a8cbe6; padding: 4px;
}
QProgressBar { border: 1px solid #7fa9cf; border-radius: 4px; background: #f2f8fd; text-align: center; height: 18px; }
QProgressBar::chunk {
    border-radius: 3px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c5f59d, stop:0.45 #74d84a, stop:0.46 #4fbb27, stop:1 #84e05a);
}
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea { border: none; }
/* scroll bars of glass: a clear track and a glossy handle that turns aqua under the mouse */
QScrollBar:vertical { background: rgba(255, 255, 255, 110); width: 14px; margin: 0; border: 1px solid #c3dbef; border-radius: 7px; }
QScrollBar:horizontal { background: rgba(255, 255, 255, 110); height: 14px; margin: 0; border: 1px solid #c3dbef; border-radius: 7px; }
QScrollBar::handle:vertical { min-height: 30px; margin: 1px; border: 1px solid #7fa9cf; border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fdfeff, stop:0.45 #dcedfb, stop:0.46 #c2def6, stop:1 #dbecfb); }
QScrollBar::handle:horizontal { min-width: 30px; margin: 1px; border: 1px solid #7fa9cf; border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fdfeff, stop:0.45 #dcedfb, stop:0.46 #c2def6, stop:1 #dbecfb); }
QScrollBar::handle:vertical:hover, QScrollBar::handle:vertical:pressed { border-color: #3c95db;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f4fbff, stop:0.45 #c3e8fd, stop:0.46 #8fd2fa, stop:1 #c2e8fc); }
QScrollBar::handle:horizontal:hover, QScrollBar::handle:horizontal:pressed { border-color: #3c95db;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f4fbff, stop:0.45 #c3e8fd, stop:0.46 #8fd2fa, stop:1 #c2e8fc); }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; border: none; background: none; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
/* a short grip in the middle of the handle of a splitter shows where to drag */
QSplitter::handle:vertical { height: 7px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(255,255,255,0),
    stop:0.46 rgba(255,255,255,0), stop:0.47 #a3cbe9, stop:0.53 #a3cbe9, stop:0.54 rgba(255,255,255,0), stop:1 rgba(255,255,255,0));
    margin: 2px 0; border-radius: 1px; }
QSplitter::handle:horizontal { width: 7px; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0),
    stop:0.46 rgba(255,255,255,0), stop:0.47 #a3cbe9, stop:0.53 #a3cbe9, stop:0.54 rgba(255,255,255,0), stop:1 rgba(255,255,255,0));
    margin: 0 2px; border-radius: 1px; }
/* tool bars of the plots: buttons of glass that show under the mouse. No background for the tool bar itself: matplotlib takes its
   icons in white if the tool bar tells a dark background, and a clear one counts as black */
QToolBar { border: none; spacing: 2px; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 3px; }
QToolButton:hover { border-color: #8cc4ef;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8fcff, stop:0.48 #dff1fd, stop:0.5 #c5e4fa, stop:1 #def1fd); }
QToolButton:pressed, QToolButton:checked { border-color: #3c95db;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #c6e5fa, stop:0.48 #a9d8f7, stop:0.5 #8ecbf3, stop:1 #b3dcf6); }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: #c9e2f5; border: 1px solid #9ec3e2; }
QSlider::sub-page:horizontal { height: 6px; border-radius: 3px; border: 1px solid #5aa7e6;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b6ecff, stop:0.5 #55b7f0, stop:1 #2f8ad6); }
QSlider::handle:horizontal:hover { border-color: #2a7a2a;
    background: qradialgradient(cx:0.4, cy:0.3, radius:0.8, fx:0.4, fy:0.3, stop:0 #ffffff, stop:0.5 #a6e87c, stop:1 #4cb521); }
QSlider::handle:horizontal { width: 14px; margin: -6px 0; border-radius: 7px; border: 1px solid #3c80bf;
    background: qradialgradient(cx:0.4, cy:0.3, radius:0.8, fx:0.4, fy:0.3, stop:0 #ffffff, stop:0.5 #8fd0fb, stop:1 #2f8ad6); }
QCheckBox, QRadioButton, QLabel { background: transparent; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 13px; height: 13px; border: 1px solid #6d9ccc;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #dcebf7);
}
QCheckBox::indicator { border-radius: 2px; }
QRadioButton::indicator { border-radius: 7px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #3c95db; }
QCheckBox::indicator:checked { image: url(ICONS/check.svg); }
QRadioButton::indicator:checked {
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.4, fy:0.35,
        stop:0 #b6ecff, stop:0.45 #2f8ad6, stop:0.55 #e9f4fd, stop:1 #e9f4fd);
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { border-color: #b8cfe2; background: #eef5fb; }
QAbstractSpinBox { padding-right: 18px; }
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {
    subcontrol-origin: border; width: 16px; border-left: 1px solid #9ec3e2;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fdfeff, stop:0.5 #e3f1fc, stop:0.51 #d3e8f9, stop:1 #e6f3fd);
}
QAbstractSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 3px; }
QAbstractSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 3px; }
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f4fbff, stop:0.5 #d9f0fe, stop:0.51 #b7e1fc, stop:1 #d0ecfd);
}
QAbstractSpinBox::up-arrow { image: url(ICONS/arrow_up.svg); width: 7px; height: 7px; }
QAbstractSpinBox::down-arrow { image: url(ICONS/arrow_down.svg); width: 7px; height: 7px; }
QComboBox::down-arrow { image: url(ICONS/arrow_down.svg); width: 8px; height: 8px; }
QToolTip { background: #f7fcff; color: #0b2a45; border: 1px solid #8fb7da; border-radius: 4px; padding: 4px; }
"""

THEMES = ("Light", "Dark", "Aero", "LCARS")


PLOT_THEMES = {"Light": "light", "Dark": "dark", "Aero": "aero", "LCARS": "lcars"}
_current = DEFAULT
_base_font = None           # font of the app before a theme changed it
_capitals = None            # font of the widgets in capitals in the LCARS theme, None in the other themes


def plot_theme():
    """Look of the plots (plot_style) for the theme of the app"""
    return PLOT_THEMES.get(_current, "light")


def _fonts(app, lcars):
    """The LCARS theme sets the app in a condensed font, with the buttons, tabs, headers and menus in capitals; the other themes in
    the font of the system"""
    global _base_font, _capitals
    if _base_font is None:
        _base_font = QFont(app.font())
    _capitals = None
    # setFont without a class name also drops the fonts of the classes
    if not lcars:
        app.setFont(_base_font)
        return
    from . import lcars as lcars_module
    font = QFont(_base_font)
    family = lcars_module.text_family()
    if family:
        font.setFamily(family)
    app.setFont(font)
    capitals = QFont(font)
    capitals.setCapitalization(QFont.Capitalization.AllUppercase)
    for name in LCARS_CAPITALS:
        app.setFont(capitals, name)
    _capitals = capitals


def capitals_font():
    """Font of the buttons, tabs and menus in the LCARS theme, None in the other themes. The main window sets it on its tab bars
    and menus directly: they do not take the fonts of their classes."""
    return _capitals


def apply(app, name, window=None):
    global _current
    _current = name if name in THEMES else DEFAULT
    name = _current
    app.setStyle(QStyleFactory.create("Fusion"))
    _fonts(app, name == "LCARS")
    icons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons").replace(os.sep, "/")
    if name == "Dark":
        app.setPalette(_palette(DARK))
        app.setStyleSheet(COMMON_QSS + "QLabel#warning { color: #f0a35e; }")
    elif name == "Aero":
        app.setPalette(_palette(AERO_PALETTE))
        app.setStyleSheet(AERO_QSS.replace("ICONS", icons) + COMMON_QSS)
    elif name == "LCARS":
        app.setPalette(_palette(LCARS_PALETTE))
        app.setStyleSheet(COMMON_QSS + LCARS_QSS.replace("ICONS", icons))
    else:
        app.setPalette(_palette(LIGHT))
        app.setStyleSheet(COMMON_QSS)
    from . import sounds
    sounds.player.set_theme(app, name == "LCARS")
    if window is not None:
        if hasattr(window, "set_lcars"):
            window.set_lcars(name == "LCARS")
        if hasattr(window, "set_backdrop"):
            window.set_backdrop(name)
        frame_colors(window, name)


def frame_colors(window, name):
    """Windows 11: title bar and window border in the colours of the Aero theme (sky blue glass) or the LCARS theme (black with an
    orange border), the system colours for the other themes. Does nothing on other systems and older Windows."""
    import sys
    if sys.platform != "win32":
        return
    try:
        if sys.getwindowsversion().build < 22000:
            return
        import ctypes
        hwnd = int(window.winId())
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute

        def colorref(hex_color):
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            return ctypes.c_uint(r | g << 8 | b << 16)

        default = ctypes.c_uint(0xFFFFFFFF)                 # DWMWA_COLOR_DEFAULT
        colors = {"Aero": ("#6aaee0", "#d4eafa", "#0b2a45"), "LCARS": ("#ff9900", "#000000", "#ff9900")}.get(name)
        # DWMWA_BORDER_COLOR = 34, DWMWA_CAPTION_COLOR = 35, DWMWA_TEXT_COLOR = 36
        for i, attribute in enumerate((34, 35, 36)):
            value = colorref(colors[i]) if colors else default
            set_attribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
