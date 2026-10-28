"""
Building blocks of the desktop app: a matplotlib canvas, input fields bound to the attributes of the Design, and the editor for
quantities along the chamber (core.design.Profile).

Input fields show the values in the units of the label (bar, mm, %) and keep SI units in the Design: scale is the factor from the
shown value to the stored one (bar -> Pa: 1e5, mm -> m: 1e-3, % -> fraction: 0.01).
"""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLineEdit,
                               QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import plot_style
from ..core.design import Profile


class PlotCanvas(QWidget):
    """A matplotlib figure with the zoom / pan toolbar. set_figure() replaces the figure, e.g. with one of the thermal plots."""

    def __init__(self, parent=None, toolbar=True, figsize=(6, 4)):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(0, 0, 0, 0)
        self.canvas = None
        self.toolbar = None
        self.with_toolbar = toolbar
        self.set_figure(Figure(figsize=figsize, layout="constrained"))

    @property
    def figure(self):
        return self.canvas.figure

    def set_figure(self, figure):
        for widget in (self.toolbar, self.canvas):
            if widget is not None:
                self.layout_.removeWidget(widget)
                widget.deleteLater()
        if figure.get_layout_engine() is None and not any(getattr(ax, "name", "") == "3d" for ax in figure.axes):
            # constrained layout keeps the labels inside the canvas when the window is resized
            figure.set_layout_engine("constrained")
        self.canvas = FigureCanvasQTAgg(figure)
        self._style()
        self.canvas.setMinimumHeight(200)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if self.with_toolbar else None
        if self.toolbar is not None:
            self.layout_.addWidget(self.toolbar)
        self.layout_.addWidget(self.canvas)
        self.canvas.draw_idle()

    def clear(self):
        self.figure.clear()
        self.canvas.draw_idle()
        return self.figure

    def draw(self):
        self._style()
        self.canvas.draw_idle()

    def _style(self):
        # plots in the look of the theme of the app
        from . import themes
        plot_style.style_figure(self.figure, themes.plot_theme())


class Bindings:
    """Input widgets bound to attributes of the current Design. get_design() returns the design, section(design) the object that
    holds the attribute (e.g. lambda d: d.operating). refresh() shows the values of a newly loaded design."""

    def __init__(self, get_design, on_change=None):
        self.get_design = get_design
        self.on_change = on_change
        self.items = []
        self.loading = False

    def _target(self, section):
        return section(self.get_design())

    def _changed(self):
        if not self.loading and self.on_change is not None:
            self.on_change()

    def number(self, section, attr, scale=1.0, decimals=3, minimum=0.0, maximum=1e9, step=None, suffix="", integer=False,
               tooltip=""):
        if integer:
            w = QSpinBox()
            w.setRange(int(minimum), int(min(maximum, 2**31 - 1)))
        else:
            w = QDoubleSpinBox()
            w.setDecimals(decimals)
            w.setRange(minimum, maximum)
            w.setSingleStep(step if step is not None else 10 ** (-decimals + 1) if decimals > 1 else 1)
        if not integer:
            w.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        w.setKeyboardTracking(False)
        if suffix:
            w.setSuffix(" " + suffix)
        if tooltip:
            w.setToolTip(tooltip)

        def to_widget():
            value = getattr(self._target(section), attr)
            w.setValue(int(value) if integer else value / scale)

        def from_widget(value):
            setattr(self._target(section), attr, int(value) if integer else value * scale)
            self._changed()

        w.valueChanged.connect(from_widget)
        self.items.append((w, to_widget))
        return w

    def check(self, section, attr, text=""):
        w = QCheckBox(text)

        def to_widget():
            w.setChecked(bool(getattr(self._target(section), attr)))

        def from_widget(state):
            setattr(self._target(section), attr, w.isChecked())
            self._changed()

        w.toggled.connect(from_widget)
        self.items.append((w, to_widget))
        return w

    def choice(self, section, attr, options):
        """options: list of (stored value, shown text)"""
        w = QComboBox()
        for value, text in options:
            w.addItem(text, value)

        def to_widget():
            i = w.findData(getattr(self._target(section), attr))
            w.setCurrentIndex(max(i, 0))

        def from_widget(i):
            setattr(self._target(section), attr, w.itemData(i))
            self._changed()

        w.currentIndexChanged.connect(from_widget)
        self.items.append((w, to_widget))
        return w

    def text(self, section, attr):
        w = QLineEdit()

        def to_widget():
            w.setText(str(getattr(self._target(section), attr)))

        def from_widget():
            setattr(self._target(section), attr, w.text())
            self._changed()

        w.editingFinished.connect(from_widget)
        self.items.append((w, to_widget))
        return w

    def profile(self, section, attr, scale=1.0, decimals=3, suffix="", minimum=0.0, maximum=1e6):
        w = ProfileEditor(scale=scale, decimals=decimals, suffix=suffix, minimum=minimum, maximum=maximum)

        def to_widget():
            w.set_profile(getattr(self._target(section), attr))

        def from_widget():
            setattr(self._target(section), attr, w.profile())
            self._changed()

        w.changed.connect(from_widget)
        self.items.append((w, to_widget))
        return w

    def custom(self, widget, to_widget):
        self.items.append((widget, to_widget))
        return widget

    def refresh(self):
        self.loading = True
        try:
            for widget, to_widget in self.items:
                widget.blockSignals(True)
                try:
                    to_widget()
                finally:
                    widget.blockSignals(False)
        finally:
            self.loading = False


