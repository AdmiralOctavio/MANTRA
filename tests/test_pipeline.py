import re

import numpy as np
import pytest

from thrust_chamber_designer import pipeline
from thrust_chamber_designer.core.design import Design, FilmPort, Profile
from thrust_chamber_designer.core.mass_budget import mass_budget
from thrust_chamber_designer.thermal.cad_export import fillet_limit
from thrust_chamber_designer.thermal.geometry import GROWTH, ChamberGeometry


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


def test_graded_sections_are_finer_at_the_throat():
    x = np.linspace(-0.05, 0.03, 400)
    y = 0.01 + 0.5 * (x - 0.00123) ** 2
    graded = ChamberGeometry.from_contour(x, y, 0.0025, throat_step=0.0005, throat_zone=0.006)
    dx = np.diff(graded.x)
    # a section at the throat, the fine step within the zone around it, growing smoothly up to the coarse step
    assert graded.y.min() == pytest.approx(y.min(), rel=1e-12)
    near = np.abs(graded.x[:-1] - 0.00123) < 0.006
    assert np.allclose(dx[near], 0.0005)
    assert dx.max() == pytest.approx(0.0025)
    ratio = dx[1:] / dx[:-1]
    assert np.all((ratio < GROWTH + 1e-9) & (ratio > 1 / GROWTH - 1e-9))
    assert graded.x[0] >= x[0] - 1e-12 and graded.x[-1] < x[-1]
    assert len(graded.x) < len(ChamberGeometry.from_contour(x, y, 0.0005).x) / 2
    # a throat step that is not smaller than the step is the uniform grid
    same = ChamberGeometry.from_contour(x, y, 0.0025, anchor_throat=True, throat_step=0.003, throat_zone=0.006)
    assert np.array_equal(same.x, ChamberGeometry.from_contour(x, y, 0.0025, anchor_throat=True).x)


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


@pytest.mark.parametrize("helical, fillet, separate", [(False, 0.0, True), (True, 0.2e-3, True), (False, 5e-3, True),
                                                       (True, 0.2e-3, False)])
def test_step_model_parts(tmp_path, helical, fillet, separate):
    import gmsh
    design = Design(name="Test engine")
    design.channels.n = 8
    design.channels.helical = helical
    design.channels.fillet_radius = fillet
    design.thermal.step_size = 0.005
    nd = pipeline.design_nozzle(design)
    path, notes = pipeline.write_step(nd, str(tmp_path), separate=separate)
    # a fillet too large for the channels is made smaller, and said so
    assert bool(notes) == (fillet > 1e-3)

    # volumes of the parts [mm^3]: the rings between the radii, and the channels with the corners taken by the fillets
    _, cg = pipeline.cooling_geometry(nd, full_length=True)
    x, r_c, r_out = cg.geom[:,0], cg.geom[:,1], cg.r_o + cg.t_w_o
    ring = lambda a, b: np.trapezoid(np.pi * (b**2 - a**2), x) * 1e9
    f = np.minimum(fillet, 0.9 * fillet_limit(cg))
    channels = np.trapezoid((cg.A_c - cg.n_channels * 4 * f**2 * (1 - np.pi / 4)) / np.cos(cg.beta), x) * 1e9
    if separate:
        expected = {"Inner wall": (1, ring(r_c, cg.r_i)), "Outer wall": (1, ring(cg.r_o, r_out)),
                    "Ribs": (8, ring(cg.r_i, cg.r_o) - channels), "Coolant channels": (8, channels)}
    else:
        expected = {"Jacket": (1, ring(r_c, r_out) - channels), "Coolant channels": (8, channels)}

    text = open(path).read()
    assert re.findall(r"PRODUCT\('([^']*)'", text) == ["Test engine"] + list(expected)
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 0)
        gmsh.option.setNumber('Geometry.OCCImportLabels', 1)
        gmsh.model.occ.importShapes(path)
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        # nothing but the faces of the solids in the file
        assert set(gmsh.model.getEntities(2)) == set(gmsh.model.getBoundary(volumes, combined=False, oriented=False))
        for part, (count, volume) in expected.items():
            bodies = [v for v in volumes if part in gmsh.model.getEntityName(*v)]
            assert len(bodies) == count
            assert sum(gmsh.model.occ.getMass(*v) for v in bodies) == pytest.approx(volume, rel=0.02)
        assert len(volumes) == sum(count for count, _ in expected.values())
        xmin, _, _, xmax, _, _ = gmsh.model.getBoundingBox(-1, -1)
        assert xmin == pytest.approx(nd.solution.wall_x[0], abs=0.1)
    finally:
        gmsh.finalize()


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
