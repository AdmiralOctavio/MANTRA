"""
Looks of the app: Qt's Fusion style with a light or a dark palette, and 'Aero', a stylesheet after Windows Vista / 7 and the
Frutiger Aero look: sky gradient, glassy panels, glossy buttons and aqua highlights.
"""

import os

from PySide6.QtGui import QColor, QPalette
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
QSplitter::handle { background: transparent; }
QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: #c9e2f5; border: 1px solid #9ec3e2; }
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

THEMES = ("Light", "Dark", "Aero")


PLOT_THEMES = {"Light": "light", "Dark": "dark", "Aero": "aero"}
_current = DEFAULT


def plot_theme():
    """Look of the plots (plot_style) for the theme of the app"""
    return PLOT_THEMES.get(_current, "light")


def apply(app, name, window=None):
    global _current
    _current = name if name in THEMES else DEFAULT
    app.setStyle(QStyleFactory.create("Fusion"))
    if name == "Dark":
        app.setPalette(_palette(DARK))
        app.setStyleSheet(COMMON_QSS + "QLabel#warning { color: #f0a35e; }")
    elif name == "Aero":
        app.setPalette(_palette(AERO_PALETTE))
        icons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons").replace(os.sep, "/")
        app.setStyleSheet(AERO_QSS.replace("ICONS", icons) + COMMON_QSS)
    else:
        app.setPalette(_palette(LIGHT))
        app.setStyleSheet(COMMON_QSS)
    if window is not None:
        frame_colors(window, name)


def frame_colors(window, name):
    """Windows 11: title bar and window border in the colours of the Aero theme (sky blue glass), the system colours for the other
    themes. Does nothing on other systems and older Windows."""
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
        aero = name == "Aero"
        # DWMWA_BORDER_COLOR = 34, DWMWA_CAPTION_COLOR = 35, DWMWA_TEXT_COLOR = 36
        for attribute, color in ((34, "#6aaee0"), (35, "#d4eafa"), (36, "#0b2a45")):
            value = colorref(color) if aero else default
            set_attribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except Exception:
        pass