class ProfileEditor(QWidget):
    """A quantity along the chamber: one value, or a table of points (x [mm], value) interpolated linearly."""
    changed = Signal()

    def __init__(self, scale=1.0, decimals=3, suffix="", minimum=0.0, maximum=1e6, parent=None):
        super().__init__(parent)
        self.scale = scale
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.constant = QRadioButton("Constant")
        self.varying = QRadioButton("Along chamber")
        self.value = QDoubleSpinBox()
        self.value.setDecimals(decimals)
        self.value.setRange(minimum, maximum)
        self.value.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        self.value.setKeyboardTracking(False)
        if suffix:
            self.value.setSuffix(" " + suffix)
        row.addWidget(self.constant)
        row.addWidget(self.value, 1)
        row.addWidget(self.varying)
        layout.addLayout(row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["x [mm]", "value" + (" [" + suffix + "]" if suffix else "")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(140)
        buttons = QHBoxLayout()
        self.add = QPushButton("Add point")
        self.remove = QPushButton("Remove point")
        buttons.addWidget(self.add)
        buttons.addWidget(self.remove)
        buttons.addStretch(1)
        self.table_box = QWidget()
        box = QVBoxLayout(self.table_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.table)
        box.addLayout(buttons)
        layout.addWidget(self.table_box)

        self.constant.setChecked(True)
        self.table_box.setVisible(False)
        self.constant.toggled.connect(self._mode)
        self.value.valueChanged.connect(lambda _: self.changed.emit())
        self.table.itemChanged.connect(lambda _: self.changed.emit())
        self.add.clicked.connect(self._add_row)
        self.remove.clicked.connect(self._remove_row)

    def _mode(self, constant):
        self.value.setEnabled(constant)
        self.table_box.setVisible(not constant)
        if not constant and self.table.rowCount() == 0:
            # start the table with the constant value at the throat
            self._add_row(0.0, self.value.value())
        self.changed.emit()

    def _add_row(self, x=None, value=None):
        r = self.table.rowCount()
        if x is None or isinstance(x, bool):
            x = float(self.table.item(r - 1, 0).text()) + 10 if r else 0.0
            value = float(self.table.item(r - 1, 1).text()) if r else self.value.value()
        self.table.blockSignals(True)
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem("%g" % x))
        self.table.setItem(r, 1, QTableWidgetItem("%g" % value))
        self.table.blockSignals(False)
        self.changed.emit()

    def _remove_row(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True) or [self.table.rowCount() - 1]
        for r in rows:
            if r >= 0:
                self.table.removeRow(r)
        self.changed.emit()

    def profile(self):
        if self.constant.isChecked():
            return Profile(self.value.value() * self.scale)
        points = []
        for r in range(self.table.rowCount()):
            try:
                points.append((float(self.table.item(r, 0).text()), float(self.table.item(r, 1).text()) * self.scale))
            except (AttributeError, ValueError):
                continue
        return Profile(self.value.value() * self.scale, points)

    def set_profile(self, profile):
        self.blockSignals(True)
        self.table.blockSignals(True)
        self.value.setValue(profile.value / self.scale)
        self.table.setRowCount(0)
        for x, v in profile.points:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem("%g" % x))
            self.table.setItem(r, 1, QTableWidgetItem("%g" % (v / self.scale)))
        (self.varying if profile.points else self.constant).setChecked(True)
        self.value.setEnabled(not profile.points)
        self.table_box.setVisible(bool(profile.points))
        self.table.blockSignals(False)
        self.blockSignals(False)


def summary_table(rows, parent=None):
    """Table of (parameter, value, unit) rows."""
    table = QTableWidget(0, 3, parent)
    table.setHorizontalHeaderLabels(["Parameter", "Value", "Unit"])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    fill_table(table, rows)
    return table


def fill_table(table, rows):
    table.setRowCount(0)
    for name, value, unit in rows:
        r = table.rowCount()
        table.insertRow(r)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            text = str(value)
        else:
            text = "%.5g" % value
        for c, t in enumerate((name, text, unit)):
            item = QTableWidgetItem(t)
            if c == 1:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
