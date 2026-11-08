"""
LCARS chrome of the app: the elbows, bars and the column of buttons of a Starfleet console around the tabs. LcarsFrame holds the
tab widget in every theme; only in the LCARS theme (themes.py) it shows the elbows and the column, which then stands in for the tab bar,
and the bottom elbow shows the messages of the status bar.
"""

import datetime

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QGridLayout, QSizePolicy, QVBoxLayout, QWidget

# colours of the LCARS consoles of the 24th century
ORANGE = "#ff9900"
PEACH = "#ff9966"
ALMOND = "#ffcc99"
LILAC = "#cc99cc"
LAVENDER = "#9999cc"
PERIWINKLE = "#9999ff"
MARS = "#cc6666"
GOLD = "#ffcc66"

# colours of the buttons of the column, one per tab
BUTTON_COLORS = (LILAC, LAVENDER, PEACH, MARS, ALMOND, PERIWINKLE)

COLUMN = 120        # width of the column on the left
BAR = 24            # height of the bars along the top and the bottom
GAP = 5             # black gaps between the blocks
R_OUT = 50          # outer radius of an elbow
R_IN = 24           # inner radius of an elbow

# condensed fonts, the first one installed is taken: Antonio (Google Fonts) is closest to the lettering of the consoles, Bahnschrift
# comes with Windows 10 and 11
TITLE_FONTS = ("Antonio", "Swiss911 UCm BT", "Bahnschrift SemiBold Condensed", "Bahnschrift Condensed", "Arial Narrow")
TEXT_FONTS = ("Antonio", "Bahnschrift SemiCondensed", "Bahnschrift", "Arial Narrow")


def _first_family(names):
    families = set(QFontDatabase.families())
    return next((name for name in names if name in families), None)


def title_family():
    return _first_family(TITLE_FONTS)


def text_family():
    return _first_family(TEXT_FONTS)


def font(pixels, bold=False):
    f = QFont()
    family = title_family()
    if family:
        f.setFamily(family)
    f.setPixelSize(int(pixels))
    f.setBold(bold)
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    return f


def stardate(now=None):
    """A stardate for the bottom bar: the year and the fraction of it, in the style of the consoles (2026-11-08: 26853.6)"""
    now = now or datetime.datetime.now()
    start = datetime.datetime(now.year, 1, 1)
    length = (datetime.datetime(now.year + 1, 1, 1) - start).total_seconds()
    return "%05.1f" % ((now.year % 100) * 1000 + 1000 * (now - start).total_seconds() / length)


class Elbow(QWidget):
    """Top or bottom elbow: the corner of the column joined to a bar along the window, broken into blocks, with a title at its end.
    label: text in the corner, text: line in the black space next to the bar, title: text at the end of the bar"""

    def __init__(self, bottom=False, colors=(ORANGE, LILAC, PEACH, ORANGE), height=84, parent=None):
        super().__init__(parent)
        self.bottom = bottom
        self.colors = colors
        self.label = ""
        self.text = ""
        self.title = ""
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text(self, text):
        self.text = text
        self.update()

    def _y(self, y, h=0):
        # top of a rectangle of height h, drawn as if it were the top elbow
        return self.height() - y - h if self.bottom else y

    def _rect(self, x, y, w, h):
        return QRectF(x, self._y(y, h), w, h)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        elbow_color, block_color, long_color, cap_color = (QColor(c) for c in self.colors)

        # the elbow: the column and the start of the bar, with a large round outer corner and a small round inner one
        x1 = COLUMN + max(120, int(0.14 * w))
        path = QPainterPath()
        path.moveTo(0, h)
        path.lineTo(0, R_OUT)
        path.arcTo(QRectF(0, 0, 2 * R_OUT, 2 * R_OUT), 180, -90)
        path.lineTo(x1, 0)
        path.lineTo(x1, BAR)
        path.lineTo(COLUMN + R_IN, BAR)
        path.arcTo(QRectF(COLUMN, BAR, 2 * R_IN, 2 * R_IN), 90, 90)
        path.lineTo(COLUMN, h)
        path.closeSubpath()
        p.save()
        if self.bottom:
            p.translate(0, h)
            p.scale(1, -1)
        p.fillPath(path, elbow_color)
        p.restore()

        # title at the end of the bar, in the black between the blocks, its capitals as high as the bar, and a round cap after it
        title_font = font(BAR * 1.4)
        title_font.setPixelSize(max(8, round(title_font.pixelSize() * BAR / QFontMetricsF(title_font).capHeight())))
        p.setFont(title_font)
        title_w = QFontMetricsF(title_font).horizontalAdvance(self.title) if self.title else 0
        cap = 2 * BAR
        title_x = w - cap - GAP - 10 - title_w
        x = x1 + GAP
        short = 80
        if title_x - 10 - x > short + GAP + 40:
            p.fillRect(self._rect(x, 0, short, BAR), block_color)
            x += short + GAP
        if title_x - 10 > x:
            p.fillRect(self._rect(x, 0, title_x - 10 - x, BAR), long_color)
        cap_path = QPainterPath()
        cap_path.addRoundedRect(self._rect(w - cap, 0, cap, BAR), BAR / 2, BAR / 2)
        p.fillPath(cap_path, cap_color)
        p.fillRect(self._rect(w - cap, 0, BAR / 2, BAR), cap_color)
        if self.title:
            p.setPen(QColor(ORANGE))
            p.drawText(QPointF(title_x, h if self.bottom else BAR), self.title)

        # number in the corner, black on the colour of the elbow
        if self.label:
            p.setPen(QColor("#000000"))
            p.setFont(font(15))
            corner = QRectF(0, BAR + 6, COLUMN - 8, h - BAR - 12) if not self.bottom else QRectF(0, 6, COLUMN - 8, h - BAR - 12)
            p.drawText(corner, (Qt.AlignmentFlag.AlignBottom if not self.bottom else Qt.AlignmentFlag.AlignTop) | Qt.AlignmentFlag.AlignRight,
                       self.label)

        # line of text in the black space next to the bar, on the side of the content
        if self.text:
            p.setPen(QColor(PEACH))
            f = QFont()
            family = text_family()
            if family:
                f.setFamily(family)
            f.setPixelSize(18)
            p.setFont(f)
            area = QRectF(COLUMN + R_IN + 6, self._y(BAR + 4, h - BAR - 8), w - COLUMN - R_IN - 16, h - BAR - 8)
            text = p.fontMetrics().elidedText(self.text, Qt.TextElideMode.ElideMiddle, int(area.width()))
            p.drawText(area, Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if self.bottom else Qt.AlignmentFlag.AlignRight), text)
        p.end()


