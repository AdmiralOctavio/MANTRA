import copy
import dataclasses
import os

import numpy as np
import pytest

from thrust_chamber_designer import pipeline
from thrust_chamber_designer.core.design import Design, FilmPort, ThrottleSettings
from thrust_chamber_designer.thermal import throttle
from thrust_chamber_designer.thermal.throttle import ThrottleResult

EXAMPLE = os.path.join(os.path.dirname(__file__), '..', 'examples', '600N_N2O_ethanol80.json')


@pytest.fixture(scope='module')
def nozzle():
    return pipeline.design_nozzle(Design.load(EXAMPLE))


def result(frac, of, film=True, **kwargs):
    return ThrottleResult(frac, of, film, subcooling_min=kwargs.pop('subcooling_min', 50.0), **kwargs)


def test_off_design_at_the_design_point_changes_nothing(nozzle):
    d = nozzle.design
    point = throttle.off_design(nozzle, d.operating.chamber_pressure, d.operating.of_ratio)
    assert point.budget.total == pytest.approx(nozzle.budget.total)
    assert point.budget.fuel_feed == pytest.approx(nozzle.budget.fuel_feed)
    assert point.design.coolant.inlet_pressure == pytest.approx(d.coolant.inlet_pressure)
    assert point.design.film.injection_velocity == pytest.approx(d.film.injection_velocity)


def test_off_design_keeps_the_contour_and_the_input(nozzle):
    before = copy.deepcopy(nozzle.design)
    point = throttle.off_design(nozzle, 17e5, 3.2)
    assert point.solution is nozzle.solution
    assert nozzle.design == before
    assert point.design.operating.chamber_pressure == 17e5
    assert point.design.operating.of_ratio == 3.2


def test_off_design_flow_follows_pc_over_c_star(nozzle):
    Pc0 = nozzle.design.operating.chamber_pressure
    point = throttle.off_design(nozzle, 0.5 * Pc0, 2.0)
    # the throat passes Pc A_t / c*, with the same throat and c* efficiency as the design point
    assert point.budget.total * point.chem.cstar_eq / (0.5 * Pc0) == pytest.approx(nozzle.budget.total * nozzle.chem.cstar_eq / Pc0)
    assert point.budget.oxidiser / point.budget.fuel_core == pytest.approx(2.0)


def test_going_fuel_rich_moves_flow_into_the_channels(nozzle):
    Pc = 0.5 * nozzle.design.operating.chamber_pressure
    lean, rich = throttle.off_design(nozzle, Pc, 4.4), throttle.off_design(nozzle, Pc, 2.8)
    assert rich.budget.coolant > lean.budget.coolant
    assert rich.budget.oxidiser < lean.budget.oxidiser
    assert rich.design.coolant.inlet_pressure > lean.design.coolant.inlet_pressure


def test_jacket_pressure_falls_with_the_square_of_the_feed(nozzle):
    d = nozzle.design
    dp = d.coolant.inlet_pressure - d.operating.chamber_pressure
    half = throttle.jacket_inlet_pressure(nozzle, 17e5, 0.5 * nozzle.budget.fuel_feed)
    assert half == pytest.approx(17e5 + dp / 4)


def test_film_velocity_follows_the_feed_at_every_ring(nozzle):
    nd = copy.deepcopy(nozzle)
    nd.design.film.ports = [FilmPort(x=-20, fraction=0.05, velocity=12.0)]
    point = throttle.off_design(nd, 17e5, 4.4)
    scale = point.budget.fuel_feed / nd.budget.fuel_feed
    assert point.design.film.injection_velocity == pytest.approx(nd.design.film.injection_velocity * scale)
    assert point.design.film.ports[0].velocity == pytest.approx(12.0 * scale)


def test_of_ratios_default_to_steps_towards_fuel_rich():
    design = Design()
    design.operating.of_ratio = 4.4
    np.testing.assert_allclose(throttle.design_of_ratios(design), [4.4, 4.0, 3.6, 3.2, 2.8, 2.4, 2.0, 1.6])
    design.throttle.of_ratios = [2.0, 3.0]
    assert throttle.design_of_ratios(design) == [3.0, 2.0]


