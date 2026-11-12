"""
Thermal analysis of a finished design while throttling. The contour is fixed, and an operating point is a chamber pressure and a core
O/F. Everything else follows from these two, and the thermal model runs on each point unchanged:

    total flow       = design flow * (Pc / design Pc) * (design c* / c*(Pc, O/F))      same throat and c* efficiency
    split of flows   = mass_budget() at the new core O/F, with the film fractions of the design
    film velocity    follows the fuel feed, the orifices are fixed
    jacket pressure  see jacket_inlet_pressure()

The O/F schedule is not an input: run_map() solves every chamber pressure with every O/F, and pick_schedule() reads the schedule off this
map. The map is solved twice, with the film as modelled and without credit for it (same flows and pressures, the wall does not see the
film). The liquid film model is not validated at and downstream of the throat, and fuel rich points reach it, so the real engine lies
between the two.

    map_results = run_map(nd, out, jobs)
    schedule = pick_schedule(map_results, nd.design.throttle, film=False)     # [(pc fraction, O/F)]
"""

import contextlib
import copy
import csv
import dataclasses
import math
import multiprocessing
import os
import queue
import traceback
import typing
import warnings
from dataclasses import dataclass

import numpy as np

from .. import pipeline
from ..core.chemistry import BipropCEA
from ..core.mass_budget import mass_budget
from .isentropic_flow import Isentropic
from .regen import POST_CHF_P_MIN

CHF_MIN_VELOCITY = 3.0          # lowest coolant velocity of the ethanol CHF tests of Meyer et al. [m/s]
LAMINAR_RE       = 2300.0       # below this 'gnielinski-rough' holds the heat transfer of Re = 2300, which is on the optimistic side
SEPARATION_RATIO = 0.4          # exit pressure over ambient pressure below which the nozzle flow can separate, as in design_nozzle()


class ThrottleCancelled(Exception):
    """The analysis was stopped with its stop function"""


@dataclass
class ThrottleResult:
    pc_fraction: float                  # of the design chamber pressure
    of_ratio: float                     # core O/F
    film: bool                          # True: film as modelled, False: no credit for the film
    Pc: float = math.nan                # chamber pressure [Pa]
    of_feed: float = math.nan           # O/F of the feed system, film included
    p_inlet: float = math.nan           # coolant pressure at the channel inlet [Pa]
    p_coolant_min: float = math.nan     # lowest coolant pressure [Pa]
    dp_channels: float = math.nan       # pressure drop of the channels [Pa]
    m_total: float = math.nan           # mass flow through the throat [kg/s]
    m_oxidiser: float = math.nan        # [kg/s]
    m_fuel: float = math.nan            # fuel feed [kg/s]
    m_coolant: float = math.nan         # through the channels [kg/s]
    thrust: float = math.nan            # estimate with attached flow [N]
    Tc: float = math.nan                # combustion temperature [K]
    cstar: float = math.nan             # c* of CEA [m/s]
    p_exit: float = math.nan            # [Pa]
    T_wall: float = math.nan            # highest gas side wall temperature [K]
    T_wall_coolant: float = math.nan    # highest wall temperature in the channels [K]
    q_max: float = math.nan             # highest heat flux into the chamber wall [W/m^2]
    chf_ratio: float = math.nan         # highest mean heat flux at the channel bottom over the CHF
    n_sections: int = 0
    n_post_chf: int = 0                 # sections on the post-CHF branch
    n_failed: int = 0                   # sections where boiling can not carry the heat flux, wall temperatures are not a prediction
    n_bulk_boiling: int = 0             # sections where the coolant itself reaches saturation, results are not valid downstream
    subcooling_min: float = math.nan    # lowest distance of the coolant from saturation [K]
    T_coolant_out: float = math.nan     # [K]
    v_throat: float = math.nan          # coolant velocity at the throat [m/s]
    Re_throat: float = math.nan         # coolant Reynolds number at the throat
    low_re_share: float = math.nan      # share of the sections below Re = 2300
    film_end: float = math.nan          # end of the liquid film, x of the contour [mm]
    film_past_throat: bool = False      # the liquid film reaches the throat, where its model is not validated
    dT_wall: float = math.nan           # highest temperature difference through the inner wall [K]
    sig_secondary: float = math.nan     # highest thermal stress [Pa]
    X: float = math.nan                 # highest primary stress / yield strength
    Y: float = math.nan                 # highest thermal stress / yield strength
    creep_damage: float = math.nan      # highest life fraction used by creep rupture
    life_steady: float = math.nan       # lowest ligament life, steady state [firings]
    life_startup: float = math.nan      # lowest ligament life, start-up bound [firings]
    stiffness_fuel: float = math.nan    # injector pressure drop / Pc of the fuel, relative to the design point, one fixed area
    stiffness_ox: float = math.nan      # the same for the oxidiser, as an incompressible liquid
    ambient_pressure: float = 101325.0  # [Pa]
    error: str = ""                     # the point could not be solved
    schedule: str = ""                  # name of the schedule, empty for points of the map

    @property
    def separation_risk(self):
        return self.p_exit < SEPARATION_RATIO * self.ambient_pressure


