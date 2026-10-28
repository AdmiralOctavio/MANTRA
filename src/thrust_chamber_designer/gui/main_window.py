import copy
import os
from dataclasses import asdict

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QTabWidget

from .. import __version__
from ..core.design import Design
from . import themes
from .tab_chamber import ChamberTab
from .tab_cooling import CoolingTab
from .tab_engine import EngineTab
from .tab_results import ResultsTab
from .tab_thermal import ThermalTab
from .widgets import Bindings
from .worker import ThermalRun, results_geometry, run_in_thread
from .. import pipeline
from ..core.mass_budget import mass_budget

FILTER = "Thrust chamber designs (*.json)"


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = QSettings("Thrust Chamber Designer", "Thrust Chamber Designer")
        self.design = Design()
        self.path = None
        self.modified = False
        self.nozzle = None                 # pipeline.NozzleDesign of the current inputs, None until solved
        self.solving = False

        self.bindings = Bindings(lambda: self.design, self.design_changed)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.engine_tab = EngineTab(self)
        self.chamber_tab = ChamberTab(self)
        self.cooling_tab = CoolingTab(self)
        self.thermal_tab = ThermalTab(self)
        self.results_tab = ResultsTab(self)
        self.tabs.addTab(self.engine_tab, "Engine")
        self.tabs.addTab(self.chamber_tab, "Chamber && Nozzle")
        self.tabs.addTab(self.cooling_tab, "Cooling")
        self.tabs.addTab(self.thermal_tab, "Thermal")
        self.tabs.addTab(self.results_tab, "Results")
        self.setCentralWidget(self.tabs)

        self.thermal = ThermalRun(self)
        self.thermal.log.connect(self.thermal_tab.add_log)
        self.thermal.section.connect(self.thermal_tab.add_section)
        self.thermal.done.connect(self._thermal_done)
        self.thermal.failed.connect(self._thermal_failed)

        self._menus()
        self.resize(1400, 900)
        self.load_design(Design(), None)
        self.statusBar().showMessage("Ready")

    # ── menus ────────────────────────────────────────────────────────────
    def _menus(self):
        def action(menu, text, slot, shortcut=None):
            a = QAction(text, self)
            if shortcut is not None:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            menu.addAction(a)
            return a

        m = self.menuBar().addMenu("&File")
        action(m, "&New", self.new, QKeySequence.StandardKey.New)
        action(m, "&Open...", self.open, QKeySequence.StandardKey.Open)
        action(m, "&Save", self.save, QKeySequence.StandardKey.Save)
        action(m, "Save &As...", self.save_as, QKeySequence.StandardKey.SaveAs)
        m.addSeparator()
        action(m, "Open &results folder...", self.open_results)
        m.addSeparator()
        action(m, "&Quit", self.close, QKeySequence.StandardKey.Quit)

        m = self.menuBar().addMenu("&Run")
        action(m, "Solve &nozzle", self.solve_nozzle, "F5")
        action(m, "Run &thermal simulation", self.run_thermal, "F6")
        action(m, "&Cancel thermal simulation", self.cancel_thermal, "Esc")

        m = self.menuBar().addMenu("&View")
        group = QActionGroup(self)
        current = self.settings.value("theme", themes.DEFAULT)
        for name in themes.THEMES:
            a = action(m, name, lambda checked=False, name=name: self.set_theme(name))
            a.setCheckable(True)
            a.setChecked(name == current)
            group.addAction(a)

        m = self.menuBar().addMenu("&Help")
        action(m, "&About", self.about)

    def set_theme(self, name):
        themes.apply(self.app, name, self)
        self.settings.setValue("theme", name)
        self.redraw_plots()

    def redraw_plots(self):
        # the plots are made again in the look of the new theme
        self.engine_tab.update_chart()
        self.chamber_tab.draw()
        self.cooling_tab.draw_preview()
        self.thermal_tab._draw_live()
        self.results_tab.reload()

    def about(self):
        QMessageBox.about(self, "Thrust Chamber Designer",
                          "<b>Thrust Chamber Designer %s</b><br><br>"
                          "Nozzle contour with the Method of Characteristics (after NASA TM X-1502) and regenerative cooling "
                          "with PyRocket (2D finite volume sections along the chamber).<br><br>"
                          "Based on the Method-Of-Characteristics-Nozzle-Solver (Flavio Cicero) and PyRocket (Jonathan Neeser).<br>"
                          "GNU General Public License v3." % __version__)

    # ── design state ─────────────────────────────────────────────────────
    def design_changed(self):
        if self.bindings.loading:
            return
        self.modified = True
        if self.nozzle is not None and _sizing_inputs(self.design) == _sizing_inputs(self.nozzle.design):
            # the contour does not depend on film, coolant, channels or thermal settings: only the split of the mass flow changes
            self.update_budget()
        else:
            self.nozzle_outdated()
        self._title()
        self.refresh()

    def nozzle_outdated(self):
        self.chamber_tab.mark_outdated()

    def update_budget(self):
        nd = self.nozzle
        nd.design.film = copy.deepcopy(self.design.film)
        nd.design.coolant = copy.deepcopy(self.design.coolant)
        try:
            nd.budget = mass_budget(nd.solution.mdot, nd.design.operating.of_ratio, nd.design.film, nd.design.coolant.fuel_fraction)
        except ValueError as e:
            self.chamber_tab.status.setText(str(e))
            return
        self.chamber_tab.show_tables(nd)

    def refresh(self):
        for tab in (self.engine_tab, self.chamber_tab, self.cooling_tab, self.thermal_tab):
            tab.refresh()

    def _title(self):
        name = os.path.basename(self.path) if self.path else "untitled"
        self.setWindowTitle("%s%s - Thrust Chamber Designer" % (name, " *" if self.modified else ""))

    def load_design(self, design, path):
        self.design = design
        self.path = path
        self.modified = False
        self.nozzle = None
        self.bindings.refresh()
        self.thermal_tab.folder.setText("")
        self.chamber_tab.status.setText("Not solved yet")
        self.refresh()
        self._title()

    def maybe_save(self):
        if not self.modified:
            return True
        answer = QMessageBox.question(self, "Unsaved changes", "Save the changes to the design?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save()
        return answer == QMessageBox.StandardButton.Discard

    def new(self):
        if self.maybe_save():
            self.load_design(Design(), None)

    def open(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open design", self.settings.value("folder", os.path.expanduser("~")), FILTER)
        if path:
            self.open_path(path)

    def open_path(self, path):
        try:
            design = Design.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Could not open the design", str(e))
            return
        self.settings.setValue("folder", os.path.dirname(path))
        self.load_design(design, path)
        self.statusBar().showMessage("Opened " + path, 5000)

    def save(self):
        if self.path is None:
            return self.save_as()
        self.design.save(self.path)
        self.modified = False
        self._title()
        self.statusBar().showMessage("Saved " + self.path, 5000)
        return True

    def save_as(self):
        start = os.path.join(self.settings.value("folder", os.path.expanduser("~")), (self.design.name or "design") + ".json")
        path, _ = QFileDialog.getSaveFileName(self, "Save design", start, FILTER)
        if not path:
            return False
        if not path.endswith(".json"):
            path += ".json"
        self.path = path
        self.settings.setValue("folder", os.path.dirname(path))
        return self.save()

    def closeEvent(self, event):
        if self.thermal.running:
            if QMessageBox.question(self, "Thermal simulation running", "Stop the thermal simulation and quit?") != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.thermal.cancel()
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()

    # ── nozzle ───────────────────────────────────────────────────────────
    def solve_nozzle(self, then=None):
        if self.solving:
            return
        self.solving = True
        self.chamber_tab.solve_button.setEnabled(False)
        self.chamber_tab.status.setText("Solving...")
        self.statusBar().showMessage("Solving the nozzle...")
        design = copy.deepcopy(self.design)

        def finished(nd):
            self.solving = False
            self.chamber_tab.solve_button.setEnabled(True)
            self.nozzle = nd
            self.chamber_tab.show_solution(nd)
            self.cooling_tab.draw_preview()
            self.statusBar().showMessage("Nozzle solved: throat %.2f mm, mass flow %.4f kg/s" % (2 * nd.solution.throat_radius, nd.solution.mdot), 8000)
            if callable(then):
                then()

        def failed(text):
            self.solving = False
            self.chamber_tab.solve_button.setEnabled(True)
            self.chamber_tab.status.setText("The nozzle could not be solved:\n" + text.strip().splitlines()[-1])
            self.statusBar().showMessage("Nozzle failed", 8000)
            QMessageBox.warning(self, "Nozzle failed", text.strip().splitlines()[-1])

        run_in_thread(pipeline.design_nozzle, design, on_finished=finished, on_failed=failed)

    # ── thermal ──────────────────────────────────────────────────────────
    def run_thermal(self):
        if self.thermal.running:
            return
        folder = self.thermal_tab.default_folder()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "Results folder", "Can not create %s: %s" % (folder, e))
            return
        self.tabs.setCurrentWidget(self.thermal_tab)
        self.thermal_tab.started_run(folder)
        self.thermal_design = copy.deepcopy(self.design)
        self.thermal.start(self.thermal_design, folder, themes.plot_theme())
        self.statusBar().showMessage("Thermal simulation running...")
        if self.nozzle is None:
            # the run solves the nozzle itself, this shows it in the other tabs as well
            self.solve_nozzle()

    def cancel_thermal(self):
        if self.thermal.running:
            self.thermal.cancel()
            self.thermal_tab.finished_run("Cancelled")
            self.statusBar().showMessage("Thermal simulation cancelled", 5000)

    def _thermal_done(self, folder, geometry, warnings):
        self.thermal_tab.finished_run("Finished")
        self.results_tab.load(folder, geometry, warnings, self.thermal_design)
        self.tabs.setCurrentWidget(self.results_tab)
        self.statusBar().showMessage("Thermal simulation finished, results in " + folder, 10000)

    def _thermal_failed(self, text):
        self.thermal_tab.finished_run("Failed")
        self.thermal_tab.add_log(text)
        self.statusBar().showMessage("Thermal simulation failed", 10000)
        QMessageBox.warning(self, "Thermal simulation failed", text.strip().splitlines()[-1] + "\n\nThe log on the Thermal tab has the details.")

    def open_results(self):
        folder = QFileDialog.getExistingDirectory(self, "Results folder of a thermal run (with design.json and sim_data.csv)",
                                                  self.settings.value("folder", os.path.expanduser("~")))
        if not folder:
            return
        if not (os.path.exists(os.path.join(folder, "design.json")) and os.path.exists(os.path.join(folder, "sim_data.csv"))):
            QMessageBox.warning(self, "Not a results folder", "The folder needs design.json and sim_data.csv of a thermal run.")
            return
        design = Design.load(os.path.join(folder, "design.json"))
        self.statusBar().showMessage("Loading results...")

        def finished(result):
            nd, geometry = result
            self.results_tab.load(folder, geometry, nd.warnings, design)
            self.tabs.setCurrentWidget(self.results_tab)
            self.statusBar().showMessage("Results of " + folder, 8000)

        run_in_thread(results_geometry, design, on_finished=finished,
                      on_failed=lambda text: QMessageBox.warning(self, "Could not load the results", text.strip().splitlines()[-1]))


def _sizing_inputs(design):
    # inputs that change the nozzle: propellants, operating point, chamber and nozzle settings. Film and coolant only change the split
    # of the mass flow through the throat (core.mass_budget), the cooling channels and the thermal settings nothing of the nozzle
    return asdict(design.propellants), asdict(design.operating), asdict(design.chamber), asdict(design.nozzle)
