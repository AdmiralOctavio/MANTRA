import os
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from ..core.design import Design
from ..thermal import throttle
from .widgets import PlotCanvas

VIEWS = {"film": "Film as modelled", "no_film": "No credit for the film", "design_file_film": "Own schedule, film as modelled",
         "design_file_no_film": "Own schedule, no credit for the film"}

# schedule table: header, text of a result
COLUMNS = (("Pc [%]", lambda r: "%.0f" % (r.pc_fraction * 100)),
           ("O/F", lambda r: "%.2f" % r.of_ratio),
           ("Feed O/F", lambda r: "%.2f" % r.of_feed),
           ("Jacket [bar]", lambda r: "%.1f" % (r.p_inlet / 1e5)),
           ("Thrust [N]", lambda r: "%.0f" % r.thrust),
           ("Wall [K]", lambda r: "%.0f" % r.T_wall),
           ("q / CHF", lambda r: "%.2f" % r.chf_ratio),
           ("Post-CHF", lambda r: "%d" % r.n_post_chf),
           ("Failed", lambda r: "%d" % r.n_failed),
           ("Subcool [K]", lambda r: "%.0f" % r.subcooling_min),
           ("Y", lambda r: "%.2f" % r.Y),
           ("Life [firings]", lambda r: "%.3g" % r.life_startup))


def parse_numbers(text):
    return [float(value) for value in text.replace(";", ",").split(",") if value.strip()]


def parse_schedule(text):
    # "100:4.4, 50:3.2" to [(1.0, 4.4), (0.5, 3.2)]
    points = []
    for point in text.replace(";", ",").split(","):
        if point.strip():
            pc, of = point.split(":")
            points.append((float(pc) / 100, float(of)))
    return points