def jacket_inlet_pressure(nd, Pc, fuel_feed):
    """Coolant pressure at the channel inlet with the throttle valve upstream of the channels. The fuel injector and the channels are
    one fixed area, with the pressure drop of the design point. A staged injector has less area at low flow, so this is the lowest
    pressure the jacket can see. To use a measured or designed injector curve, replace this function."""
    design, budget = nd.design, nd.budget
    dp = design.coolant.inlet_pressure - design.operating.chamber_pressure
    return Pc + dp * (fuel_feed / budget.fuel_feed)**2


def off_design(nd, Pc, of_ratio):
    """The NozzleDesign of nd at another chamber pressure and core O/F, with the same contour. build_thermal and run_thermal take it
    like the design point. nd itself is not changed."""
    d0, b0 = nd.design, nd.budget
    fuel, ox = pipeline.propellant_blends(d0)
    chem = BipropCEA(fuel, ox, Pc, d0.operating.ambient_pressure)
    chem.nozzle_output(of_ratio, nd.solution.expansion_ratio)

    total = b0.total * (Pc / d0.operating.chamber_pressure) * (nd.chem.cstar_eq / chem.cstar_eq)
    budget = mass_budget(total, of_ratio, d0.film, d0.coolant.fuel_fraction)

    d = copy.deepcopy(d0)
    d.operating.chamber_pressure = Pc
    d.operating.of_ratio = of_ratio
    d.coolant.inlet_pressure = jacket_inlet_pressure(nd, Pc, budget.fuel_feed)
    scale = budget.fuel_feed / b0.fuel_feed                 # the film fractions are constant, so every film flow scales with the feed
    d.film.injection_velocity *= scale
    for port in d.film.ports:
        port.velocity *= scale
    return dataclasses.replace(nd, design=d, budget=budget, chem=chem)


def design_of_ratios(design):
    # the O/F values of the map, from the design O/F towards fuel rich: 4.4, 4.0, ... 1.6 for a design at 4.4
    th = design.throttle
    if th.of_ratios:
        return sorted(th.of_ratios, reverse=True)
    of = design.operating.of_ratio
    return [round(of * (1 - k / 11), 3) for k in range(8)]


def thrust_estimate(nd, cea, gas, geometry):
    # thrust with attached flow. Only the ratio to the design point is used, see solve_point
    op = nd.design.operating
    v_exit = gas.M[-1] * np.sqrt(cea.gamma * 8314.46 / cea.MW * gas.T_s[-1])
    return nd.budget.total * v_exit * op.eta_nozzle + (gas.p_s[-1] - op.ambient_pressure) * np.pi * geometry[-1, 1]**2


