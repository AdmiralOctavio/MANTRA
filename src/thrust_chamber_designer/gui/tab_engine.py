from functools import lru_cache

import numpy as np
from matplotlib import cm
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..core import chemistry
from ..core import propellants as props
from .widgets import PlotCanvas
from .worker import run_in_thread


@lru_cache(maxsize=64)
def _of_sweep(oxidiser, fuel, concentration, pc, pa):
    # arguments are the cache key
    return chemistry.mixture_ratio_sweep(props.fuel_blend(fuel, concentration), props.oxidiser_blend(oxidiser), pc, pa)


class EngineTab(QWidget):
    """Propellants and operating point, with the Isp over O/F of the propellants for the choice of the O/F."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        b = window.bindings
        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        box = QGroupBox("Design")
        form = QFormLayout(box)
        self.name = b.text(lambda d: d, "name")
        form.addRow("Name", self.name)
        left.addWidget(box)

        box = QGroupBox("Propellants")
        form = QFormLayout(box)
        self.oxidiser = b.choice(lambda d: d.propellants, "oxidiser", [(k, v.name) for k, v in props.OXIDISERS.items()])
        self.fuel = b.choice(lambda d: d.propellants, "fuel", [(k, v.name) for k, v in props.FUELS.items()])
        self.concentration = b.number(lambda d: d.propellants, "fuel_concentration", decimals=1, minimum=50, maximum=100, step=1,
                                      suffix="wt%", tooltip="Fuel in a fuel-water blend, balance water")
        form.addRow("Oxidiser", self.oxidiser)
        form.addRow("Fuel", self.fuel)
        form.addRow("Fuel concentration", self.concentration)
        left.addWidget(box)

        box = QGroupBox("Operating point")
        form = QFormLayout(box)
        op = lambda d: d.operating
        form.addRow("Chamber pressure", b.number(op, "chamber_pressure", scale=1e5, decimals=2, minimum=1, maximum=500, step=1, suffix="bar"))
        form.addRow("Ambient pressure", b.number(op, "ambient_pressure", scale=1e5, decimals=4, minimum=0.0001, maximum=10, step=0.1, suffix="bar"))
        self.of_ratio = b.number(op, "of_ratio", decimals=3, minimum=0.1, maximum=50, step=0.1,
                                 tooltip="O/F of the combustion. Film coolant is extra fuel on top of this, see the mass flows of the nozzle")
        form.addRow("O/F (core)", self.of_ratio)
        form.addRow("Thrust", b.number(op, "thrust", decimals=1, minimum=1, maximum=1e7, step=10, suffix="N"))
        form.addRow("c* efficiency", b.number(op, "eta_c_star", scale=0.01, decimals=1, minimum=1, maximum=100, step=0.5, suffix="%"))
        form.addRow("Nozzle efficiency", b.number(op, "eta_nozzle", scale=0.01, decimals=1, minimum=1, maximum=100, step=0.5, suffix="%"))
        left.addWidget(box)

        box = QGroupBox("Film cooling")
        form = QFormLayout(box)
        form.addRow("Injector film", b.number(lambda d: d.film, "injector_fraction", scale=0.01, decimals=1, minimum=0, maximum=99,
                                              step=1, suffix="% of fuel feed",
                                              tooltip="Film from the injector face. It is fuel on top of the core O/F and does not change the "
                                                      "nozzle, only the split of the mass flow. Velocity, diameter and rings of ports in the "
                                                      "wall are on the Cooling tab"))
        self.feed = QLabel("")
        self.feed.setWordWrap(True)
        form.addRow("", self.feed)
        left.addWidget(box)
        left.addStretch(1)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        box = QGroupBox("Ideal Isp over O/F (CEA, expanded to ambient pressure)")
        inner = QVBoxLayout(box)
        self.chart = PlotCanvas(toolbar=False, figsize=(5, 3))
        self.caption = QLabel("")
        self.caption.setWordWrap(True)
        inner.addWidget(self.chart, 1)
        inner.addWidget(self.caption)
        right.addWidget(box, 1)
        layout.addLayout(right, 3)

        self.timer = QTimer(self, singleShot=True, interval=400)
        self.timer.timeout.connect(self.update_chart)
        self.request = None

    def refresh(self):
        fuel = props.FUELS[self.window.design.propellants.fuel]
        self.concentration.setEnabled(fuel.water_blend)
        d = self.window.design
        f = d.film.total_fraction
        ports = sum(port.fraction for port in d.film.ports)
        self.feed.setText("Film %.1f %% of the fuel feed in total%s, feed O/F %.3f (core O/F %.3f)"
                          % (f * 100, " (%.1f %% from rings of ports)" % (ports * 100) if ports else "", d.operating.of_ratio * (1 - f),
                             d.operating.of_ratio))
        self.timer.start()

    def update_chart(self):
        d = self.window.design
        key = (d.propellants.oxidiser, d.propellants.fuel, float(d.propellants.fuel_concentration), float(d.operating.chamber_pressure),
               float(d.operating.ambient_pressure))
        self.request = key
        run_in_thread(_of_sweep, *key, on_finished=lambda result, key=key: self._draw(key, result),
                      on_failed=lambda text: self.caption.setText("CEA failed for these propellants:\n" + text.splitlines()[-1]))

    def _draw(self, key, result):
        if key != self.request:
            return
        # Mini Isp-vs-O/F chart: green at the Isp peak, fading to red 10% below it.
        of, isp, of_stoich = result
        of_val = self.window.design.operating.of_ratio
        fig = self.chart.clear()
        ax = fig.add_subplot()
        ok = np.isfinite(isp)
        if not ok.any():
            self.caption.setText("CEA did not converge for these propellants")
            self.chart.draw()
            return
        i_peak = int(np.nanargmax(isp))
        score = np.clip(1 - (isp[i_peak] - isp) / (0.2 * isp[i_peak]), 0, 1)
        base = np.nanmin(isp) - 0.05 * (isp[i_peak] - np.nanmin(isp))
        ink = "#5a5a5a"
        ax.bar(of[ok], isp[ok] - base, bottom=base, width=of[1] - of[0], color=cm.YlGnBu_r(score[ok]), linewidth=0, alpha=0.7)
        ax.plot(of, isp, color=ink, linewidth=0.8)
        ax.plot(of[i_peak], isp[i_peak], "v", color="#1a9850", markersize=6, markeredgecolor=ink, markeredgewidth=0.4)
        in_range = of[0] <= of_val <= of[-1]
        if in_range:
            # White over black so the marker shows on every colour band
            ax.axvline(of_val, color="black", linewidth=2.0)
            ax.axvline(of_val, color="white", linewidth=1.0)
        ax.axvline(of_stoich, color=ink, linewidth=0.6, linestyle=":")
        ax.set_xlim(of[0], of[-1])
        ax.set_ylim(base, isp[i_peak] + 0.12 * (isp[i_peak] - base))
        ax.set_xlabel("O/F (core)")
        ax.set_ylabel("Isp (s)")
        for side, spine in ax.spines.items():
            spine.set_visible(side in ("left", "bottom"))
        self.chart.draw()
        text = f"Peak Isp {isp[i_peak]:.1f} s at O/F {of[i_peak]:.2f}, stoichiometric O/F {of_stoich:.2f} (dotted)"
        if in_range:
            isp_now = float(np.interp(of_val, of, isp))
            text += (f"\nSelected O/F {of_val:.2f}: {isp_now:.1f} s "
                     f"({100 * (isp_now / isp[i_peak] - 1):+.1f}%)")
        else:
            text += f"\nSelected O/F {of_val:.2f} is off the chart"
        self.caption.setText(text)
