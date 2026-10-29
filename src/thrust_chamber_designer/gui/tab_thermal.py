import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt

from ..thermal.geometry import GROWTH, ChamberGeometry
from .widgets import PlotCanvas


class ThermalTab(QWidget):
    """Models and solver settings of the thermal simulation, the run with its progress, and the log."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        b = window.bindings
        layout = QHBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inputs = QWidget()
        left = QVBoxLayout(inputs)
        scroll.setWidget(inputs)
        th = lambda d: d.thermal

        box = QGroupBox("Heat transfer models")
        form = QFormLayout(box)
        form.addRow("Hot gas side", b.choice(th, "hot_gas_method", [("cinjarev", "Cinjarev (small engines)"),
                                                                    ("standard-bartz", "Standard Bartz"),
                                                                    ("modified-bartz", "Modified Bartz")]))
        form.addRow("Coolant side", b.choice(th, "cooling_method", [("gnielinski", "Gnielinski"),
                                                                    ("gnielinski-rough", "Gnielinski, rough channels"),
                                                                    ("dittus-boelter", "Dittus-Boelter"),
                                                                    ("dittus-boelter-simple", "Dittus-Boelter, simple")]))
        self.boiling = b.check(th, "boiling", "Nucleate boiling at the channel walls")
        form.addRow("", self.boiling)
        self.chf = b.choice(th, "chf_method", [("hall-mudawar", "Hall-Mudawar (corrected for ethanol)"), ("meyer", "Meyer (ethanol)"),
                                               ("gambill", "Gambill (any coolant)")])
        form.addRow("Critical heat flux", self.chf)
        self.post_chf = b.choice(th, "post_chf", [("meyer", "Meyer post-CHF branch (ethanol)"),
                                                  ("fallback", "Fall back to forced convection")])
        form.addRow("Beyond CHF", self.post_chf)
        form.addRow("Ambient temperature", b.number(th, "ambient_temperature", decimals=1, minimum=1, maximum=1000, suffix="K"))
        left.addWidget(box)

        box = QGroupBox("Solver")
        form = QFormLayout(box)
        form.addRow("Step along the contour", b.number(th, "step_size", scale=1e-3, decimals=2, minimum=0.1, maximum=100, step=0.5,
                                                       suffix="mm", tooltip="Distance between the 2D sections. Fewer sections are faster"))
        self.throat_step = b.number(th, "throat_step", scale=1e-3, decimals=2, minimum=0, maximum=100, step=0.1, suffix="mm",
                                    tooltip="Smaller step near the throat, where the heat flux peaks. It grows by %g times per section "
                                            "away from the fine zone up to the step along the contour" % GROWTH)
        self.throat_step.setSpecialValueText("Off")
        form.addRow("Step at the throat", self.throat_step)
        self.throat_zone = b.number(th, "throat_zone", decimals=1, minimum=0, maximum=1000, step=1, suffix="mm",
                                    tooltip="Distance upstream and downstream of the throat within which the step at the throat is used")
        form.addRow("Fine zone", self.throat_zone)
        self.sections_note = QLabel("")
        form.addRow("", self.sections_note)
        form.addRow("Cell size", b.number(th, "cell_size_factor", decimals=3, minimum=0.01, maximum=2, step=0.05,
                                          suffix="x inner wall", tooltip="Cell size of the 2D sections as a fraction of the thinnest inner wall"))
        form.addRow("Tolerance", b.number(th, "tolerance", decimals=3, minimum=1e-4, maximum=10, step=0.01, suffix="K"))
        form.addRow("Max iterations", b.number(th, "max_iter", integer=True, minimum=1, maximum=100000))
        form.addRow("Adaptive time step", b.number(th, "adaptive_up", decimals=2, minimum=1.0, maximum=5, step=0.1,
                                                   tooltip="Growth factor of the time step of transient runs"))
        self.transient = QCheckBox("Transient run")
        self.run_time = QDoubleSpinBox()
        self.run_time.setRange(0.01, 1000)
        self.run_time.setDecimals(2)
        self.run_time.setSuffix(" s")
        b.custom(self.transient, lambda: self.transient.setChecked(self.window.design.thermal.run_time is not None))
        b.custom(self.run_time, lambda: self.run_time.setValue(self.window.design.thermal.run_time or 3.0))
        self.transient.toggled.connect(self._run_time_changed)
        self.run_time.valueChanged.connect(self._run_time_changed)
        row = QHBoxLayout()
        row.addWidget(self.transient)
        row.addWidget(self.run_time, 1)
        form.addRow("Firing time", row)
        form.addRow("", b.check(th, "anchor_throat", "Section exactly at the throat"))
        form.addRow("", b.check(th, "save_section_figures", "Save a picture of every section (slow)"))
        left.addWidget(box)

        box = QGroupBox("Run")
        form = QFormLayout(box)
        self.folder = QLineEdit()
        browse = QPushButton("Browse...")
        browse.clicked.connect(self.browse)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        form.addRow("Results folder", row)
        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run thermal simulation")
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(window.run_thermal)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(window.cancel_thermal)
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        form.addRow(buttons)
        self.progress = QProgressBar()
        self.progress.setFormat("Not running")
        self.progress.setValue(0)
        form.addRow(self.progress)
        self.time_label = QLabel("")
        form.addRow(self.time_label)
        left.addWidget(box)
        left.addStretch(1)
        layout.addWidget(scroll, 2)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.live = PlotCanvas(figsize=(7, 4))
        splitter.addWidget(self.live)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("monospace", 9))
        self.log.setMaximumBlockCount(5000)
        splitter.addWidget(self.log)
        splitter.setSizes([450, 250])
        layout.addWidget(splitter, 3)

        self.started = None
        self.clock = QTimer(self, interval=1000)
        self.clock.timeout.connect(self._tick)
        self.points = []
        self._draw_live()

    def _run_time_changed(self, *_):
        self.window.design.thermal.run_time = self.run_time.value() if self.transient.isChecked() else None
        self.run_time.setEnabled(self.transient.isChecked())
        self.window.design_changed()

    def refresh(self):
        d = self.window.design
        self.run_time.setEnabled(d.thermal.run_time is not None)
        self.chf.setEnabled(d.thermal.boiling)
        self.post_chf.setEnabled(d.thermal.boiling)
        th = d.thermal
        graded = 0 < th.throat_step < th.step_size
        self.throat_zone.setEnabled(graded)
        nd = self.window.nozzle
        if nd is None:
            self.sections_note.setText("Solve the nozzle to see the number of sections")
            return
        # sections of the thermal model, against the same step everywhere
        x, y = nd.solution.wall_x / 1000, nd.solution.wall_y / 1000
        n = len(ChamberGeometry.from_contour(x, y, th.step_size, anchor_throat=th.anchor_throat, throat_step=th.throat_step,
                                             throat_zone=th.throat_zone / 1000).x)
        text = "%d sections" % n
        if graded:
            text += ", %d with %.2f mm everywhere" % (len(ChamberGeometry.from_contour(x, y, th.throat_step).x), th.throat_step * 1e3)
        elif th.throat_step >= th.step_size:
            text += " (the step at the throat is not smaller than the step along the contour)"
        self.sections_note.setText(text)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Results folder", self.folder.text() or os.path.expanduser("~"))
        if folder:
            self.folder.setText(folder)

    def default_folder(self):
        if self.folder.text():
            return self.folder.text()
        base = os.path.splitext(self.window.path)[0] if self.window.path else os.path.join(os.path.expanduser("~"), "Thrust Chamber Designer",
                                                                                         self.window.design.name or "design")
        return base + "_results"

    # ── run ──────────────────────────────────────────────────────────────
    def started_run(self, folder):
        self.folder.setText(folder)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setMaximum(0)          # busy until the first section is solved
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m sections")
        self.log.clear()
        self.points = []
        self.started = time.time()
        self.clock.start()
        self._tick()
        self._draw_live()

    def finished_run(self, text):
        if self.progress.maximum() == 0:
            self.progress.setMaximum(1)
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.clock.stop()
        self.time_label.setText(text + (" after %.0f s" % (time.time() - self.started) if self.started else ""))

    def _tick(self):
        if self.started is not None:
            elapsed = time.time() - self.started
            done, total = self.progress.value(), self.progress.maximum()
            text = "Running for %.0f s" % elapsed
            if done > 0 and total > 1:
                text += ", about %.0f s left" % (elapsed / done * (total - done))
            self.time_label.setText(text)

    def add_log(self, line):
        self.log.appendPlainText(line)

    def add_section(self, done, total, x, T_wall, T_coolant, q):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.points.append((x, T_wall, T_coolant, q))
        self._draw_live()

    def _draw_live(self):
        fig = self.live.clear()
        ax = fig.add_subplot()
        if self.points:
            pts = sorted(self.points)
            x, T_wall, T_c, q = (list(v) for v in zip(*pts))
            ax.plot(x, [t - 273.15 for t in T_wall], "r.-", label="Inner wall (hot gas side)")
            ax.plot(x, [t - 273.15 for t in T_c], "b.-", label="Coolant bulk")
            ax2 = ax.twinx()
            ax2.plot(x, [v / 1e6 for v in q], color="0.55", lw=0.8, ls="--", label="Heat flux")
            ax2.set_ylabel("Heat flux [MW/m$^2$]", color="0.4")
            ax.legend(loc="upper left", fontsize=8)
        nd = self.window.nozzle
        if nd is not None:
            ax.set_xlim(nd.solution.wall_x[0], nd.solution.wall_x[-1])
        ax.set_xlabel("x [mm]")
        ax.set_ylabel(r"Temperature [$^\circ$C]")
        ax.set_title("Sections as they are solved", fontsize=9)
        self.live.draw()