def design_thrust_estimate(nd, geometry):
    # the estimate of thrust_estimate at the design point, on the same sections as the point it is compared with
    d = nd.design
    fuel, ox = pipeline.propellant_blends(d)
    cea = BipropCEA(fuel, ox, d.operating.chamber_pressure)
    cea.metric_cea_output("throat", d.operating.of_ratio, nd.solution.expansion_ratio)
    gas = Isentropic(d.operating.chamber_pressure, cea.Tc, cea.gamma, cea.Pr, geometry[:, 0], geometry[:, 1])
    gas.calculate()
    return thrust_estimate(nd, cea, gas, geometry)


def _largest(values):
    # the stress results are all nan for materials without the data
    values = np.asarray(values, dtype=float)
    return float(np.nanmax(values)) if np.any(np.isfinite(values)) else math.nan


def _smallest(values):
    values = np.asarray(values, dtype=float)
    return float(np.nanmin(values)) if np.any(np.isfinite(values)) else math.nan


def _result(nd, point, setup, sim, film, pc_fraction):
    design, budget, op = nd.design, point.budget, point.design.operating
    out, gas = setup.output, setup.gas
    geometry = setup.geometry
    x = geometry[:, 0] * 1e3
    throat = int(np.argmin(geometry[:, 1]))
    pc_ratio = op.chamber_pressure / design.operating.chamber_pressure
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # sections without a CHF, e.g. a coolant above its critical pressure
        chf_ratio = out.q_c_bottom / out.q_chf
    liquid = np.asarray(setup.film.liquid, dtype=bool)
    film_end = float(x[liquid].max()) if liquid.any() else math.nan
    return ThrottleResult(
        pc_fraction=pc_fraction, of_ratio=op.of_ratio, film=film,
        Pc=op.chamber_pressure, of_feed=budget.of_feed,
        p_inlet=point.design.coolant.inlet_pressure, p_coolant_min=_smallest(out.P_c), dp_channels=_largest(out.P_c) - _smallest(out.P_c),
        m_total=budget.total, m_oxidiser=budget.oxidiser, m_fuel=budget.fuel_feed, m_coolant=budget.coolant,
        thrust=float(nd.solution.thrust * thrust_estimate(point, setup.cea, gas, geometry) / design_thrust_estimate(nd, geometry)),
        Tc=float(setup.cea.Tc), cstar=float(point.chem.cstar_eq), p_exit=float(gas.p_s[-1]),
        T_wall=_largest(out.T_wall_i), T_wall_coolant=_largest(out.T_wall_c), q_max=_largest(out.q), chf_ratio=_largest(chf_ratio),
        n_sections=len(x), n_post_chf=int(np.sum(out.chf_state == 1)), n_failed=int(np.sum(out.chf_state == 2)),
        n_bulk_boiling=len(sim.bulk_boiling), subcooling_min=_smallest(out.T_sat - out.T_c), T_coolant_out=_largest(out.T_c),
        v_throat=float(out.v_coolant[throat]), Re_throat=float(out.Re[throat]), low_re_share=float(np.mean(out.Re < LAMINAR_RE)),
        film_end=film_end, film_past_throat=bool(liquid[throat:].any()),
        dT_wall=_largest(out.dT_wall), sig_secondary=_largest(out.sig_secondary), X=_largest(out.X), Y=_largest(out.Y),
        creep_damage=_largest(out.creep_damage), life_steady=_smallest(out.N_life), life_startup=_smallest(out.N_life_startup),
        stiffness_fuel=(budget.fuel_feed / nd.budget.fuel_feed)**2 / pc_ratio,
        stiffness_ox=(budget.oxidiser / nd.budget.oxidiser)**2 / pc_ratio,
        ambient_pressure=op.ambient_pressure,
    )


