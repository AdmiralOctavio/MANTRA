"""
From a Design to a thrust chamber: combustion properties with CEA, the nozzle contour with the Method of Characteristics, the split of
the mass flow, and the regenerative cooling simulation of PyRocket on that contour.

    nozzle = design_nozzle(design)                    # seconds
    thermal = build_thermal(nozzle, output_folder)    # sets up the thermal model like PyRocket's config.py
    sim = run_thermal(thermal, progress)              # minutes, writes sim_data.csv and section_fields.npz to the folder
"""

import os
import warnings
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

import numpy as np

from .core import propellants as props
from .core.chemistry import BipropCEA
from .core.design import Design
from .core.mass_budget import MassBudget, mass_budget
from .nozzle import export
from .nozzle.moc import NozzleSolution
from .nozzle.sizing import size_nozzle
from .thermal import regen
from .thermal.coolant import Coolant
from .thermal.film import FilmCooling
from .thermal.geometry import ChamberGeometry, CoolingGeometry
from .thermal.isentropic_flow import Isentropic
from .thermal.materials import MATERIALS
from .thermal.output import Output1D, Settings2D

G0 = 9.80665


@dataclass
class NozzleDesign:
    design: Design
    chem: BipropCEA                  # combustion properties at the core O/F and the expansion ratio of the contour
    solution: NozzleSolution         # contour and performance
    budget: MassBudget               # split of the mass flow
    expansion_history: List[tuple] = field(default_factory=list)    # (expansion ratio of CEA, expansion ratio of the contour)
    warnings: List[str] = field(default_factory=list)


def propellant_blends(design):
    p = design.propellants
    return props.fuel_blend(p.fuel, p.fuel_concentration), props.oxidiser_blend(p.oxidiser)


def design_nozzle(design, tol=1e-4, max_iter=10):
    """Nozzle for the thrust and the perfect expansion of the design.

    The exit gamma of CEA depends on the expansion ratio, which is only known once the nozzle is there. The nozzle solver used to
    take it at a fixed expansion ratio of 5.77, here CEA and the nozzle sizing are repeated until the expansion ratio of CEA is the
    one of the contour (usually 2 to 3 times).
    """
    fuel, ox = propellant_blends(design)
    op = design.operating
    chem = BipropCEA(fuel, ox, op.chamber_pressure, op.ambient_pressure)

    with warnings.catch_warnings(record=True) as caught:
        # warnings of the design (e.g. L* too small) are kept, the numpy warnings of trial points of the solver are not
        warnings.simplefilter("ignore")
        warnings.simplefilter("always", UserWarning)
        # start with the expansion ratio for the expansion to the ambient pressure
        chem.nozzle_output(op.of_ratio, 5.0)
        eps = chem.expansion_ratio_ideal
        history = []
        for _ in range(max_iter):
            chem.nozzle_output(op.of_ratio, eps)
            solution = size_nozzle(chem, op, design.chamber, design.nozzle)
            history.append((eps, solution.expansion_ratio))
            if abs(solution.expansion_ratio - eps) < tol * eps:
                break
            eps = solution.expansion_ratio
        else:
            warnings.warn("The expansion ratio of CEA and of the contour did not converge, last %.4f and %.4f" % history[-1])

    notes = [str(w.message) for w in caught]
    if not solution.converged:
        notes.append("Nozzle sizing did not converge: " + solution.message)
    if solution.P_exit < 0.4 * op.ambient_pressure:
        notes.append("Exit pressure %.0f Pa is below 40 %% of the ambient pressure: flow separation risk" % solution.P_exit)
    if solution.exit_angle > 6:
        notes.append("Exit angle %.1f deg is above 6 deg" % solution.exit_angle)

    budget = mass_budget(solution.mdot, op.of_ratio, design.film, design.coolant.fuel_fraction)
    return NozzleDesign(design=design, chem=chem, solution=solution, budget=budget, expansion_history=history, warnings=notes)


