import copy

import numpy as np
from matplotlib.patches import Wedge
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import pipeline
from ..core import propellants as props
from ..core.design import FilmPort
from ..thermal.materials import MATERIALS
from .widgets import PlotCanvas
from .worker import run_in_thread


class CoolingTab(QWidget):
    """Coolant, film cooling, cooling channels and wall material, with a preview of the channels on the contour of the nozzle."""

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

        # coolant
        box = QGroupBox("Coolant")
        form = QFormLayout(box)
        co = lambda d: d.coolant
        self.fluids = QLineEdit()
        self.fluids.setToolTip("CoolProp fluid names, separated by commas, e.g. Ethanol, Water")
        self.fractions = QLineEdit()
        self.fractions.setToolTip("Mass fractions of the fluids, separated by commas, adding up to 1")
        b.custom(self.fluids, lambda: self.fluids.setText(", ".join(self.window.design.coolant.fluids)))
        b.custom(self.fractions, lambda: self.fractions.setText(", ".join("%g" % w for w in self.window.design.coolant.mass_fractions)))
        self.fluids.editingFinished.connect(self._fluids_changed)
        self.fractions.editingFinished.connect(self._fluids_changed)
        use_fuel = QPushButton("Use fuel")
        use_fuel.setToolTip("Set the coolant to the fuel of the Engine tab")
        use_fuel.clicked.connect(self.use_fuel)
        row = QHBoxLayout()
        row.addWidget(self.fluids, 1)
        row.addWidget(use_fuel)
        form.addRow("Fluids", row)
        form.addRow("Mass fractions", self.fractions)
        self.coolant_note = QLabel("")
        self.coolant_note.setWordWrap(True)
        self.coolant_note.setObjectName("warning")
        form.addRow("", self.coolant_note)
        form.addRow("Coolant flow", b.number(co, "fuel_fraction", scale=0.01, decimals=1, minimum=1, maximum=100, step=5, suffix="% of fuel feed"))
        form.addRow("Inlet temperature", b.number(co, "inlet_temperature", decimals=1, minimum=10, maximum=1000, step=1, suffix="K"))
        form.addRow("Inlet pressure", b.number(co, "inlet_pressure", scale=1e5, decimals=2, minimum=1, maximum=1000, step=1, suffix="bar"))
        form.addRow("Coolant enters at", b.choice(co, "start", [("nozzle", "Nozzle exit (counterflow)"), ("injector", "Injector")]))
        left.addWidget(box)

        # film cooling
        box = QGroupBox("Film cooling")
        form = QFormLayout(box)
        fi = lambda d: d.film
        self.film_note = QLabel("")
        self.film_note.setWordWrap(True)
        form.addRow("Injector film", self.film_note)
        form.addRow("Injection velocity", b.number(fi, "injection_velocity", decimals=1, minimum=0.1, maximum=200, step=1, suffix="m/s"))
        form.addRow("Injector diameter", b.number(fi, "injector_diameter", scale=1e-3, decimals=2, minimum=0.01, maximum=20, step=0.1, suffix="mm"))
        self.ports = QTableWidget(0, 4)
        self.ports.setHorizontalHeaderLabels(["x [mm]", "% of fuel feed", "v [m/s]", "d [mm]"])
        self.ports.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ports.verticalHeader().setVisible(False)
        self.ports.setMaximumHeight(120)
        self.ports.itemChanged.connect(self._ports_changed)
        b.custom(self.ports, self._show_ports)
        row = QHBoxLayout()
        add, remove = QPushButton("Add ring"), QPushButton("Remove ring")
        add.clicked.connect(self._add_port)
        remove.clicked.connect(self._remove_port)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        form.addRow(QLabel("Rings of ports in the chamber wall, fed from the cooling channels:"))
        form.addRow(self.ports)
        form.addRow(row)
        left.addWidget(box)

        # channels
        box = QGroupBox("Cooling channels")
        form = QFormLayout(box)
        cg = lambda d: d.channels
        form.addRow("Number of channels", b.number(cg, "n", integer=True, minimum=1, maximum=1000,
                                                   tooltip="At the injector end, up to the first change below"))
        self.splits = QTableWidget(0, 2)
        self.splits.setHorizontalHeaderLabels(["x [mm]", "Channels from x on"])
        self.splits.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.splits.verticalHeader().setVisible(False)
        self.splits.setMaximumHeight(110)
        self.splits.setToolTip("Changes of the number of channels along the chamber, e.g. fewer around the throat where the channels would "
                               "be too narrow. Each channel should split into a whole number of channels")
        self.splits.itemChanged.connect(self._splits_changed)
        b.custom(self.splits, self._show_splits)
        row = QHBoxLayout()
        add, remove = QPushButton("Add change"), QPushButton("Remove change")
        add.clicked.connect(self._add_split)
        remove.clicked.connect(self._remove_split)
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        form.addRow("Channel splits", self.splits)
        form.addRow("", row)
        self.splits_note = QLabel("")
        self.splits_note.setWordWrap(True)
        self.splits_note.setObjectName("warning")
        form.addRow("", self.splits_note)
        form.addRow("Channel height", b.profile(cg, "height", scale=1e-3, decimals=3, suffix="mm", maximum=1000))
        form.addRow("Fill factor", b.profile(cg, "fill_factor", scale=0.01, decimals=1, suffix="%", maximum=99))
        form.addRow("Inner wall", b.profile(cg, "inner_wall", scale=1e-3, decimals=3, suffix="mm", maximum=1000))
        form.addRow("Outer wall", b.number(cg, "outer_wall", scale=1e-3, decimals=3, minimum=0.01, maximum=1000, step=0.1, suffix="mm"))
        self.helical = b.check(cg, "helical", "Helical channels")
        form.addRow("", self.helical)
        self.helix = b.profile(cg, "helix_angle", decimals=1, suffix="deg", maximum=89.9)
        form.addRow("Helix angle", self.helix)
        form.addRow("Smallest printable channel", b.number(cg, "min_channel_size", scale=1e-3, decimals=2, minimum=0, maximum=100,
                                                           step=0.1, suffix="mm"))
        form.addRow("Corner fillet", b.number(cg, "fillet_radius", scale=1e-3, decimals=2, minimum=0, maximum=10, step=0.05, suffix="mm",
                                              tooltip="Radius of the channel corners in the STEP model, made smaller where a channel is "
                                                      "too small for it. Not part of the thermal model"))
        self.split_length = b.number(cg, "split_length", scale=1e-3, decimals=1, minimum=0.5, maximum=200, step=0.5, suffix="mm",
                                     tooltip="Length over which the channels divide in the STEP model, rounded to whole steps of the thermal "
                                             "model: the new ribs grow from a blunt leading edge and the ribs that go on narrow as fast, so "
                                             "the channels keep their width. Not part of the thermal model")
        form.addRow("Split transition", self.split_length)
        self.step_button = QPushButton("Export 3D model (STEP)...")
        self.step_button.setToolTip("Chamber wall and coolant channels as solids for CAD (Fusion 360, CATIA, SolidWorks...)")
        self.step_button.clicked.connect(self.export_step)
        self.step_bodies = QComboBox()
        self.step_bodies.addItem("Inner wall, outer wall, ribs, channels", True)
        self.step_bodies.addItem("Jacket as one solid, channels", False)
        self.step_bodies.setToolTip("Parts of the STEP model. Ribs and channels are one part each, with a body per rib or channel")
        row = QHBoxLayout()
        row.addWidget(self.step_bodies, 1)
        row.addWidget(self.step_button)
        form.addRow("STEP model", row)
        left.addWidget(box)

        box = QGroupBox("Wall material")
        form = QFormLayout(box)
        form.addRow("Material", b.choice(lambda d: d.thermal, "material", [(k, k) for k in MATERIALS]))
        form.addRow("Firing time", b.number(lambda d: d.thermal, "firing_time", decimals=1, minimum=0.1, maximum=1e6, step=1, suffix="s",
                                            tooltip="Duration of one firing at steady state, for the creep rupture screening and the cyclic life"))
        form.addRow("Firings", b.number(lambda d: d.thermal, "firings", integer=True, minimum=1, maximum=1000000,
                                        tooltip="Number of firings over the life of the chamber, for the creep rupture screening and the cyclic life"))
        self.material_note = QLabel("")
        self.material_note.setWordWrap(True)
        form.addRow("", self.material_note)
        left.addWidget(box)
        left.addStretch(1)
        layout.addWidget(scroll, 2)

        right = QVBoxLayout()
        self.preview_note = QLabel("")
        self.preview_note.setWordWrap(True)
        right.addWidget(self.preview_note)
        self.preview = PlotCanvas(figsize=(7, 6))
        right.addWidget(self.preview, 1)
        layout.addLayout(right, 3)

        self.timer = QTimer(self, singleShot=True, interval=300)
        self.timer.timeout.connect(self.draw_preview)

    # ── coolant ──────────────────────────────────────────────────────────
    def _fluids_changed(self):
        fluids = [f.strip() for f in self.fluids.text().split(",") if f.strip()]
        try:
            fractions = [float(w) for w in self.fractions.text().split(",") if w.strip()]
        except ValueError:
            fractions = []
        c = self.window.design.coolant
        if fluids != c.fluids or (fractions and fractions != c.mass_fractions):
            c.fluids = fluids
            if len(fractions) == len(fluids):
                c.mass_fractions = fractions
            self.window.design_changed()

    def use_fuel(self):
        p = self.window.design.propellants
        default = props.default_coolant(p.fuel, p.fuel_concentration)
        if default is None:
            self.coolant_note.setText("CoolProp has no fluid for %s, enter the coolant by hand" % props.FUELS[p.fuel].name)
            return
        self.window.design.coolant.fluids, self.window.design.coolant.mass_fractions = default
        self.window.bindings.refresh()
        self.window.design_changed()

    # ── film ports ───────────────────────────────────────────────────────
    def _show_ports(self):
        self.ports.blockSignals(True)
        self.ports.setRowCount(0)
        for port in self.window.design.film.ports:
            r = self.ports.rowCount()
            self.ports.insertRow(r)
            for c, v in enumerate((port.x, port.fraction * 100, port.velocity, port.diameter * 1e3)):
                self.ports.setItem(r, c, QTableWidgetItem("%g" % v))
        self.ports.blockSignals(False)

    def _ports_changed(self, *_):
        ports = []
        for r in range(self.ports.rowCount()):
            try:
                x, f, v, dia = (float(self.ports.item(r, c).text()) for c in range(4))
            except (AttributeError, ValueError):
                continue
            ports.append(FilmPort(x=x, fraction=f / 100, velocity=v, diameter=dia / 1000))
        self.window.design.film.ports = ports
        self.window.design_changed()

    def _add_port(self):
        self.window.design.film.ports.append(FilmPort())
        self._show_ports()
        self.window.design_changed()

    def _remove_port(self):
        rows = sorted({i.row() for i in self.ports.selectedIndexes()}, reverse=True) or [self.ports.rowCount() - 1]
        for r in rows:
            if 0 <= r < len(self.window.design.film.ports):
                del self.window.design.film.ports[r]
        self._show_ports()
        self.window.design_changed()

    # ── channel splits ───────────────────────────────────────────────────
    def _show_splits(self):
        self.splits.blockSignals(True)
        self.splits.setRowCount(0)
        for x, n in self.window.design.channels.splits:
            r = self.splits.rowCount()
            self.splits.insertRow(r)
            self.splits.setItem(r, 0, QTableWidgetItem("%g" % x))
            self.splits.setItem(r, 1, QTableWidgetItem("%d" % n))
        self.splits.blockSignals(False)

    def _splits_changed(self, *_):
        splits = []
        for r in range(self.splits.rowCount()):
            try:
                x, n = float(self.splits.item(r, 0).text()), int(float(self.splits.item(r, 1).text()))
            except (AttributeError, ValueError):
                continue
            if n >= 1:
                splits.append((x, n))
        self.window.design.channels.splits = splits
        self.window.design_changed()

    def _add_split(self):
        ch = self.window.design.channels
        # by default the channels split in two downstream of the last change, or of the injector end
        x, n = ch.splits[-1] if ch.splits else (0.0, ch.n)
        ch.splits.append((x + 10.0, 2 * n))
        self._show_splits()
        self.window.design_changed()

    def _remove_split(self):
        rows = sorted({i.row() for i in self.splits.selectedIndexes()}, reverse=True) or [self.splits.rowCount() - 1]
        for r in rows:
            if 0 <= r < len(self.window.design.channels.splits):
                del self.window.design.channels.splits[r]
        self._show_splits()
        self.window.design_changed()

    # ── STEP export ──────────────────────────────────────────────────────
    def export_step(self):
        from .main_window import _sizing_inputs
        folder = QFileDialog.getExistingDirectory(self, "Folder for Cooling_Jacket.step")
        if not folder:
            return
        w = self.window
        if w.nozzle is None or _sizing_inputs(w.design) != _sizing_inputs(w.nozzle.design):
            # the model is built on the contour of the current inputs
            w.solve_nozzle(then=lambda: self._write_step(folder))
        else:
            self._write_step(folder)

    def _write_step(self, folder):
        w = self.window
        self.step_button.setEnabled(False)
        w.statusBar().showMessage("Writing the STEP model...")

        def finished(result):
            self.step_button.setEnabled(True)
            path, notes = result
            w.statusBar().showMessage("Written " + path, 8000)
            if notes:
                QMessageBox.information(self, "STEP model", "Written %s\n\n- %s" % (path, "\n- ".join(notes)))

        def failed(text):
            self.step_button.setEnabled(True)
            w.statusBar().showMessage("STEP export failed", 8000)
            QMessageBox.critical(self, "STEP export failed", text.strip().splitlines()[-1])

        run_in_thread(pipeline.write_step, w.nozzle, folder, copy.deepcopy(w.design), self.step_bodies.currentData(),
                      on_finished=finished, on_failed=failed)

    # ── updates ──────────────────────────────────────────────────────────
    def refresh(self):
        d = self.window.design
        self.helix.setEnabled(d.channels.helical)
        self.split_length.setEnabled(bool(d.channels.changes()))
        self.splits_note.setText("\n".join("The %d channels do not split evenly into %d at x = %g mm" % (min(a, b), max(a, b), x)
                                           for x, a, b in d.channels.uneven_changes()))
        p = d.propellants
        default = props.default_coolant(p.fuel, p.fuel_concentration)
        if default is not None and (default[0] != d.coolant.fluids or not np.allclose(default[1], d.coolant.mass_fractions[:len(default[1])])
                                    or len(default[1]) != len(d.coolant.mass_fractions)):
            self.coolant_note.setText("The coolant is not the fuel of the Engine tab (%s). Press 'Use fuel' if it should be."
                                      % ", ".join("%s %g%%" % (f, w * 100) for f, w in zip(*default)))
        else:
            self.coolant_note.setText("")
        self.film_note.setText("%.1f %% of the fuel feed, set on the Engine tab" % (d.film.injector_fraction * 100))
        m = MATERIALS[d.thermal.material]
        notes = []
        if m.sig_y is None:
            notes.append("No yield strength in the library: the wall stress analysis is skipped")
        if m.creep is None:
            notes.append("No creep rupture data in the library: creep is not screened")
        else:
            notes.append("Creep data: %s%s" % (m.creep.source, ", stress x %g for printed parts" % m.creep.factor if m.creep.factor != 1 else ""))
        if m.norton is None or m.fatigue is None:
            notes.append("No creep rate or fatigue data in the library: ratcheting and cyclic life are not evaluated")
        else:
            notes.append("Cyclic life data: %s; %s" % (m.norton.source, m.fatigue.source))
        self.material_note.setText("\n".join(notes))
        self.timer.start()

    def draw_preview(self):
        nd = self.window.nozzle
        fig = self.preview.clear()
        if nd is None:
            self.preview_note.setText("Solve the nozzle (Chamber & Nozzle tab) to see the channels on the contour.")
            self.preview.draw()
            return
        self.preview_note.setText("Channels at the throat, and channel size along the chamber.")
        ch = self.window.design.channels
        x = nd.solution.wall_x / 1000
        r = nd.solution.wall_y / 1000
        n = np.maximum(ch.count(x), 1)
        beta = np.radians(ch.helix_angle(x)) if ch.helical else np.zeros_like(x)
        psi = ch.fill_factor(x)
        h_c, t_i = ch.height(x), ch.inner_wall(x)
        psi_c = 2 * np.pi * psi / n * np.cos(beta)
        width = psi_c * (r + t_i)                       # at the bottom of the channel, perpendicular to it

        # cross section at the throat: three channels and their ribs
        i = int(np.argmin(r))
        ax = fig.add_subplot(2, 1, 1)
        r_c, r_ci, r_co = r[i] * 1e3, (r[i] + t_i[i]) * 1e3, (r[i] + t_i[i] + h_c[i]) * 1e3
        r_o = r_co + ch.outer_wall * 1e3
        pitch = 360.0 / n[i] * np.cos(beta[i])
        span = 3 * pitch
        ax.add_patch(Wedge((0, 0), r_o, 90 - span / 2, 90 + span / 2, width=r_o - r_c, facecolor="#c98a5b", edgecolor="#5a3a20", lw=0.8))
        for k in (-1, 0, 1):
            c = 90 + k * pitch
            ax.add_patch(Wedge((0, 0), r_co, c - np.degrees(psi_c[i]) / 2, c + np.degrees(psi_c[i]) / 2, width=r_co - r_ci,
                               facecolor="#7ec8e3", edgecolor="#2a5080", lw=0.8))
        ax.set_xlim(-r_o * np.sin(np.radians(span / 2)) * 1.1, r_o * np.sin(np.radians(span / 2)) * 1.1)
        ax.set_ylim(r_c * np.cos(np.radians(span / 2)) * 0.97, r_o * 1.02)
        ax.set_aspect("equal")
        ax.set_title("Throat, x = %.1f mm, %d channels%s" % (round(x[i] * 1e3, 1) + 0.0, n[i], ", perpendicular to the channels" if ch.helical else ""),
                     fontsize=9)
        ax.set_xlabel("mm")

        ax = fig.add_subplot(2, 1, 2)
        ax.plot(x * 1e3, width * 1e3, label="Channel width (bottom)")
        ax.plot(x * 1e3, h_c * 1e3, label="Channel height")
        ax.plot(x * 1e3, t_i * 1e3, label="Inner wall")
        ax.axhline(ch.min_channel_size * 1e3, color="r", lw=0.8, ls="--", label="Smallest printable")
        for x_s, a, b in ch.changes():
            # where the channels split or merge, with the number of channels downstream
            ax.axvline(x_s, color="0.5", lw=0.8, ls=":")
            ax.annotate("%d → %d" % (a, b), (x_s, 0), xycoords=("data", "axes fraction"), xytext=(2, 2), textcoords="offset points",
                        ha="left", va="bottom", fontsize=7, color="0.4")
        ax2 = ax.twinx()
        ax2.plot(x * 1e3, r * 1e3, color="0.6", lw=0.8)
        ax2.set_ylabel("Contour radius [mm]", color="0.5")
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("[mm]")
        ax.set_ylim(bottom=0)
        ax.legend(fontsize=7, loc="upper right")
        self.preview.draw()