def solve_point(nd, pc_fraction, of_ratio, film, folder, coarse=True, progress=None):
    """Thermal simulation of one operating point, the files of the run go to folder. A point which can not be solved is returned with
    its error, so that it does not end the map. coarse uses the mesh of the map. progress(done, total, index) is called after every
    section."""
    os.makedirs(folder, exist_ok=True)
    try:
        with open(os.path.join(folder, "log.txt"), "w") as log, contextlib.redirect_stdout(log):
            point = off_design(nd, pc_fraction * nd.design.operating.chamber_pressure, of_ratio)
            if coarse:
                th, settings = point.design.thermal, point.design.throttle
                th.step_size, th.cell_size_factor = settings.map_step_size, settings.map_cell_size_factor
                th.throat_step = 0.0
            setup = pipeline.build_thermal(point, folder)
            modelled = setup.film
            if not film:
                setup.film = False
            sim = pipeline.run_thermal(setup, progress)
            setup.film = modelled
            os.remove(os.path.join(folder, "section_fields.npz"))           # large, and only needed for the 3D plot of a single run
            return _result(nd, point, setup, sim, film, pc_fraction)
    except Exception:
        return ThrottleResult(pc_fraction, of_ratio, film, error=traceback.format_exc(limit=-3))


def _worker(design, tasks, finished):
    # worker process: solves the points of the queue until it gets None. Answers (index, result, part): part is the share of the
    # sections of the point that are solved, with result None until the point is done
    nd = pipeline.design_nozzle(design)
    for index, case in iter(tasks.get, None):
        # the points of the map take seconds; those on the mesh of the design minutes, so they tell how far they are
        report = None if case[-1] else (lambda done, total, idx, index=index: finished.put((index, None, done / total)))
        finished.put((index, solve_point(nd, *case, progress=report), 1.0))


def _point_name(pc_fraction, of_ratio, film):
    return "pc%.2f_of%.2f_%s" % (pc_fraction, of_ratio, "film" if film else "no_film")


def run_points(design, points, folder, coarse, jobs=None, progress=None, stop=None, status=None):
    """Solves the points (pc fraction, O/F, film) in parallel. progress(done, total, result) is called as each point finishes, in any
    order. status(done, total) is called when the points start and as they advance, done being the points solved and the solved share
    of the ones in work (told for the mesh of the design only, where a point takes minutes). stop() is asked while waiting, if it
    returns True the workers are stopped and ThrottleCancelled is raised. Own worker processes rather than a process pool, because a
    pool can not stop a point that is being solved."""
    if not design.thermal.boiling:
        raise ValueError("The throttle analysis judges the points by the critical heat flux, which needs ThermalSettings.boiling")
    # one point per process, threads of the linear algebra libraries would only compete with the other processes
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(name, "1")
    # spawn, not fork: a forked copy of a process with gmsh or Qt in it is not safe
    ctx = multiprocessing.get_context("spawn")
    tasks, finished = ctx.Queue(), ctx.Queue()
    for index, (frac, of, film) in enumerate(points):
        tasks.put((index, (frac, of, film, os.path.join(folder, _point_name(frac, of, film)), coarse)))
    count = min(jobs or max(1, (os.cpu_count() or 2) - 2), max(len(points), 1))
    workers = [ctx.Process(target=_worker, args=(design, tasks, finished), daemon=True) for _ in range(count)]
    results = [None] * len(points)
    parts = [0.0] * len(points)
    if status is not None:
        status(0.0, len(points))
    try:
        for worker in workers:
            tasks.put(None)
            worker.start()
        done = 0
        while done < len(points):
            try:
                index, result, part = finished.get(timeout=0.2)
            except queue.Empty:
                if stop is not None and stop():
                    raise ThrottleCancelled()
                if not any(worker.is_alive() for worker in workers):
                    raise RuntimeError("The worker processes ended before all points were solved")
                continue
            parts[index] = part
            if result is not None:
                done += 1
                results[index] = result
                if progress is not None:
                    progress(done, len(points), result)
            if status is not None:
                status(sum(parts), len(points))
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join()
    return results