class ColumnButton(QAbstractButton):
    """A block of the column: number at the top, name at the bottom right, black on its colour; orange while its tab is shown"""

    def __init__(self, number, text, color, parent=None):
        super().__init__(parent)
        self.number = number
        self.color = QColor(color)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(COLUMN)
        self.setMinimumHeight(34)
        self.setMaximumHeight(52)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        p = QPainter(self)
        color = QColor(ORANGE) if self.isChecked() else self.color
        if self.isDown():
            color = QColor("#ffffff")
        elif self.underMouse():
            color = color.lighter(118)
        p.fillRect(self.rect(), color)
        if self.isChecked():
            # a black notch on the side of the content marks the tab that is shown
            p.fillRect(QRectF(self.width() - 10, 0, 4, self.height()), QColor("#000000"))
        p.setPen(QColor("#000000"))
        p.setFont(font(12))
        p.drawText(self.rect().adjusted(8, 3, -8, -3), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "%02d" % self.number)
        # the name as large as it fits
        size = 19
        while size > 11 and QFontMetricsF(font(size, self.isChecked())).horizontalAdvance(self.text()) > self.width() - 26:
            size -= 1
        p.setFont(font(size, bold=self.isChecked()))
        p.drawText(self.rect().adjusted(8, 3, -16, -3), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight, self.text())
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class Block(QWidget):
    """A plain block of the column, fills the space under the buttons"""

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedWidth(COLUMN)
        self.setMinimumHeight(GAP)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), self.color)
        p.end()


class LcarsFrame(QWidget):
    """Holds the tab widget of the main window. set_lcars(True) puts the LCARS elbows and the column of buttons around it and hides
    its tab bar, set_lcars(False) shows the tabs alone."""

    def __init__(self, tabs, version="", parent=None):
        super().__init__(parent)
        self.tabs = tabs
        self.lcars = False
        self.top = Elbow(False, (ORANGE, LILAC, PEACH, ORANGE), 84)
        self.top.label = "TCD %s" % version if version else "TCD"
        self.top.title = "Thrust Chamber Designer"
        self.bottom = Elbow(True, (LAVENDER, MARS, ALMOND, LAVENDER), 64)
        self.bottom.label = "MANTRA"
        self.bottom.title = "Stardate " + stardate()

        self.column = QWidget()
        column = QVBoxLayout(self.column)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(GAP)
        self.buttons = QButtonGroup(self)
        self.buttons.setExclusive(True)
        for i in range(tabs.count()):
            button = ColumnButton(i + 1, tabs.tabText(i).replace("&&", "&"), BUTTON_COLORS[i % len(BUTTON_COLORS)])
            self.buttons.addButton(button, i)
            column.addWidget(button)
        column.addWidget(Block(GOLD), 1)
        end = Block(PEACH)
        end.setFixedHeight(28)
        column.addWidget(end)
        self.buttons.idClicked.connect(tabs.setCurrentIndex)
        tabs.currentChanged.connect(self._tab_changed)
        self._tab_changed(tabs.currentIndex())

        self.grid = QGridLayout(self)
        self.grid.addWidget(self.top, 0, 0, 1, 2)
        self.grid.addWidget(self.column, 1, 0)
        self.grid.addWidget(tabs, 1, 1)
        self.grid.addWidget(self.bottom, 2, 0, 1, 2)
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(1, 1)
        self.set_lcars(False)

    def _tab_changed(self, i):
        button = self.buttons.button(i)
        if button is not None:
            button.setChecked(True)

    def set_status(self, text):
        self.bottom.set_text(text)

    def set_name(self, text):
        self.top.set_text(text)

    def set_lcars(self, on):
        self.lcars = on
        for widget in (self.top, self.bottom, self.column):
            widget.setVisible(on)
        self.tabs.tabBar().setVisible(not on)
        if on:
            self.bottom.title = "Stardate " + stardate()
            self.grid.setContentsMargins(6, 6, 6, 6)
            self.grid.setHorizontalSpacing(10)
            self.grid.setVerticalSpacing(GAP)
        else:
            self.grid.setContentsMargins(0, 0, 0, 0)
            self.grid.setSpacing(0)
