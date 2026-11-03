import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _wait(app, condition, timeout=60):
    import time
    t0 = time.time()
    while not condition() and time.time() - t0 < timeout:
        app.processEvents()
        time.sleep(0.02)
    return condition()


def test_window_solves_the_nozzle(app, tmp_path):
    from thrust_chamber_designer.gui import themes
    from thrust_chamber_designer.gui.main_window import MainWindow

    window = MainWindow(app)
    for name in themes.THEMES:
        themes.apply(app, name)
    window.design.operating.thrust = 1000.0
    window.bindings.refresh()
    window.solve_nozzle()
    assert _wait(app, lambda: window.nozzle is not None)
    assert window.nozzle.solution.thrust == pytest.approx(1000.0, rel=1e-6)
    assert window.chamber_tab.performance.rowCount() > 10

    # film changes the split of the mass flow at once, not the nozzle
    throat = window.nozzle.solution.throat_radius
    status = window.chamber_tab.status.text()
    window.design.film.injector_fraction = 0.35
    window.design_changed()
    b = window.nozzle.budget
    assert b.film == pytest.approx(0.35 * b.fuel_feed)
    assert b.of_feed == pytest.approx(window.design.operating.of_ratio * 0.65)
    assert window.nozzle.solution.throat_radius == throat
    assert window.chamber_tab.status.text() == status
    flows = {window.chamber_tab.flows.item(r, 0).text(): float(window.chamber_tab.flows.item(r, 1).text())
             for r in range(window.chamber_tab.flows.rowCount())}
    assert flows["Film Flow"] == pytest.approx(b.film, rel=1e-4)

    # a change of an input marks the solution as outdated
    window.chamber_tab.lstar.setValue(1.2)
    assert window.design.chamber.lstar == pytest.approx(1.2)
    assert "changed" in window.chamber_tab.status.text()

    path = tmp_path / "engine.json"
    window.path = str(path)
    assert window.save()
    from thrust_chamber_designer.core.design import Design
    assert Design.load(path).chamber.lstar == pytest.approx(1.2)
    window.modified = False
    window.close()


