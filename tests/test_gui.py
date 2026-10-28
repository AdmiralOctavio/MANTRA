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