def nozzle_summary(nd):
    """Inputs and results of the nozzle as rows of (category, parameter, value, unit), like params.csv of the nozzle solver."""
    d, s, b, c = nd.design, nd.solution, nd.budget, nd.chem
    op, ch = d.operating, d.chamber
    if ch.lstar_sizing:
        chamber_len_row = ("Input", "Chamber L*", ch.lstar, "m")
    else:
        chamber_len_row = ("Input", "Chamber Length", ch.length, "mm")
    g = c.gamma_throat
    M_optimal = np.sqrt(((op.chamber_pressure / op.ambient_pressure) ** ((g - 1) / g) - 1) * 2 / (g - 1))
    p = d.propellants
    return [
        # ── Inputs ────────────────────────────────────────────────────────────
        ("Input", "Propellant", props.propellant_name(p.oxidiser, p.fuel, p.fuel_concentration), "-"),
        ("Input", "Chamber Pressure", op.chamber_pressure, "Pa"),
        ("Input", "Ambient Pressure", op.ambient_pressure, "Pa"),
        ("Input", "O/F Ratio (core)", op.of_ratio, "-"),
        ("Input", "Target Thrust", op.thrust, "N"),
        ("Input", "c* Efficiency", op.eta_c_star, "-"),
        ("Input", "Nozzle Efficiency", op.eta_nozzle, "-"),
        ("Input", "Refinement Factor", d.nozzle.refinement, "-"),
        ("Input", "Nozzle Length Fraction", d.nozzle.shorten, "-"),
        ("Input", "L* Sizing", ch.lstar_sizing, "bool"),
        chamber_len_row,
        ("Input", "Contraction Ratio", ch.contraction_ratio, "-"),
        ("Input", "Chamber Slope", ch.slope, "deg"),
        ("Input", "Radius 1", ch.R1, "mm"),
        ("Input", "Radius 2", ch.R2, "mm"),
        ("Input", "Film Fraction of Fuel Feed", d.film.total_fraction, "-"),
        # ── Outputs ───────────────────────────────────────────────────────────
        ("Output", "Nozzle Length", s.wall_x[-1], "mm"),
        ("Output", "Chamber Length", s.chamber_length, "mm"),
        ("Output", "Total Length", s.wall_x[-1] - s.wall_x[0], "mm"),
        ("Output", "Throat Radius", s.throat_radius, "mm"),
        ("Output", "Throat Diameter", 2 * s.throat_radius, "mm"),
        ("Output", "Chamber Diameter", 2 * s.throat_radius * np.sqrt(ch.contraction_ratio), "mm"),
        ("Output", "Exit Radius", s.exit_radius, "mm"),
        ("Output", "Exit Angle", s.exit_angle, "deg"),
        ("Output", "Combustion Temperature", c.Tc, "K"),
        ("Output", "Gamma (throat)", c.gamma_throat, "-"),
        ("Output", "Gamma (exit)", c.gamma_exit, "-"),
        ("Output", "c* (CEA)", c.cstar_eq, "m/s"),
        ("Output", "Optimal Exit Mach", M_optimal, "-"),
        ("Output", "Optimal Expansion Ratio (CEA)", c.expansion_ratio_ideal, "-"),
        ("Output", "True Expansion Ratio", s.expansion_ratio, "-"),
        ("Output", "Design Exit Mach", s.M_exit_design, "-"),
        ("Output", "Predicted Exit Mach", s.M_exit, "-"),
        ("Output", "Total Thrust", s.thrust, "N"),
        ("Output", "Momentum Thrust", s.thrust_momentum, "N"),
        ("Output", "Pressure Thrust", s.thrust_pressure, "N"),
        ("Output", "Thrust Coefficient", s.C_F, "-"),
        ("Output", "Exit Pressure", s.P_exit, "Pa"),
        ("Output", "Exit Velocity", s.Ve, "m/s"),
        ("Output", "Specific Impulse (Design)", s.thrust / (s.mdot * G0), "s"),
        ("Output", "Specific Impulse (CEA, ideal)", c.isp_ideal, "s"),
        ("Output", "Mass Flow (throat)", b.total, "kg/s"),
        ("Output", "Oxidiser Flow", b.oxidiser, "kg/s"),
        ("Output", "Fuel Flow (core)", b.fuel_core, "kg/s"),
        ("Output", "Fuel Flow (feed, with film)", b.fuel_feed, "kg/s"),
        ("Output", "Film Flow", b.film, "kg/s"),
        ("Output", "Coolant Flow (channels)", b.coolant, "kg/s"),
        ("Output", "O/F (feed, with film)", b.of_feed, "-"),
    ]


def write_nozzle_outputs(nd, folder, dxf=True, stl=False):
    """params.csv, Contour.csv and the CAD files of the nozzle in folder"""
    import csv
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "params.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Parameter", "Value", "Unit"])
        writer.writerows(nozzle_summary(nd))
    s = nd.solution
    export.create_csv(s.wall_x, s.wall_y, folder)
    if dxf:
        export.create_dxf(s.wall_x / 1000, -s.wall_y / 1000, s.M_exit_design, folder)
    if stl:
        export.create_stl(s.wall_x, s.wall_y, s.M_exit_design, folder)