def test_cooling_tab_exports_step(app, tmp_path, monkeypatch):
    from thrust_chamber_designer.gui import tab_cooling
    from thrust_chamber_designer.gui.main_window import MainWindow

    window = MainWindow(app)
    window.design.channels.n = 8
    window.design.thermal.step_size = 0.005
    monkeypatch.setattr(tab_cooling.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    # without a nozzle, the export solves it first
    window.cooling_tab.export_step()
    assert _wait(app, lambda: window.nozzle is not None and window.cooling_tab.step_button.isEnabled(), timeout=120)
    assert (tmp_path / "Cooling_Jacket.step").stat().st_size > 0
    window.modified = False
    window.close()


def test_cooling_tab_channel_splits(app):
    from thrust_chamber_designer.gui.main_window import MainWindow

    window = MainWindow(app)
    tab = window.cooling_tab
    window.design.channels.n = 20
    tab._add_split()
    assert window.design.channels.splits == [(10.0, 40)]
    tab.splits.item(0, 0).setText("-12")
    tab.splits.item(0, 1).setText("10")
    assert window.design.channels.splits == [(-12.0, 10)]
    assert tab.split_length.isEnabled() and tab.splits_note.text() == ""
    tab.splits.item(0, 1).setText("15")
    assert "do not split evenly" in tab.splits_note.text()
    tab.draw_preview()
    tab._remove_split()
    assert window.design.channels.splits == [] and not tab.split_length.isEnabled()
    window.modified = False
    window.close()


def test_throttle_tab_inputs(app):
    from thrust_chamber_designer.gui.main_window import MainWindow
    from thrust_chamber_designer.gui.tab_throttle import parse_schedule

    assert parse_schedule("100:4.4, 50:3.2") == [(1.0, 4.4), (0.5, 3.2)]
    window = MainWindow(app)
    tab = window.throttle_tab
    window.design.film.injector_fraction = 0.35
    window.refresh()
    assert tab.points_note.text().startswith("144 points")

    tab.levels.setText("100, 50")
    tab.levels.editingFinished.emit()
    assert window.design.throttle.pc_fractions == [1.0, 0.5]
    assert tab.points_note.text().startswith("32 points")

    tab.of_values.setText("3.2, 2.8")
    tab.of_values.editingFinished.emit()
    assert window.design.throttle.of_ratios == [3.2, 2.8]

    tab.own.setText("100:4.4, 50:3.0")
    tab.own.editingFinished.emit()
    assert window.design.throttle.schedule == [(1.0, 4.4), (0.5, 3.0)]

    # what can not be read leaves the design as it was
    tab.levels.setText("100, half")
    tab.levels.editingFinished.emit()
    assert window.design.throttle.pc_fractions == [1.0, 0.5]
    assert tab.levels.text() == "100, 50"
    tab.own.setText("100")
    tab.own.editingFinished.emit()
    assert window.design.throttle.schedule == [(1.0, 4.4), (0.5, 3.0)]

    window.design.thermal.boiling = False
    window.refresh()
    assert not tab.run_button.isEnabled()
    window.modified = False
    window.close()


def test_throttle_tab_shows_results_and_marks_outdated_ones(app):
    from thrust_chamber_designer.gui.main_window import MainWindow
    from thrust_chamber_designer.thermal.throttle import ThrottleResult

    def point(frac, of, film, **kwargs):
        return ThrottleResult(frac, of, film, Pc=34e5 * frac, of_feed=0.65 * of, p_inlet=45e5 * frac, thrust=600 * frac, T_wall=600.0,
                              chf_ratio=0.9, subcooling_min=50.0, Y=0.5, life_startup=100.0, v_throat=5.0, p_coolant_min=45e5 * frac,
                              p_exit=1e5, **kwargs)

    window = MainWindow(app)
    window.design.film.injector_fraction = 0.35
    window.design.throttle.pc_fractions = [1.0, 0.5]
    window.design.throttle.of_ratios = [4.4, 3.2]
    window.refresh()
    tab = window.throttle_tab
    import copy
    tab.started_run(copy.deepcopy(window.design), "folder")
    tab.add_point("map", 1, 2, point(1.0, 4.4, True))
    assert tab.outdated_map
    tab._tick()
    assert not tab.outdated_map
    assert "Map 1 / 2" in tab.log.toPlainText()

    results = [point(f, of, film) for film in (True, False) for f in (1.0, 0.5) for of in (4.4, 3.2)]
    schedules = {"film": [point(1.0, 4.4, True), point(0.5, 3.2, True, n_failed=1)], "no_film": [point(1.0, 3.2, False)]}
    tab.finished_run("Finished")
    tab.show_results(results, schedules)
    assert tab.view.count() == 2
    assert tab.table.rowCount() == 2
    assert "Outside the limits" in tab.table.item(1, tab.table.columnCount() - 1).text()
    tab.view.setCurrentIndex(tab.view.findData("no_film"))
    assert tab.table.rowCount() == 1
    assert not tab._film()
    assert tab.state.text() == ""

    window.design.operating.of_ratio = 4.0
    window.design_changed()
    assert "changed" in tab.state.text()

    window.load_design(type(window.design)(), None)
    assert tab.table.rowCount() == 0 and tab.map_results == []
    window.modified = False
    window.close()


@pytest.mark.slow
def test_throttle_analysis_runs_and_cancels_through_the_window(app, tmp_path, monkeypatch):
    import multiprocessing

    from thrust_chamber_designer.core.design import Design
    from thrust_chamber_designer.gui import tab_throttle
    from thrust_chamber_designer.gui.main_window import MainWindow

    design = Design.load(os.path.join(os.path.dirname(__file__), "..", "examples", "600N_N2O_ethanol80.json"))
    design.film.injector_fraction = 0.0
    design.thermal.step_size = design.throttle.map_step_size = 0.01
    design.thermal.cell_size_factor = design.throttle.map_cell_size_factor = 0.4
    design.throttle.pc_fractions = [1.0, 0.6]
    design.throttle.of_ratios = [design.operating.of_ratio]
    # without film no point of the map keeps the limits, so no schedule comes out of it and only this one is solved
    design.throttle.schedule = [(1.0, design.operating.of_ratio)]

    window = MainWindow(app)
    window.load_design(design, None)
    window.thermal_tab.folder.setText(str(tmp_path))
    window.throttle_tab.jobs.setValue(2)

    window.run_throttle()
    assert not window.throttle_tab.run_button.isEnabled()
    window.cancel_throttle()
    assert window.throttle_tab.run_button.isEnabled()
    assert _wait(app, lambda: multiprocessing.active_children() == [], timeout=20)

    window.run_throttle()
    assert _wait(app, lambda: not window.throttle.running and window.throttle_tab.schedules, timeout=280)
    tab = window.throttle_tab
    assert len(tab.map_results) == 2
    tab.view.setCurrentIndex(tab.view.findData("design_file_film"))
    assert tab.table.rowCount() == 1
    assert (tmp_path / "throttle" / "throttle_map.csv").exists()
    assert (tmp_path / "throttle" / "throttle_map_film.png").exists()

    # the folder of the run shows the same results again
    monkeypatch.setattr(tab_throttle.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path / "throttle"))
    tab.clear_results()
    tab.open_results()
    assert len(tab.map_results) == 2 and list(tab.schedules) == ["design_file_film"]
    window.modified = False
    window.close()
