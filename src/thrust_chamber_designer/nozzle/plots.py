"""
Plots of the Method of Characteristics nozzle, from solver_standard.py of the nozzle solver: the wall contour with the net of
characteristics, and the 3D surface of the thrust chamber. The functions return matplotlib figures which are not managed by pyplot,
so the desktop app can show them and they can be saved with fig.savefig.
"""

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from .. import plot_style

# ── Simple dark theme palette ─────────────────────────────────────────────
BG         = "#1a1e2e"   # dark navy background
SURFACE    = "#1e2235"   # slightly lighter for axes
WALL_COLOR = "#7ec8e3"   # light blue — nozzle wall
AXIS_COLOR = "#4a5070"   # muted blue-grey for grid / spines
TEXT_COLOR = "#c8cfe8"   # soft white-blue for labels
CL_COLOR   = "#5a7faa"   # centreline dash
RED        = "#e05c5c"   # family II characteristics
PURPLE     = "#8878cc"   # family I internal
TEAL       = "#4aadad"   # family I exit

STYLE = {
    "font.family":      "monospace",
    "font.size":        9,
    "text.color":       TEXT_COLOR,
    "axes.facecolor":   SURFACE,
    "figure.facecolor": BG,
    "axes.edgecolor":   AXIS_COLOR,
    "axes.labelcolor":  TEXT_COLOR,
    "xtick.color":      TEXT_COLOR,
    "ytick.color":      TEXT_COLOR,
    "grid.color":       AXIS_COLOR,
    "grid.linestyle":   "-",
    "grid.linewidth":   0.4,
    "grid.alpha":       0.4,
}


def characteristics_plot(result, show_characteristics=True, fig=None, theme="dark"):
    """Wall contour of the thrust chamber with the characteristics of the nozzle (moc.NozzleSolution). theme: 'dark' (the look of
    the nozzle solver), 'light' or 'aero' (see plot_style)"""
    import matplotlib
    WALL_COLOR, CL_COLOR, RED, PURPLE, TEAL = plot_style.NOZZLE_LINES.get(theme, plot_style.NOZZLE_LINES["dark"])
    dark = theme == "dark"
    # ── 2D Plot ───────────────────────────────────────────────────────────
    with matplotlib.rc_context(STYLE if dark else {}):
        # ── 2D figure setup ───────────────────────────────────────────────────
        fig = fig or Figure(figsize=(14, 7), layout="constrained")
        ax = fig.add_subplot()
        if dark:
            fig.set_facecolor(BG)
            ax.set_facecolor(SURFACE)
            for spine in ax.spines.values():
                spine.set_edgecolor(AXIS_COLOR)
                spine.set_linewidth(1.0)

        family_2, family_1_internal, family_1_exit = result.characteristics
        if show_characteristics:
            # ── Characteristics Family II ─────────────────────────────────────────
            for x_line, y_line in family_2:
                ax.plot(x_line, y_line, color=RED, lw=0.6, alpha=0.45, zorder=2)
            # ── Characteristics Family I ──────────────────────────────────────────
            for x_line, y_line in family_1_internal:
                ax.plot(x_line, y_line, color=PURPLE, lw=0.6, alpha=0.55, zorder=2)
            for x_line, y_line in family_1_exit:
                ax.plot(x_line, y_line, color=TEAL, lw=0.6, alpha=0.45, zorder=2)

        wall_x, wall_y = result.wall_x, result.wall_y
        ax.plot(wall_x, wall_y,  color=WALL_COLOR, lw=2.0, zorder=5)
        ax.plot(wall_x, -wall_y, color=WALL_COLOR, lw=2.0, zorder=5)

        x0 = np.array([np.min(wall_x), np.max(wall_x)])
        ax.plot(x0, np.zeros(2), color=CL_COLOR, lw=0.9, alpha=0.7,
                linestyle="-.", zorder=4)

        if dark:
            ax.set_title("Nozzle Wall Contour  +  Characteristics  —  MOC Solver",
                         color=TEXT_COLOR, fontsize=11, pad=10)
        else:
            ax.set_title("Wall contour and characteristics", fontsize=11, pad=8)
        ax.set_xlabel("X  (mm)", fontsize=9)
        ax.set_ylabel("Y  (mm)", fontsize=9)
        ax.axis("equal")
        ax.grid(True)

        legend_elements = [
            Line2D([0], [0], color=WALL_COLOR, lw=2,
                   label="Nozzle wall contour"),
        ]
        if show_characteristics:
            legend_elements += [
                Line2D([0], [0], color=RED,    lw=1, linestyle="--", alpha=0.7,
                       label="Char. Family II"),
                Line2D([0], [0], color=PURPLE, lw=1, linestyle="--", alpha=0.7,
                       label="Char. Family I (internal)"),
                Line2D([0], [0], color=TEAL,   lw=1, linestyle="--", alpha=0.7,
                       label="Char. Family I (exit)"),
            ]
        if dark:
            leg = ax.legend(
                handles=legend_elements,
                loc="lower right",
                frameon=True,
                facecolor=BG,
                edgecolor=AXIS_COLOR,
                labelcolor=TEXT_COLOR,
                fontsize=8,
            )
            leg.get_frame().set_linewidth(1.0)
        else:
            ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
            plot_style.style_figure(fig, theme)
    return fig


