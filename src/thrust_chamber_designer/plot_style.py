"""
Looks of the plots, to match the theme of the app: 'light' (matplotlib as it is), 'dark' (the palette of the nozzle solver) and 'aero'
(white to pale sky blue plot areas, soft blue frames and grid, glossy blue / green / coral lines, after Windows Vista / 7).

style_figure() restyles a finished figure, so the plots of PyRocket keep their code: the basic colours they use ('b', 'r', 'g', 'k')
are swapped for the colours of the theme.
"""

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgba

THEMES = ("light", "dark", "aero")

# temperature colours of the aero theme: deep blue through aqua and green to amber and red, without a white band in the middle that
# would look like the empty cooling channel
AERO_HEAT = ["#1d3f8f", "#1f7fc8", "#35b6c6", "#6cc98a", "#d9e36a", "#f5b04a", "#e4573c", "#b3203a"]

PALETTES = {
    "dark": {
        "figure": "#1a1e2e", "axes": "#1e2235", "text": "#c8cfe8", "frame": "#4a5070", "grid": "#4a5070", "legend": "#1a1e2e",
        "colors": {"b": "#7ec8e3", "r": "#e05c5c", "g": "#6fcf97", "k": "#c8cfe8", "orange": "#f0a35e"},
        "section_cmap": "magma", "plotly_scale": "Magma",
    },
    "aero": {
        "figure": "#f5faff", "axes": "#ffffff", "text": "#123a5e", "frame": "#8fb7da", "grid": "#bcd8ee", "legend": "#ffffff",
        # plot area: white at the top fading into pale sky blue, with a hint of green at the bottom
        "gradient": ["#ffffff", "#f1f8fe", "#e2f1fb", "#e4f4ec"],
        "colors": {"b": "#1f8ad6", "r": "#e2583e", "g": "#3aaa4f", "k": "#2a4a68", "orange": "#f29d38"},
        "section_cmap": LinearSegmentedColormap.from_list("aero_heat", AERO_HEAT),
        "plotly_scale": [[i / (len(AERO_HEAT) - 1), c] for i, c in enumerate(AERO_HEAT)],
    },
    "light": {"section_cmap": "magma", "plotly_scale": "Magma"},
}

# line colours of the nozzle plot: wall, centre line, family II, family I inside the nozzle, family I through the exit
NOZZLE_LINES = {
    "dark": ("#7ec8e3", "#5a7faa", "#e05c5c", "#8878cc", "#4aadad"),
    "aero": ("#0f6cbd", "#7aa7cc", "#ef7b5a", "#8f7fd6", "#2fb3a1"),
    "light": ("#1f4e79", "#7f7f7f", "#d62728", "#9467bd", "#17becf"),
}


def palette(theme):
    return PALETTES.get(theme, PALETTES["light"])


def _same(c1, c2):
    try:
        return np.allclose(to_rgba(c1), to_rgba(c2))
    except ValueError:
        return False


def _recolor(color, colors):
    for basic, new in colors.items():
        if _same(color, basic):
            return new
    return None


def style_figure(fig, theme):
    """Gives a finished matplotlib figure the look of the theme. Can be called more than once."""
    p = PALETTES.get(theme)
    if p is None or "figure" not in p:
        return fig
    fig.patch.set_facecolor(p["figure"])
    for ax in list(fig.axes):
        if getattr(ax, "name", "") == "3d":
            ax.set_facecolor(p["figure"])
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.set_facecolor(p["axes"])
                pane.set_edgecolor(p["frame"])
            ax.tick_params(colors=p["text"])
            for label in (ax.xaxis.label, ax.yaxis.label, ax.zaxis.label, ax.title):
                label.set_color(p["text"])
            continue
        colorbar = hasattr(ax, "_colorbar")
        twin = not ax.patch.get_visible()          # twinx axes lie over another one, their background stays clear
        if not colorbar and not twin:
            ax.set_facecolor(p["axes"])
            if "gradient" in p and not getattr(ax, "_tcd_background", False):
                bg = ax.inset_axes([0, 0, 1, 1], zorder=-10)
                bg.imshow(np.linspace(0, 1, 256)[:, None], aspect="auto", extent=(0, 1, 0, 1), origin="upper",
                          cmap=LinearSegmentedColormap.from_list("aero", p["gradient"]), interpolation="bicubic")
                bg.set_axis_off()
                bg.set_navigate(False)
                ax._tcd_background = True
            ax.grid(True, color=p["grid"], linewidth=0.6, alpha=0.8)
            ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_edgecolor(p["frame"])
        ax.tick_params(colors=p["text"], which="both")
        for label in (ax.xaxis.label, ax.yaxis.label, ax.title):
            label.set_color(p["text"])
        for line in ax.get_lines():
            for get, set_ in ((line.get_color, line.set_color), (line.get_markerfacecolor, line.set_markerfacecolor),
                              (line.get_markeredgecolor, line.set_markeredgecolor)):
                new = _recolor(get(), p["colors"])
                if new is not None:
                    set_(new)
        legend = ax.get_legend()
        if legend is not None:
            frame = legend.get_frame()
            frame.set_facecolor(p["legend"])
            frame.set_edgecolor(p["frame"])
            frame.set_alpha(0.9)
            for text in legend.get_texts():
                text.set_color(p["text"])
            for handle in getattr(legend, "legend_handles", getattr(legend, "legendHandles", [])):
                if hasattr(handle, "get_color"):
                    new = _recolor(handle.get_color(), p["colors"])
                    if new is not None:
                        handle.set_color(new)
    for text in fig.texts:
        text.set_color(p["text"])
    return fig


def plotly_layout(theme):
    """Colours of the plotly 3D view for the theme: (template, paper colour, scene colour, grid colour, font colour)."""
    if theme == "aero":
        return "plotly_white", "#f2f9ff", "#f2f9ff", "#c5def0", "#123a5e"
    if theme == "light":
        return "plotly_white", "#ffffff", "#ffffff", "#dddddd", "#222222"
    return "plotly_dark", None, None, None, None