def map_axes(design):
    """Chamber pressure fractions and O/F values of the map, the design point is always part of it"""
    fractions = sorted(set(design.throttle.pc_fractions) | {1.0}, reverse=True)
    ofs = sorted(set(design_of_ratios(design)) | {design.operating.of_ratio}, reverse=True)
    return fractions, ofs


def credit_modes(design):
    # without film the two solutions are the same
    return (True, False) if design.film.total_fraction > 0 else (True,)


def run_map(nd, out, jobs=None, progress=None, stop=None, status=None):
    """Every chamber pressure with every O/F, with and without credit for the film"""
    d = nd.design
    fractions, ofs = map_axes(d)
    points = [(frac, of, film) for film in credit_modes(d) for frac in fractions for of in ofs]
    return run_points(d, points, os.path.join(out, "throttle_map"), True, jobs, progress, stop, status)


def passes(result, settings):
    """True if the point keeps the limits. Failed sections include every section above the CHF below 17 bar of coolant pressure, where
    the post-CHF branch does not exist, and every section beyond the second excursion above it."""
    if result.error or result.n_failed or result.n_bulk_boiling:
        return False
    if result.n_post_chf and not settings.allow_post_chf:
        return False
    return result.subcooling_min >= settings.min_subcooling


def pick_schedule(results, settings, film, design_of=None):
    """(pc fraction, O/F) from high to low chamber pressure: the highest O/F which keeps the limits at each chamber pressure of the map.

    O/F is interpolated between the points in operation, so a point must also be rich enough for the next point down, or the engine
    would reach that point on its way down with too lean a mixture. This matters most when the coolant falls below 17 bar, where the
    post-CHF branch ends. The design point keeps design_of (the highest O/F of the map by default) if it passes. The schedule stops
    above the first chamber pressure where no O/F keeps the limits."""
    results = [r for r in results if r.film == film]
    fractions = sorted({r.pc_fraction for r in results}, reverse=True)
    best = []
    for frac in fractions:
        passing = [r.of_ratio for r in results if r.pc_fraction == frac and passes(r, settings)]
        if not passing:
            break
        best.append(max(passing))
    if not best:
        return []
    ofs = [min(best[i], best[i + 1]) for i in range(len(best) - 1)] + [best[-1]]
    if fractions[0] == 1.0:
        ofs[0] = best[0] if design_of is None else min(best[0], design_of)
    return list(zip(fractions, ofs))


def run_schedules(nd, map_results, out, jobs=None, progress=None, stop=None, status=None):
    """The schedules of the map on the mesh of the design: {name: [ThrottleResult]}, a schedule of the design file with and without the film"""
    d = nd.design
    schedules = {}
    for film in credit_modes(d):
        name = "film" if film else "no_film"
        schedule = pick_schedule(map_results, d.throttle, film, d.operating.of_ratio)
        if schedule:
            schedules[name] = [(frac, of, film) for frac, of in schedule]
    for film in credit_modes(d) if d.throttle.schedule else ():
        schedules["design_file_film" if film else "design_file_no_film"] = [(frac, of, film) for frac, of in d.throttle.schedule]

    points = sorted({point for schedule in schedules.values() for point in schedule})
    solved = dict(zip(points, run_points(d, points, os.path.join(out, "throttle_schedule"), False, jobs, progress, stop, status)))
    return {name: sorted((dataclasses.replace(solved[point], schedule=name) for point in schedule), key=lambda r: -r.pc_fraction)
            for name, schedule in schedules.items()}


def write_csv(results, path):
    names = [f.name for f in dataclasses.fields(ThrottleResult)]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(names)
        for r in results:
            writer.writerow([getattr(r, name) for name in names])


def read_csv(path):
    """The results of write_csv"""
    hints = typing.get_type_hints(ThrottleResult)
    convert = {bool: lambda text: text == "True", int: int, float: float, str: str}
    with open(path, newline="") as f:
        return [ThrottleResult(**{name: convert[hints[name]](text) for name, text in row.items() if name in hints}) for row in csv.DictReader(f)]