def surface_plot(result, fig=None):
    """3D surface of the thrust chamber (moc.NozzleSolution)."""
    import matplotlib
    # ── 3D Plot ───────────────────────────────────────────────────────────
    with matplotlib.rc_context(STYLE):
        fig = fig or Figure(figsize=(16, 8))
        fig.set_facecolor(BG)
        ax3 = fig.add_subplot(111, projection="3d")
        ax3.set_facecolor(BG)

        wall_x, wall_y = result.wall_x, result.wall_y
        theta = np.linspace(0, 2 * np.pi, 100)
        theta_grid, wall_x_grid = np.meshgrid(theta, wall_x)
        _, wall_y_grid = np.meshgrid(theta, wall_y)

        X = wall_x_grid
        Y = wall_y_grid * np.cos(theta_grid)
        Z = wall_y_grid * np.sin(theta_grid)

        blue_cmap = LinearSegmentedColormap.from_list(
            "dark_blue", ["#0d1117", "#1a2a4a", "#2a5080", "#7ec8e3"]
        )
        norm   = Normalize(wall_y.min() - 5, wall_y.max() + 5)
        colors = blue_cmap(norm(wall_y_grid))
        colors[..., 3] = 0.92

        ax3.plot_surface(X, Y, Z, facecolors=colors, linewidth=0,
                         antialiased=True, rstride=1, cstride=1)
        ax3.plot(wall_x, np.zeros_like(wall_x), wall_y,
                 color=WALL_COLOR, lw=1.8, alpha=0.95, zorder=10)

        ax3.set_xlabel("X  (mm)", color=TEXT_COLOR, labelpad=8)
        ax3.set_ylabel("Y  (mm)", color=TEXT_COLOR, labelpad=8)
        ax3.set_zlabel("Z  (mm)", color=TEXT_COLOR, labelpad=8)
        ax3.tick_params(colors=AXIS_COLOR, labelsize=7)

        for pane in (ax3.xaxis.pane, ax3.yaxis.pane, ax3.zaxis.pane):
            pane.fill = True
            pane.set_facecolor(SURFACE)
            pane.set_edgecolor(AXIS_COLOR)

        ax3.set_title("Nozzle Geometry  —  3D Surface  —  MOC Solver",
                      color=TEXT_COLOR, fontsize=11, pad=14)

        x_range = wall_x.max() - wall_x.min()
        y_range = Y.max() - Y.min()
        z_range = Z.max() - Z.min()
        ax3.set_xlim(wall_x.min(), wall_x.max())
        ax3.set_ylim(Y.min(), Y.max())
        ax3.set_zlim(Z.min(), Z.max())
        ax3.set_box_aspect((x_range, y_range, z_range))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    return fig
