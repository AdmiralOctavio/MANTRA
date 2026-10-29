"""
Command line runs of a design file, for scripting and parameter sweeps without the desktop app.

    tcd new my_engine.json                 write a design file with the default inputs
    tcd nozzle my_engine.json -o out       nozzle only: params.csv, Contour.csv, Contour.dxf and plots
    tcd nozzle my_engine.json --step       also Cooling_Jacket.step: inner wall, outer wall, ribs and channels for CAD
    tcd nozzle my_engine.json --step jacket   the same with inner wall, outer wall and ribs as one solid
    tcd run my_engine.json -o out          nozzle and thermal simulation
"""

import argparse
import os
import sys
import time


def _nozzle(design, out, stl, step):
    import matplotlib
    matplotlib.use("Agg")
    from . import pipeline
    from .nozzle import plots

    nd = pipeline.design_nozzle(design)
    pipeline.write_nozzle_outputs(nd, out, dxf=True, stl=stl)
    if step:
        t0 = time.time()
        path, notes = pipeline.write_step(nd, out, separate=step == "parts")
        print("Wrote %s in %.0f s" % (path, time.time() - t0))
        for note in notes:
            print("NOTE:", note)
    plots.characteristics_plot(nd.solution).savefig(os.path.join(out, "nozzle_characteristics.png"), dpi=200)
    # Standard Terminal Output
    for category, name, value, unit in pipeline.nozzle_summary(nd):
        if category == "Output":
            print("%-34s %14s %s" % (name, "%.5g" % value if isinstance(value, float) else value, unit))
    for note in nd.warnings:
        print("WARNING:", note)
    return nd


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tcd", description="Thrust Chamber Designer")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new", help="write a design file with the default inputs")
    p_new.add_argument("design")
    for name, text in (("nozzle", "design the nozzle"), ("run", "design the nozzle and run the thermal simulation")):
        p = sub.add_parser(name, help=text)
        p.add_argument("design", help="design file (.json)")
        p.add_argument("-o", "--output", default=None, help="output folder, default: <design name>_results next to the file")
        p.add_argument("--stl", action="store_true", help="also write an STL of the inner wall")
        p.add_argument("--step", nargs="?", const="parts", choices=("parts", "jacket"),
                       help="also write a STEP model of the wall and the coolant: inner wall, outer wall, ribs and channels as parts "
                            "(default), or 'jacket' for the wall as one solid and the channels")
    args = parser.parse_args(argv)

    from .core.design import Design

    if args.command == "new":
        Design().save(args.design)
        print("Wrote", args.design)
        return 0

    design = Design.load(args.design)
    out = args.output or os.path.splitext(args.design)[0] + "_results"
    os.makedirs(out, exist_ok=True)
    nd = _nozzle(design, out, args.stl, args.step)
    if args.command == "nozzle":
        return 0

    from . import pipeline
    from .thermal.plots import Plotting1D
    from .thermal.stress import summary

    t0 = time.time()
    setup = pipeline.build_thermal(nd, out)
    print("\nThermal simulation of %d sections" % len(setup.geometry))
    sim = pipeline.run_thermal(setup)
    th = design.thermal
    plot = Plotting1D(save_path=out, geometry=setup.geometry, cooling_geom=setup.cooling_geom, boiling=th.boiling,
                      post_chf=th.post_chf, save=True, show=False)
    for name in ("temperature_plot", "pressure_plot", "heat_transfer_coeff_plot", "heat_flux_plot", "reynolds_plot", "chf_plot",
                 "wall_delta_plot", "stress_plot", "bree_plot"):
        getattr(plot, name)()
    plot.section_3d_plot(include_plotlyjs=True)
    summary(setup.output, setup.material, th.ambient_temperature)
    for note in pipeline.thermal_warnings(setup, sim):
        print("WARNING:", note)
    print("Thermal simulation took %.0f s, results in %s" % (time.time() - t0, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