def load_results(folder):
    """Map and schedules of an earlier run from its folder: (map results, {name: [ThrottleResult]})"""
    schedules = {}
    path = os.path.join(folder, "throttle_schedule.csv")
    for r in read_csv(path) if os.path.exists(path) else ():
        schedules.setdefault(r.schedule, []).append(r)
    return read_csv(os.path.join(folder, "throttle_map.csv")), schedules


def notes(result):
    """What limits the meaning of a point, as short text. These do not make a point fail."""
    r = result
    text = []
    if r.film and r.film_past_throat:
        text.append("film past throat")
    if r.v_throat < CHF_MIN_VELOCITY:
        text.append("below CHF test velocity")
    if r.low_re_share > 0.5:
        text.append("mostly Re < 2300")
    if r.p_coolant_min < POST_CHF_P_MIN:
        text.append("coolant below 17 bar")
    if r.separation_risk:
        text.append("separation risk at this ambient pressure")
    return ", ".join(text)


def summary(schedules, settings):
    # results of the schedules for the terminal
    for name, results in schedules.items():
        print("\nSchedule: %s" % name.replace("_", " "))
        print("%5s %5s %6s %7s %6s %7s %6s %5s %7s %5s %5s %8s  %s"
              % ("Pc", "O/F", "feed", "p_in", "F", "T_wall", "q/CHF", "post", "subcool", "fail", "Y", "life", "notes"))
        print("%5s %5s %6s %7s %6s %7s %6s %5s %7s %5s %5s %8s"
              % ("[%]", "[-]", "O/F", "[bar]", "[N]", "[K]", "[-]", "[-]", "[K]", "[-]", "[-]", "[firings]"))
        for r in results:
            if r.error:
                print("%5.0f %5.2f  not solved: %s" % (r.pc_fraction * 100, r.of_ratio, r.error.strip().splitlines()[-1]))
                continue
            state = "" if passes(r, settings) else "OUTSIDE LIMITS, "
            print("%5.0f %5.2f %6.2f %7.1f %6.0f %7.0f %6.2f %5d %7.0f %5d %5.2f %8.3g  %s%s"
                  % (r.pc_fraction * 100, r.of_ratio, r.of_feed, r.p_inlet / 1e5, r.thrust, r.T_wall, r.chf_ratio, r.n_post_chf,
                     r.subcooling_min, r.n_failed, r.Y, r.life_startup, state, notes(r)))