def test_limits():
    settings = ThrottleSettings(min_subcooling=20.0)
    assert throttle.passes(result(0.5, 3.2), settings)
    assert throttle.passes(result(0.5, 3.2, n_post_chf=4), settings)
    assert not throttle.passes(result(0.5, 3.2, n_post_chf=4), ThrottleSettings(allow_post_chf=False))
    assert not throttle.passes(result(0.5, 3.2, n_failed=1), settings)
    assert not throttle.passes(result(0.5, 3.2, n_bulk_boiling=1), settings)
    assert not throttle.passes(result(0.5, 3.2, subcooling_min=19.0), settings)
    assert not throttle.passes(result(0.5, 3.2, error='CEA did not converge'), settings)


def map_of(limits):
    # a map where each chamber pressure passes at its limit O/F and below
    return [result(frac, of, n_failed=int(of > limit)) for frac, limit in limits.items() for of in (4.4, 3.2, 2.8, 2.0)]


def test_schedule_takes_the_highest_passing_of_and_prepares_the_next_point():
    schedule = throttle.pick_schedule(map_of({1.0: 4.4, 0.6: 4.4, 0.5: 4.4, 0.4: 3.2, 0.3: 2.8}), ThrottleSettings(), True)
    # 50 % must already be at the O/F of 40 %, or the engine would pass through 45 % too lean
    assert schedule == [(1.0, 4.4), (0.6, 4.4), (0.5, 3.2), (0.4, 2.8), (0.3, 2.8)]


def test_schedule_keeps_the_design_point():
    schedule = throttle.pick_schedule(map_of({1.0: 4.4, 0.7: 2.8}), ThrottleSettings(), True, 4.4)
    assert schedule == [(1.0, 4.4), (0.7, 2.8)]


def test_schedule_stops_where_no_of_passes():
    schedule = throttle.pick_schedule(map_of({1.0: 4.4, 0.5: 3.2, 0.3: 0.0, 0.2: 2.0}), ThrottleSettings(), True)
    assert schedule == [(1.0, 4.4), (0.5, 3.2)]


def test_schedule_is_read_for_one_film_mode_only():
    results = map_of({1.0: 4.4}) + [dataclasses.replace(r, film=False, n_failed=int(r.of_ratio > 2.8)) for r in map_of({1.0: 4.4})]
    assert throttle.pick_schedule(results, ThrottleSettings(), True) == [(1.0, 4.4)]
    assert throttle.pick_schedule(results, ThrottleSettings(), False) == [(1.0, 2.8)]


def test_schedule_is_empty_if_nothing_passes():
    assert throttle.pick_schedule(map_of({1.0: 0.0}), ThrottleSettings(), True) == []


def test_notes_flag_where_the_models_are_stretched():
    r = result(0.3, 2.8, v_throat=2.5, low_re_share=1.0, p_coolant_min=12e5, p_exit=0.3e5, film_past_throat=True)
    text = throttle.notes(r)
    for part in ('film past throat', 'below CHF test velocity', 'mostly Re < 2300', 'coolant below 17 bar', 'separation risk'):
        assert part in text
    assert throttle.notes(result(1.0, 4.4, v_throat=6, low_re_share=0.1, p_coolant_min=45e5, p_exit=1.2e5)) == ''


def test_csv_has_one_row_per_point(tmp_path):
    path = tmp_path / 'map.csv'
    throttle.write_csv([result(1.0, 4.4), result(0.5, 3.2, film=False)], path)
    rows = path.read_text().splitlines()
    assert len(rows) == 3 and rows[0].startswith('pc_fraction,of_ratio,film')


def test_map_plot_is_written(tmp_path):
    results = [result(frac, of, T_wall=500.0 + 100 * of, chf_ratio=of / 4, p_inlet=2e6 * frac, n_failed=int(of > 3)) for frac in (1.0, 0.5) for of in (4.4, 2.8)]
    throttle.plot_map(results, ThrottleSettings(), True, tmp_path / 'map.png', [(1.0, 2.8), (0.5, 2.8)])
    assert (tmp_path / 'map.png').stat().st_size > 0


def test_throttle_settings_round_trip(tmp_path):
    design = Design()
    design.throttle.of_ratios = [4.0, 3.0]
    design.throttle.schedule = [(1.0, 4.4), (0.5, 3.0)]
    path = tmp_path / 'design.json'
    design.save(path)
    assert Design.load(path) == design


