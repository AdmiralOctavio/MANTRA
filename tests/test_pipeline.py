import numpy as np
import pytest

from thrust_chamber_designer import pipeline
from thrust_chamber_designer.core.design import Design, FilmPort, Profile
from thrust_chamber_designer.core.mass_budget import mass_budget
from thrust_chamber_designer.thermal.geometry import ChamberGeometry


def test_mass_budget_film_on_top_of_core():
    design = Design()
    design.film.injector_fraction = 0.25
    design.film.ports = [FilmPort(x=-20, fraction=0.1)]
    b = mass_budget(1.0, 4.0, design.film)

    assert b.oxidiser + b.fuel_feed == pytest.approx(1.0)
    assert b.oxidiser / b.fuel_core == pytest.approx(4.0)              # combustion at the core O/F
    assert b.film == pytest.approx(0.35 * b.fuel_feed)
    assert b.fuel_core + b.film == pytest.approx(b.fuel_feed)
    assert b.of_feed == pytest.approx(4.0 * 0.65)
    assert b.coolant == pytest.approx(b.fuel_feed)


def test_mass_budget_without_film_is_plain_split():
    b = mass_budget(0.6, 5.0, Design().film)
    assert b.fuel_feed == pytest.approx(0.1)
    assert b.of_feed == pytest.approx(5.0)


def test_design_file_round_trip(tmp_path):
    design = Design(name="test")
    design.channels.height = Profile(points=[(-50, 1.5e-3), (0, 0.8e-3), (30, 1.2e-3)])
    design.film.ports = [FilmPort(x=-10, fraction=0.05, velocity=12, diameter=0.3e-3)]
    design.thermal.run_time = 2.0
    path = tmp_path / "design.json"
    design.save(path)
    assert Design.load(path) == design


def test_profile_interpolates_in_mm_and_holds_ends():
    p = Profile(points=[(0, 1.0), (10, 2.0)])
    np.testing.assert_allclose(p(np.array([-0.005, 0.0, 0.005, 0.02])), [1.0, 1.0, 1.5, 2.0])
    assert Profile(3.0).as_input() == 3.0


def test_resampling_puts_a_section_at_the_throat():
    x = np.linspace(-0.05, 0.03, 400)
    y = 0.01 + 0.5 * (x - 0.00123) ** 2
    plain = ChamberGeometry.from_contour(x, y, 0.0025)
    anchored = ChamberGeometry.from_contour(x, y, 0.0025, anchor_throat=True)
    assert anchored.y.min() == pytest.approx(y.min(), rel=1e-12)
    assert plain.y.min() > y.min()
    assert np.allclose(np.diff(anchored.x), 0.0025)


def test_nozzle_design_is_consistent():
    nd = pipeline.design_nozzle(Design())
    s, op = nd.solution, nd.design.operating
    assert s.converged
    assert s.thrust == pytest.approx(op.thrust, rel=1e-6)
    assert s.P_exit == pytest.approx(op.ambient_pressure, rel=1e-6)
    # CEA was run at the expansion ratio of the contour
    eps_cea, eps_contour = nd.expansion_history[-1]
    assert eps_cea == pytest.approx(eps_contour, rel=1e-3)
    # the throat is sized for all mass through it with the delivered c* of the core
    A_t = np.pi * (s.throat_radius / 1000) ** 2
    assert s.mdot * nd.chem.cstar_eq * op.eta_c_star / A_t == pytest.approx(op.chamber_pressure, rel=1e-9)


@pytest.mark.slow
def test_thermal_run_on_the_nozzle(tmp_path):
    design = Design()
    design.film.injector_fraction = 0.35
    design.thermal.step_size = 0.008
    design.thermal.cell_size_factor = 0.3
    nd = pipeline.design_nozzle(design)
    setup = pipeline.build_thermal(nd, str(tmp_path))
    calls = []
    pipeline.run_thermal(setup, progress=lambda done, total, idx: calls.append((done, total, idx)))

    n = len(setup.geometry)
    assert [c[0] for c in calls] == list(range(1, n + 1))
    assert (tmp_path / "sim_data.csv").exists()
    assert np.all(np.isfinite(setup.output.T_wall_i))
    # the coolant enters at the nozzle and heats up on the way to the injector
    assert setup.output.T_c[0] > design.coolant.inlet_temperature