def draw_map(fig, results, settings, film, schedule=(), axes=None, fontsize=8.5, theme="light"):
    """Heatmaps of the map in fig, one of chamber pressure against O/F per quantity, the strong end of the colours is the unfavourable
    one in each. Cells outside the limits are hatched, the schedule is outlined. axes: (fractions, O/F values) to show, by default those
    of the results. Points which are not solved yet stay empty. theme: look of plot_style, for the colours of the cells."""
    from matplotlib.patches import Rectangle

    from .. import plot_style

    look = plot_style.palette(theme)
    colors = look["map_cmap"]
    results = [r for r in results if r.film == film]
    fractions, ofs = axes or (sorted({r.pc_fraction for r in results}, reverse=True), sorted({r.of_ratio for r in results}, reverse=True))
    grid = {(r.pc_fraction, r.of_ratio): r for r in results}
    # title, value, format, True if a high value is the unfavourable end
    panels = (("Peak gas side wall temperature [K]", lambda r: r.T_wall, "%.0f", True),
              ("Heat flux at the channel bottom / CHF", lambda r: r.chf_ratio, "%.2f", True),
              ("Lowest subcooling of the coolant [K]", lambda r: r.subcooling_min, "%.0f", False),
              ("Coolant pressure at the channel inlet [bar]", lambda r: r.p_inlet / 1e5, "%.1f", False))

    title = "with the film as modelled" if film else "without credit for the film"
    fig.suptitle("Throttle map, %s. Hatched: outside the limits. Outlined: schedule" % title, fontsize=fontsize + 2)
    for ax, (label, value, fmt, high_is_bad) in zip(fig.subplots(2, 2).flat, panels):
        ax._tcd_plain = True                    # no grid or background of the theme over the cells
        cmap = colors if high_is_bad else colors.reversed()
        data = np.array([[value(grid[f, o]) if (f, o) in grid and not grid[f, o].error else np.nan for o in ofs] for f in fractions])
        solved = bool(np.isfinite(data).any())
        image = ax.imshow(data, cmap=cmap, aspect="auto")
        if solved:
            fig.colorbar(image, ax=ax, shrink=0.9)
        ax.set_title(label, fontsize=fontsize + 1.5)
        ax.set_xticks(range(len(ofs)), ["%.2g" % o for o in ofs])
        ax.set_yticks(range(len(fractions)), ["%.0f" % (f * 100) for f in fractions])
        ax.set_xlabel("Core O/F", fontsize=fontsize + 0.5)
        ax.set_ylabel("Chamber pressure [% of design]", fontsize=fontsize + 0.5)
        ax.tick_params(length=0, labelsize=fontsize)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if not solved:
            continue
        for i, f in enumerate(fractions):
            for j, o in enumerate(ofs):
                if np.isnan(data[i, j]):
                    continue
                # dark numbers and hatching on a light cell, light ones on a dark cell
                light_cell = plot_style.luminance(cmap(image.norm(data[i, j]))) > 0.5
                ax.text(j, i, fmt % data[i, j], ha="center", va="center", fontsize=fontsize, color="#1a1a1a" if light_cell else "white")
                if not passes(grid[f, o], settings):
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="////", linewidth=0,
                                           edgecolor=(0.1, 0.1, 0.1, 0.45) if light_cell else (1.0, 1.0, 1.0, 0.4)))
        for frac, of in schedule:
            if frac in fractions and of in ofs:
                ax.add_patch(Rectangle((ofs.index(of) - 0.47, fractions.index(frac) - 0.47), 0.94, 0.94, fill=False,
                                       edgecolor=look["map_outline"], linewidth=2.2))


def plot_map(results, settings, film, path, schedule=()):
    """draw_map to an image file"""
    from matplotlib.figure import Figure

    fig = Figure(figsize=(13, 9.5), layout="constrained")
    draw_map(fig, results, settings, film, schedule)
    fig.savefig(path, dpi=200)


def run(nd, out, jobs=None, verify=True, progress=None, stop=None, status=None):
    """The whole analysis of a design: the map, its schedules on the mesh of the design, csv files and plots in out. progress(stage, done,
    total, result) with stage 'map' or 'schedule' is called after every point, status(stage, done, total) when a stage starts and as
    its points advance (see run_points). stop() ends the run with ThrottleCancelled."""
    d = nd.design
    report = (lambda stage: lambda *args: progress(stage, *args)) if progress is not None else (lambda stage: None)
    tell = (lambda stage: lambda *args: status(stage, *args)) if status is not None else (lambda stage: None)
    map_results = run_map(nd, out, jobs, report("map"), stop, tell("map"))
    write_csv(map_results, os.path.join(out, "throttle_map.csv"))
    for film in credit_modes(d):
        name = "throttle_map_%s.png" % ("film" if film else "no_film")
        plot_map(map_results, d.throttle, film, os.path.join(out, name), pick_schedule(map_results, d.throttle, film, d.operating.of_ratio))

    schedules = {}
    if verify:
        schedules = run_schedules(nd, map_results, out, jobs, report("schedule"), stop, tell("schedule"))
        write_csv([r for results in schedules.values() for r in results], os.path.join(out, "throttle_schedule.csv"))
        summary(schedules, d.throttle)
    else:
        for film in credit_modes(d):
            print("Schedule %s: %s" % ("with film" if film else "without film", pick_schedule(map_results, d.throttle, film, d.operating.of_ratio)))
    return map_results, schedules