def test_older_design_file_gets_the_default_settings():
    assert Design.load(EXAMPLE).throttle == ThrottleSettings()


def test_map_needs_the_boiling_model(tmp_path):
    design = Design()
    design.thermal.boiling = False
    with pytest.raises(ValueError, match='boiling'):
        throttle.run_points(design, [(1.0, 4.4, True)], str(tmp_path), True)


@pytest.mark.slow
def test_point_matches_the_design_run_and_film_credit_is_the_only_difference(nozzle, tmp_path):
    nd = copy.deepcopy(nozzle)
    d = nd.design
    d.thermal.step_size, d.thermal.cell_size_factor = 0.008, 0.3
    d.throttle.map_step_size, d.throttle.map_cell_size_factor = 0.008, 0.3

    setup = pipeline.build_thermal(nd, str(tmp_path / 'direct'))
    pipeline.run_thermal(setup)
    film = throttle.solve_point(nd, 1.0, d.operating.of_ratio, True, str(tmp_path / 'film'))
    bare = throttle.solve_point(nd, 1.0, d.operating.of_ratio, False, str(tmp_path / 'bare'))

    assert film.error == '' and bare.error == ''
    assert film.T_wall == pytest.approx(np.nanmax(setup.output.T_wall_i), abs=0.5)
    assert film.q_max == pytest.approx(np.nanmax(setup.output.q), rel=1e-3)
    assert film.thrust == pytest.approx(nd.solution.thrust)
    assert film.p_inlet == bare.p_inlet and film.m_coolant == bare.m_coolant
    assert bare.T_wall > film.T_wall
    assert not (tmp_path / 'film' / 'section_fields.npz').exists()
    assert (tmp_path / 'film' / 'sim_data.csv').exists()


def test_csv_round_trip(tmp_path):
    results = [result(0.5, 3.2, film=False, n_failed=2, T_wall=500.5, film_past_throat=True, schedule='no_film'), result(1.0, 4.4)]
    path = tmp_path / 'map.csv'
    throttle.write_csv(results, path)
    loaded = throttle.read_csv(path)
    assert loaded[0].film is False and loaded[0].film_past_throat is True
    assert loaded[0].n_failed == 2 and loaded[0].T_wall == 500.5 and loaded[0].schedule == 'no_film'
    assert np.isnan(loaded[1].T_wall)


def test_results_load_from_their_folder(tmp_path):
    throttle.write_csv([result(1.0, 4.4)], tmp_path / 'throttle_map.csv')
    throttle.write_csv([result(1.0, 4.4, schedule='film'), result(0.5, 3.2, schedule='film'), result(1.0, 4.4, film=False, schedule='no_film')],
                       tmp_path / 'throttle_schedule.csv')
    map_results, schedules = throttle.load_results(tmp_path)
    assert len(map_results) == 1
    assert {name: len(points) for name, points in schedules.items()} == {'film': 2, 'no_film': 1}


def test_map_draws_with_points_missing():
    from matplotlib.figure import Figure

    for results in ([], [result(1.0, 4.4, T_wall=600.0, chf_ratio=1.0, p_inlet=45e5)]):
        fig = Figure()
        throttle.draw_map(fig, results, ThrottleSettings(), True, axes=([1.0, 0.5], [4.4, 3.2]))
        fig.canvas.draw()


def test_map_includes_the_design_point():
    design = Design()
    design.throttle.pc_fractions = [0.5]
    design.throttle.of_ratios = [3.0]
    assert throttle.map_axes(design) == ([1.0, 0.5], [design.operating.of_ratio, 3.0])


def test_film_credit_needs_a_film():
    design = Design()
    assert throttle.credit_modes(design) == (True,)
    design.film.injector_fraction = 0.2
    assert throttle.credit_modes(design) == (True, False)


@pytest.mark.slow
def test_stopping_ends_the_worker_processes(tmp_path):
    import multiprocessing

    design = Design.load(EXAMPLE)
    design.throttle.map_step_size = 0.008
    points = [(1.0, 4.4, True), (0.5, 4.4, True), (0.3, 4.4, True)]
    with pytest.raises(throttle.ThrottleCancelled):
        throttle.run_points(design, points, str(tmp_path), True, jobs=2, stop=lambda: True)
    assert multiprocessing.active_children() == []