class ThrottleTab(QWidget):
    """Range and limits of the throttle analysis, the run with its progress, the map as it fills up and the schedules."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        b = window.bindings
        t = lambda d: d.throttle
        layout = QHBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inputs = QWidget()
        left = QVBoxLayout(inputs)
        scroll.setWidget(inputs)

        note = QLabel("Solves every chamber pressure with every core O/F on the contour of the nozzle, with and without credit for the film, "
                      "and reads the O/F schedules off the map. The throttle valve is taken to be upstream of the channels, so the "
                      "jacket pressure falls with the chamber pressure.")
        note.setWordWrap(True)
        left.addWidget(note)

        box = QGroupBox("Map")
        form = QFormLayout(box)
        self.levels = QLineEdit()
        self.levels.setToolTip("Chamber pressures of the map in % of the design chamber pressure, separated by commas. 100 is always included")
        self.of_values = QLineEdit()
        self.of_values.setToolTip("Core O/F values of the map, separated by commas. The design O/F is always included")
        self.own = QLineEdit()
        self.own.setPlaceholderText("Pc %:O/F, e.g. 100:4.4, 50:3.2, 30:2.8")
        self.own.setToolTip("Points of your own schedule, solved on top of the schedules read off the map")
        b.custom(self.levels, lambda: self.levels.setText(", ".join("%g" % (f * 100) for f in window.design.throttle.pc_fractions)))
        b.custom(self.of_values, lambda: self.of_values.setText(", ".join("%g" % o for o in window.design.throttle.of_ratios)))
        b.custom(self.own, lambda: self.own.setText(", ".join("%g:%g" % (f * 100, o) for f, o in window.design.throttle.schedule)))
        self.levels.editingFinished.connect(self._levels_changed)
        self.of_values.editingFinished.connect(self._ofs_changed)
        self.own.editingFinished.connect(self._schedule_changed)
        form.addRow("Chamber pressures", self.levels)
        form.addRow("Core O/F values", self.of_values)
        form.addRow("Own schedule", self.own)
        self.points_note = QLabel("")
        self.points_note.setWordWrap(True)
        form.addRow("", self.points_note)
        form.addRow("Step along the contour", b.number(t, "map_step_size", scale=1e-3, decimals=2, minimum=0.1, maximum=100, step=0.5, suffix="mm",
                                                       tooltip="Mesh of the map only. The schedules are solved with the settings of the Thermal tab"))
        form.addRow("Cell size", b.number(t, "map_cell_size_factor", decimals=3, minimum=0.01, maximum=2, step=0.05, suffix="x inner wall",
                                          tooltip="Mesh of the map only. The schedules are solved with the settings of the Thermal tab"))
        left.addWidget(box)

        box = QGroupBox("Limits")
        form = QFormLayout(box)
        form.addRow("Lowest subcooling", b.number(t, "min_subcooling", decimals=1, minimum=0, maximum=500, step=5, suffix="K",
                                                  tooltip="Lowest allowed distance of the coolant from its saturation temperature"))
        form.addRow("", b.check(t, "allow_post_chf", "Accept the post-CHF branch above 17 bar"))
        left.addWidget(box)

        box = QGroupBox("Run")
        form = QFormLayout(box)
        self.jobs = QSpinBox()
        self.jobs.setRange(1, os.cpu_count() or 1)
        self.jobs.setValue(max(1, (os.cpu_count() or 2) - 2))
        self.jobs.setToolTip("Points solved at the same time")
        form.addRow("Processes", self.jobs)
        self.folder = QLineEdit()
        self.folder.setReadOnly(True)               # the Results folder of the Thermal tab, in a folder 'throttle'
        form.addRow("Results folder", self.folder)
        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run throttle analysis")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(window.run_throttle)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(window.cancel_throttle)
        self.cancel_button.setEnabled(False)
        self.open_button = QPushButton("Open results...")
        self.open_button.clicked.connect(self.open_results)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        form.addRow(buttons)
        form.addRow(self.open_button)
        self.progress = QProgressBar()
        self.progress.setFormat("Not running")
        self.progress.setValue(0)
        form.addRow(self.progress)
        self.time_label = QLabel("")
        form.addRow(self.time_label)
        left.addWidget(box)
        left.addStretch(1)
        layout.addWidget(scroll, 2)

        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("Show"))
        self.view = QComboBox()
        self.view.currentIndexChanged.connect(self._view_changed)
        row.addWidget(self.view, 1)
        self.state = QLabel("")
        row.addWidget(self.state, 2)
        column.addLayout(row)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.map = PlotCanvas(figsize=(8, 5.5))
        splitter.addWidget(self.map)
        self.details = QTabWidget()
        self.table = QTableWidget(0, len(COLUMNS) + 1)
        self.table.setHorizontalHeaderLabels([name for name, _ in COLUMNS] + ["Notes"])
        for index, tip in ((3, "Coolant pressure at the channel inlet"), (7, "Sections on the post-CHF branch"),
                            (8, "Sections where boiling can not carry the heat flux"), (9, "Lowest subcooling of the coolant"),
                            (11, "Lowest ligament life, start-up bound")):
            self.table.horizontalHeaderItem(index).setToolTip(tip)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.details.addTab(self.table, "Schedule")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("monospace", 9))
        self.log.setMaximumBlockCount(5000)
        self.details.addTab(self.log, "Log")
        splitter.addWidget(self.details)
        splitter.setSizes([560, 240])
        column.addWidget(splitter, 1)
        layout.addWidget(right, 4)

        self.started = None
        self.stage = "map"
        self.outdated_map = False
        self.clock = QTimer(self, interval=1000)
        self.clock.timeout.connect(self._tick)
        self.clear_results()

    # ── inputs ───────────────────────────────────────────────────────────
    def _apply(self, field, parse, name):
        try:
            value = parse(field.text())
        except ValueError:
            self.window.bindings.refresh()
            self.window.statusBar().showMessage("Could not read the %s, the values are unchanged" % name, 8000)
            return None
        return value

    def _levels_changed(self):
        values = self._apply(self.levels, parse_numbers, "chamber pressures")
        if values and all(0 < v <= 100 for v in values) and [v / 100 for v in values] != self.window.design.throttle.pc_fractions:
            self.window.design.throttle.pc_fractions = [v / 100 for v in values]
            self.window.design_changed()
        self.window.bindings.refresh()

    def _ofs_changed(self):
        values = self._apply(self.of_values, parse_numbers, "O/F values")
        if values is not None and all(v > 0 for v in values) and values != self.window.design.throttle.of_ratios:
            self.window.design.throttle.of_ratios = values
            self.window.design_changed()
        self.window.bindings.refresh()

    def _schedule_changed(self):
        values = self._apply(self.own, parse_schedule, "schedule")
        if values is not None and values != self.window.design.throttle.schedule:
            self.window.design.throttle.schedule = values
            self.window.design_changed()
        self.window.bindings.refresh()

    def refresh(self):
        d = self.window.design
        fractions, ofs = throttle.map_axes(d)
        modes = len(throttle.credit_modes(d))
        self.of_values.setPlaceholderText("Automatic: " + ", ".join("%g" % o for o in ofs))
        self.points_note.setText("%d points: %d chamber pressures x %d O/F values%s" % (len(fractions) * len(ofs) * modes, len(fractions), len(ofs),
                                                                                       " x 2 for the film" if modes == 2 else ""))
        self.folder.setText(self.default_folder())
        self.run_button.setEnabled(d.thermal.boiling and not self.window.throttle.running)
        self.state.setText("The design changed after this run" if self.run_design is not None and d != self.run_design else "")

    def default_folder(self):
        return os.path.join(self.window.thermal_tab.default_folder(), "throttle")

    # ── results ──────────────────────────────────────────────────────────
    def clear_results(self):
        self.map_results = []
        self.schedules = {}
        self.run_design = None
        self.log.clear()
        self.table.setRowCount(0)
        self._fill_views()
        self.draw()

    def _fill_views(self):
        # the map of a film mode can be looked at even if no schedule came out of it
        current = self.view.currentData()
        modes = throttle.credit_modes(self.run_design or self.window.design)
        names = set(self.schedules) | {"film" if film else "no_film" for film in modes}
        self.view.blockSignals(True)
        self.view.clear()
        for name in VIEWS:
            if name in names:
                self.view.addItem(VIEWS[name], name)
        self.view.setCurrentIndex(max(self.view.findData(current), 0))
        self.view.blockSignals(False)

    def _view_changed(self, *_):
        self.show_schedule()
        self.draw()

    def _film(self):
        return (self.view.currentData() or "film") in ("film", "design_file_film")

    def draw(self):
        self.outdated_map = False
        fig = self.map.clear()
        design = self.run_design or self.window.design
        results = self.schedules.get(self.view.currentData(), [])
        throttle.draw_map(fig, self.map_results, design.throttle, self._film(), [(r.pc_fraction, r.of_ratio) for r in results],
                          throttle.map_axes(design), fontsize=7)
        self.map.draw()

    def show_schedule(self):
        results = self.schedules.get(self.view.currentData(), [])
        design = self.run_design or self.window.design
        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            if r.error:
                cells = ["%.0f" % (r.pc_fraction * 100), "%.2f" % r.of_ratio] + [""] * (len(COLUMNS) - 2) + [r.error.strip().splitlines()[-1]]
            else:
                state = "" if throttle.passes(r, design.throttle) else "Outside the limits. "
                cells = [text(r) for _, text in COLUMNS] + [state + throttle.notes(r)]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column < len(COLUMNS):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setToolTip(text)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(len(COLUMNS), QHeaderView.ResizeMode.Stretch)

    def show_results(self, map_results, schedules):
        self.map_results = map_results
        self.schedules = schedules
        self._fill_views()
        self.show_schedule()
        self.draw()
        self.refresh()
        self.details.setCurrentWidget(self.table)

    def open_results(self):
        folder = QFileDialog.getExistingDirectory(self, "Folder of a throttle analysis (with design.json and throttle_map.csv)", self.default_folder())
        if not folder:
            return
        if not (os.path.exists(os.path.join(folder, "design.json")) and os.path.exists(os.path.join(folder, "throttle_map.csv"))):
            QMessageBox.warning(self, "Not a throttle analysis", "The folder needs design.json and throttle_map.csv of a throttle analysis.")
            return
        self.run_design = Design.load(os.path.join(folder, "design.json"))
        self.show_results(*throttle.load_results(folder))

    # ── run ──────────────────────────────────────────────────────────────
    def started_run(self, design, folder):
        self.clear_results()
        self.run_design = design
        self.folder.setText(folder)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.details.setCurrentWidget(self.log)
        self.stage = "map"
        self.progress.setMaximum(0)          # busy until the first point is solved
        self.progress.setValue(0)
        self.progress.setFormat("Map: %v / %m points")
        self.started = time.time()
        self.clock.start()
        self._tick()

    def finished_run(self, text):
        if self.progress.maximum() == 0:
            self.progress.setMaximum(1)
        self.run_button.setEnabled(self.window.design.thermal.boiling)
        self.cancel_button.setEnabled(False)
        self.clock.stop()
        self.time_label.setText(text + (" after %.0f s" % (time.time() - self.started) if self.started else ""))
        if self.outdated_map:
            self.draw()

    def _tick(self):
        if self.outdated_map:
            self.draw()                      # at most once per tick, a redraw of the whole map takes a moment
        if self.started is not None:
            elapsed = time.time() - self.started
            done, total = self.progress.value(), self.progress.maximum()
            text = "Running for %.0f s" % elapsed
            if self.stage == "map" and done > 0 and total > 1:
                text += ", map done in about %.0f s" % (elapsed / done * (total - done))
            self.time_label.setText(text)

    def add_log(self, line):
        self.log.appendPlainText(line)

    def add_point(self, stage, done, total, result):
        if stage != self.stage:
            self.stage = stage
            self.progress.setFormat("Schedules: %v / %m points")
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.add_log("%s %d / %d: %.0f %% Pc, O/F %.2f, %s%s" % (stage.capitalize(), done, total, result.pc_fraction * 100, result.of_ratio,
                                                                 "film" if result.film else "no film credit",
                                                                 ", not solved" if result.error else ", wall %.0f K, q/CHF %.2f" % (result.T_wall, result.chf_ratio)))
        if result.error:
            self.add_log(result.error)
        if stage == "map":
            self.map_results.append(result)
            self.outdated_map = True
