import os

import numpy as np
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QPushButton, QSlider, QSplitter, QTabWidget, QVBoxLayout, QWidget)

from types import SimpleNamespace

from .. import plot_style
from ..thermal.plots import Plotting1D
from .widgets import PlotCanvas, fill_table, summary_table

PLOTS = [("Temperature", "temperature_plot"), ("Heat flux", "heat_flux_plot"), ("Critical heat flux", "chf_plot"),
         ("Heat transfer coeff.", "heat_transfer_coeff_plot"), ("Coolant pressure", "pressure_plot"), ("Reynolds", "reynolds_plot"),
         ("Wall temperature differences", "wall_delta_plot"), ("Stress", "stress_plot"), ("Bree diagram", "bree_plot")]


class ResultsTab(QWidget):
    """Results of the thermal simulation from its folder: summary and warnings, the plots of PyRocket, the 2D sections and the 3D
    view."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.folder_label = QLabel("No results yet. Run the thermal simulation, or open a results folder (File menu).")
        self.folder_label.setWordWrap(True)
        open_folder = QPushButton("Open folder")
        open_folder.clicked.connect(lambda: self.folder and QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder)))
        top.addWidget(self.folder_label, 1)
        top.addWidget(open_folder)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        summary = QSplitter(Qt.Orientation.Vertical)
        self.summary = summary_table([])
        self.warnings = QListWidget()
        summary.addWidget(self.summary)
        summary.addWidget(self.warnings)
        summary.setSizes([400, 200])
        self.tabs.addTab(summary, "Summary")

        self.canvases = {}
        for title, name in PLOTS:
            canvas = PlotCanvas()
            self.canvases[name] = canvas
            self.tabs.addTab(canvas, title)

        sections = QWidget()
        s_layout = QVBoxLayout(sections)
        row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self.draw_section)
        self.section_label = QLabel("")
        row.addWidget(QLabel("Section"))
        row.addWidget(self.slider, 1)
        row.addWidget(self.section_label)
        s_layout.addLayout(row)
        self.section_canvas = PlotCanvas()
        s_layout.addWidget(self.section_canvas, 1)
        self.tabs.addTab(sections, "Sections")

        # the 3D view of the sections is a plotly page. It is shown in an embedded browser (QtWebEngine) only on request, which keeps
        # the start of the app fast and works without QtWebEngine
        self.view3d_box = QWidget()
        self.v_layout = QVBoxLayout(self.view3d_box)
        row = QHBoxLayout()
        open3d = QPushButton("Open in the web browser")
        open3d.clicked.connect(self.open_3d)
        self.show3d = QPushButton("Show here")
        self.show3d.clicked.connect(self.show_3d)
        row.addWidget(open3d)
        row.addWidget(self.show3d)
        row.addStretch(1)
        self.v_layout.addLayout(row)
        self.note3d = QLabel("Sections joined along the chamber, coloured by temperature, with the wall transparent so the channels show.")
        self.note3d.setWordWrap(True)
        self.v_layout.addWidget(self.note3d)
        self.v_layout.addStretch(1)
        self.view3d = None
        self.tabs.addTab(self.view3d_box, "3D")

        self.folder = None
        self.fields = None
        self.geometry = None

    def load(self, folder, geometry, warnings, design):
        """Shows the results in folder. geometry: dict with the contour of the thermal model (from the run)."""
        self.folder = folder
        self.geometry = geometry
        self.loaded = (folder, geometry, warnings, design)
        self.theme3d = None                  # theme of sections_3d.html, made again in the theme of the app when it is shown
        self.folder_label.setText("Results in " + folder)
        contour = geometry["contour"]
        th = design.thermal
        plot = Plotting1D(save_path=folder, geometry=contour, boiling=th.boiling, post_chf=th.post_chf, save=False, show=False)
        self.warnings.clear()
        self.warnings.addItems(warnings or ["No warnings"])
        for name, canvas in self.canvases.items():
            try:
                fig = getattr(plot, name)()
            except Exception as e:
                fig = None
                self.warnings.addItem("%s could not be drawn: %s" % (name, e))
            if fig is not None:
                canvas.set_figure(fig)
            else:
                canvas.clear()
        self._summary(plot.data, contour)

        path = os.path.join(folder, "section_fields.npz")
        self.fields = np.load(path) if os.path.exists(path) else None
        n = len(contour)
        self.slider.setRange(0, n - 1)
        self.slider.setValue(int(np.argmin(contour[:, 1])))
        self.draw_section()

        if self.view3d is not None:
            self.show_3d()

    def _summary(self, data, contour):
        x = contour[:, 0] * 1e3
        rows = []

        def at(col, fn=np.nanargmax):
            i = int(fn(data[:, col]))
            return data[i, col], x[i]

        T, xi = at(6)
        rows.append(("Highest inner wall temperature (hot gas side)", "%.0f K at x = %.1f mm" % (T, xi), ""))
        if data.shape[1] > 12 and np.any(np.isfinite(data[:, 12])):
            T, xi = at(12)
            rows.append(("Highest coolant side wall temperature", "%.0f K at x = %.1f mm" % (T, xi), ""))
        start, end = (-1, 0) if data[0, 7] > data[-1, 7] else (0, -1)
        rows.append(("Coolant temperature in / out", "%.1f / %.1f K" % (data[start, 7], data[end, 7]), ""))
        rows.append(("Coolant pressure drop", data[start, 8] / 1e5 - data[end, 8] / 1e5, "bar"))
        rows.append(("Highest coolant velocity", np.nanmax(data[:, 10]), "m/s"))
        q, xi = at(5)
        rows.append(("Highest heat flux", "%.2f MW/m^2 at x = %.1f mm" % (q / 1e6, xi), ""))
        col = 31 if data.shape[1] > 31 else 14
        ratio = data[:, col] / data[:, 15]
        if np.any(np.isfinite(ratio)):
            i = int(np.nanargmax(ratio))
            rows.append(("Highest heat flux / critical heat flux", "%.2f at x = %.1f mm" % (ratio[i], x[i]), ""))
        if data.shape[1] > 28 and np.any(np.isfinite(data[:, 28])):
            i = int(np.nanargmax(data[:, 28]))
            rows.append(("Highest Bree Y (secondary stress / yield)", "%.2f at x = %.1f mm" % (data[i, 28], x[i]), ""))
        rows.append(("Sections", len(x), ""))
        fill_table(self.summary, rows)

    def draw_section(self, *_):
        if self.geometry is None:
            return
        i = self.slider.value()
        x = self.geometry["contour"][i, 0] * 1e3
        self.section_label.setText("%d, x = %.1f mm" % (i, x))
        fig = self.section_canvas.clear()
        ax = fig.add_subplot()
        if self.fields is None or "T%d" % i not in self.fields:
            ax.text(0.5, 0.5, "No temperature field for this section", ha="center", transform=ax.transAxes)
            self.section_canvas.draw()
            return
        vx, vy = self.fields["x%d" % i] * 1e3, self.fields["y%d" % i] * 1e3
        tri, T = self.fields["tri%d" % i], self.fields["T%d" % i]
        # the half section and its mirror image: one cooling channel between two half ribs
        levels = np.linspace(T.min(), T.max(), 40)
        for sign in (1, -1):
            cs = ax.tricontourf(sign * vx, vy, tri, T, levels=levels, cmap=self._cmap())
        fig.colorbar(cs, ax=ax, label="Temperature [K]")
        ax.set_aspect("equal")
        ax.set_xlabel("mm")
        ax.set_ylabel("radius [mm]")
        beta = np.degrees(self.geometry["beta"][i])
        ax.set_title("Section at x = %.1f mm, T max %.0f K%s" % (x, T.max(), (", helix %.0f deg" % beta) if beta > 0 else ""))
        self.section_canvas.draw()

    def _cmap(self):
        from . import themes
        return plot_style.palette(themes.plot_theme())["section_cmap"]

    def reload(self):
        # the plots again in the look of the current theme
        if getattr(self, "loaded", None) is not None:
            self.load(*self.loaded)

    def _make_3d(self):
        # the 3D view in the look of the theme of the app, made from the section fields of the run
        from . import themes
        theme = themes.plot_theme()
        if self.theme3d == theme or self.geometry is None:
            return
        g = self.geometry
        cg = SimpleNamespace(**{k: g[k] for k in ("beta", "psi_c", "psi_w", "h_c", "t_w_i", "t_w_o", "twist", "n_channels")})
        try:
            Plotting1D(save_path=self.folder, geometry=g["contour"], cooling_geom=cg, save=False).section_3d_plot(include_plotlyjs=True,
                                                                                                                 theme=theme)
            self.theme3d = theme
        except Exception as e:
            self.note3d.setText("The 3D view could not be made: %s" % e)

    def show_3d(self):
        self._make_3d()
        html = os.path.join(self.folder, "sections_3d.html") if self.folder else None
        if html is None or not os.path.exists(html):
            self.note3d.setText("No 3D view in the results folder.")
            return
        if self.view3d is None:
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
            except Exception:
                self.note3d.setText("Showing the 3D view here needs QtWebEngine. Open it in the web browser instead.")
                return
            self.view3d = QWebEngineView()
            self.v_layout.takeAt(self.v_layout.count() - 1)        # the stretch
            self.v_layout.addWidget(self.view3d, 1)
        self.view3d.setUrl(QUrl.fromLocalFile(html))

    def open_3d(self):
        self._make_3d()
        if self.folder:
            html = os.path.join(self.folder, "sections_3d.html")
            if os.path.exists(html):
                QDesktopServices.openUrl(QUrl.fromLocalFile(html))