def build_thermal(nd, save_path):
    """Sets up the thermal model on the contour of the nozzle, like the setup part of PyRocket's config.py. Returns the objects
    under the names config.py used."""
    d = nd.design
    th, chn, cool, op = d.thermal, d.channels, d.coolant, d.operating
    budget = nd.budget
    os.makedirs(save_path, exist_ok=True)

    material = MATERIALS[th.material]
    fuel, ox = propellant_blends(d)

    # generate chamber geometry
    chamber = ChamberGeometry.from_contour(nd.solution.wall_x / 1000, nd.solution.wall_y / 1000, th.step_size,
                                           expansion_ratio=nd.solution.expansion_ratio, anchor_throat=th.anchor_throat)
    geometry = chamber.geometry

    # generate cooling channel geometry
    cooling_geom = CoolingGeometry(geometry, chn.height.as_input(), chn.fill_factor.as_input(), chn.inner_wall.as_input(),
                                   float(chn.outer_wall), int(chn.n), chn.helix_angle.as_input() if chn.helical else 0.0)
    cooling_geom.channel_geometry()

    # generate settings class for 2D thermal sim
    cell_size = th.cell_size_factor * float(np.min(cooling_geom.t_w_i))
    time_step = cell_size**2 / material.alpha
    start_idx = {"nozzle": -1, "injector": 0}[cool.start]
    run_time = "steady_state" if th.run_time is None else float(th.run_time)
    settings = Settings2D(cell_size, time_step, th.tolerance, th.max_iter, th.save_section_figures, False, run_time, start_idx,
                          th.adaptive_up, False, 0)

    # generate output class
    output = Output1D(geometry, save_path)

    # calculate hot gas properties from NASA CEA, at the core O/F and the expansion ratio of the contour
    cea = BipropCEA(fuel, ox, op.chamber_pressure)
    cea.metric_cea_output("throat", op.of_ratio, nd.solution.expansion_ratio)

    # isentropic properties for the hot gas along the chamber contour
    gas = Isentropic(op.chamber_pressure, cea.Tc, cea.gamma, cea.Pr, geometry[:, 0], geometry[:, 1])
    gas.calculate()

    # coolant Properties from CoolProp library
    coolant = Coolant(list(cool.fluids), ws=list(cool.mass_fractions), P=cool.inlet_pressure, T=cool.inlet_temperature)

    # film cooling model, the film from the injector face is the first ring of ports
    ports = [[geometry[0, 0], budget.film_injector, d.film.injection_velocity, d.film.injector_diameter]]
    ports += [[port.x / 1000, m, port.velocity, port.diameter] for port, m in zip(d.film.ports, budget.film_ports)]
    film = FilmCooling(cea, gas, coolant, geometry, budget.total, ports)
    film.calculate()

    return SimpleNamespace(design=d, nozzle=nd, chamber=chamber, geometry=geometry, cooling_geom=cooling_geom, settings=settings,
                           output=output, cea=cea, gas=gas, coolant=coolant, film=film, material=material, save_path=save_path)


def run_thermal(setup, progress=None):
    """Runs the thermal simulation set up with build_thermal. progress(done, total, idx) is called after every section."""
    d = setup.design
    th = d.thermal
    sim = regen.HeatTransfer(
        cea=setup.cea,
        gas=setup.gas,
        geometry=setup.geometry,
        material=setup.material,
        coolant=setup.coolant,
        cooling_geometry=setup.cooling_geom,
        m_dot=setup.nozzle.budget.total,
        m_dot_coolant=setup.nozzle.budget.coolant,
        T_amb=float(th.ambient_temperature),
        output=setup.output,
        settings2D=setup.settings,
        model=th.hot_gas_method,
        cool_model=th.cooling_method,
        eta_c_star=d.operating.eta_c_star,
        film=setup.film,
        boiling=th.boiling,
        chf_model=th.chf_method,
        post_chf=th.post_chf,
    )
    sim.run(progress)
    return sim


def thermal_warnings(setup, sim):
    """Warnings of a thermal run as text: critical heat flux, bulk boiling of the coolant and channels too small to depowder."""
    notes = []
    x = setup.geometry[:, 0] * 1e3
    if sim.post_chf_sections:
        notes.append("Beyond the critical heat flux on the post-CHF branch in %d sections, x = %.1f to %.1f mm"
                     % (len(sim.post_chf_sections), x[min(sim.post_chf_sections)], x[max(sim.post_chf_sections)]))
    if sim.chf_exceeded:
        notes.append("Boiling can not carry the heat flux in %d sections, x = %.1f to %.1f mm (solved without nucleate boiling)"
                     % (len(sim.chf_exceeded), x[min(sim.chf_exceeded)], x[max(sim.chf_exceeded)]))
    if sim.bulk_boiling:
        notes.append("The coolant reaches its saturation temperature at x = %.1f mm, results downstream are not valid"
                     % x[sim.bulk_boiling[0]])
    cg = setup.cooling_geom
    min_size = setup.design.channels.min_channel_size
    width = cg.psi_c * cg.r_i
    small = np.where((width < min_size * (1 - 1e-9)) | (cg.h_c < min_size * (1 - 1e-9)))[0]
    if len(small):
        notes.append("Cooling channels smaller than %.2f mm in %d of %d sections (narrowest %.2f mm wide, lowest %.2f mm high)"
                     % (min_size * 1e3, len(small), len(x), width.min() * 1e3, cg.h_c.min() * 1e3))
    return notes
