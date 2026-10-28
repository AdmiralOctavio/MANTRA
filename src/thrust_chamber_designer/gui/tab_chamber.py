from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QSplitter, QTabWidget, QVBoxLayout, QWidget)

from .. import pipeline
from ..core import propellants as props
from ..nozzle import plots
from .widgets import PlotCanvas, fill_table, summary_table


class ChamberTab(QWidget):
    """Chamber and nozzle shape, the Method of Characteristics solution and the mass flows."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        b = window.bindings
        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        box = QGroupBox("Combustion chamber")
        form = QFormLayout(box)
        ch = lambda d: d.chamber
        form.addRow("Contraction ratio", b.number(ch, "contraction_ratio", decimals=2, minimum=1.5, maximum=100, step=0.5))
        form.addRow("Convergent slope", b.number(ch, "slope", decimals=1, minimum=5, maximum=80, step=1, suffix="deg"))
        form.addRow("Throat radius R1", b.number(ch, "R1", decimals=2, minimum=0.1, maximum=1000, step=1, suffix="mm",
                                                 tooltip="Radius of the wall arc upstream of the throat"))
        form.addRow("Inlet radius R2", b.number(ch, "R2", decimals=2, minimum=0.1, maximum=5000, step=1, suffix="mm",
                                                tooltip="Radius of the wall arc from the cylinder into the convergent"))
        self.lstar_sizing = b.check(ch, "lstar_sizing", "Chamber length from L*")
        form.addRow("", self.lstar_sizing)
        self.lstar = b.number(ch, "lstar", decimals=3, minimum=0.05, maximum=10, step=0.05, suffix="m")
        form.addRow("L*", self.lstar)
        self.lstar_hint = QLabel("")
        self.lstar_hint.setWordWrap(True)
        form.addRow("", self.lstar_hint)
        self.length = b.number(ch, "length", decimals=2, minimum=1, maximum=10000, step=1, suffix="mm",
                               tooltip="Injector face to throat")
        form.addRow("Chamber length", self.length)
        left.addWidget(box)

        box = QGroupBox("Nozzle (Method of Characteristics)")
        form = QFormLayout(box)
        nz = lambda d: d.nozzle
        form.addRow("Refinement", b.number(nz, "refinement", integer=True, minimum=10, maximum=1000,
                                           tooltip="Number of characteristics. More is finer and slower"))
        form.addRow("Nozzle length", b.number(nz, "shorten", scale=0.01, decimals=0, minimum=30, maximum=100, step=5, suffix="%",
                                              tooltip="Fraction of the full length nozzle that is kept"))
        left.addWidget(box)

        buttons = QHBoxLayout()
        self.solve_button = QPushButton("Solve nozzle")
        self.solve_button.setObjectName("primary")
        self.solve_button.clicked.connect(window.solve_nozzle)
        self.export_button = QPushButton("Export contour...")
        self.export_button.clicked.connect(self.export)
        self.export_button.setEnabled(False)
        buttons.addWidget(self.solve_button)
        buttons.addWidget(self.export_button)
        left.addLayout(buttons)
        self.status = QLabel("Not solved yet")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)
        layout.addLayout(left, 2)

        splitter = QSplitter(Qt.Orientation.Vertical)
        plot_box = QWidget()
        plot_layout = QVBoxLayout(plot_box)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        self.show_characteristics = QCheckBox("Show characteristics")
        self.show_characteristics.setChecked(True)
        self.show_characteristics.toggled.connect(self.draw)
        plot_layout.addWidget(self.show_characteristics)
        self.plot = PlotCanvas(figsize=(8, 4))
        plot_layout.addWidget(self.plot, 1)
        splitter.addWidget(plot_box)
        self.tables = QTabWidget()
        self.performance = summary_table([])
        self.flows = summary_table([])
        self.inputs = summary_table([])
        self.tables.addTab(self.performance, "Performance and geometry")
        self.tables.addTab(self.flows, "Mass flows")
        self.tables.addTab(self.inputs, "Inputs")
        splitter.addWidget(self.tables)
        splitter.setSizes([500, 300])
        layout.addWidget(splitter, 5)

    def refresh(self):
        d = self.window.design
        sizing = d.chamber.lstar_sizing
        self.lstar.setEnabled(sizing)
        self.length.setEnabled(not sizing)
        short, nominal, long = props.lstar_range(d.propellants.oxidiser, d.propellants.fuel)
        self.lstar_hint.setText("Typical for these propellants: %.2f (short), %.2f (nominal), %.2f m (elongated)" % (short, nominal, long))

    def mark_outdated(self):
        if self.window.nozzle is not None:
            self.status.setText("Inputs changed since the last solution. Solve again to update.")

    def show_solution(self, nd):
        self.show_tables(nd)
        s = nd.solution
        text = "Throat %.2f mm, exit %.2f mm (expansion ratio %.2f), total length %.1f mm, thrust %.1f N, mass flow %.4f kg/s" % (
            2 * s.throat_radius, 2 * s.exit_radius, s.expansion_ratio, s.wall_x[-1] - s.wall_x[0], s.thrust, s.mdot)
        if nd.warnings:
            text += "\n\nWarnings:\n- " + "\n- ".join(nd.warnings)
        self.status.setText(text)
        self.export_button.setEnabled(True)
        self.draw()

    def show_tables(self, nd):
        # also called when only the film or coolant fractions change: they change the split of the mass flow, not the nozzle
        rows = pipeline.nozzle_summary(nd)
        flow_names = ("Mass Flow", "Oxidiser Flow", "Fuel Flow", "Film Flow", "Coolant Flow", "O/F")
        outputs = [(n, v, u) for c, n, v, u in rows if c == "Output"]
        fill_table(self.performance, [r for r in outputs if not r[0].startswith(flow_names)])
        fill_table(self.flows, [r for r in outputs if r[0].startswith(flow_names)])
        fill_table(self.inputs, [(n, v, u) for c, n, v, u in rows if c == "Input"])

    def draw(self):
        nd = self.window.nozzle
        if nd is None:
            return
        from . import themes
        self.plot.set_figure(plots.characteristics_plot(nd.solution, self.show_characteristics.isChecked(), theme=themes.plot_theme()))

    def export(self):
        nd = self.window.nozzle
        if nd is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "Folder for params.csv, Contour.csv, Contour.dxf and the STL")
        if not folder:
            return
        try:
            pipeline.write_nozzle_outputs(nd, folder, dxf=True, stl=True)
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            return
        self.window.statusBar().showMessage("Contour written to " + folder, 5000)
