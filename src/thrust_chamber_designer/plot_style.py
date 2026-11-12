"""
Looks of the plots, to match the theme of the app: 'light' (matplotlib as it is), 'dark' (the palette of the nozzle solver) and 'aero'
(white to pale sky blue plot areas, soft blue frames and grid, glossy blue / green / coral lines, after Windows Vista / 7) and 'lcars'
(black screens, lavender frames, peach lettering and orange / periwinkle lines, after the consoles of a 24th century starship).

style_figure() restyles a finished figure, so the plots of PyRocket keep their code: the basic colours they use ('b', 'r', 'g', 'k')
are swapped for the colours of the theme.
"""

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgba

THEMES = ("light", "dark", "aero", "lcars")

# temperature colours of the aero theme: deep blue through aqua and green to amber and red, without a white band in the middle that
# would look like the empty cooling channel
AERO_HEAT = ["#1d3f8f", "#1f7fc8", "#35b6c6", "#6cc98a", "#d9e36a", "#f5b04a", "#e4573c", "#b3203a"]

# temperature colours of the lcars theme: from deep space blue through lavender and lilac to the orange and gold of the consoles
LCARS_HEAT = ["#1b1b4d", "#3d3d99", "#7a6fcc", "#cc99cc", "#ff9966", "#ff9900", "#ffcc66", "#fff2cc"]

# cells of the throttle map, from the favourable to the unfavourable end of a quantity: one hue per theme, so that the four panels
# of the map read as shades and not as alarms
MAP_COLORS = {
    "light": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
    "dark": ["#232842", "#2c4a7c", "#3f7fb5", "#7ec8e3", "#e3f6fd"],
    "aero": ["#f7fcff", "#cfe9fb", "#8ccbf2", "#3d9be9", "#0f5fa8", "#0b3a6b"],
    "lcars": ["#14142e", "#33337a", "#7070b8", "#cc99cc", "#ff9966", "#ff9900"],
}

PALETTES = {
    "dark": {
        "figure": "#1a1e2e", "axes": "#1e2235", "text": "#c8cfe8", "frame": "#4a5070", "grid": "#4a5070", "legend": "#1a1e2e",
        "colors": {"b": "#7ec8e3", "r": "#e05c5c", "g": "#6fcf97", "k": "#c8cfe8", "orange": "#f0a35e"},
        "section_cmap": "magma", "plotly_scale": "Magma",
        "map_outline": "#f0a35e", "empty": "#4a5070",
        "jacket": {"background": ("#1e2235", "#141726"), "wall": "#c98a5b", "coolant": "#7ec8e3", "ink": "#c8cfe8", "accent": "#f0a35e",
                   "glass": 0.16, "gloss": 0.5, "shadow": 0.0},
    },
    "aero": {
        "figure": "#f5faff", "axes": "#ffffff", "text": "#123a5e", "frame": "#8fb7da", "grid": "#bcd8ee", "legend": "#ffffff",
        # plot area: white at the top fading into pale sky blue, with a hint of green at the bottom
        "gradient": ["#ffffff", "#f1f8fe", "#e2f1fb", "#e4f4ec"],
        "colors": {"b": "#1f8ad6", "r": "#e2583e", "g": "#3aaa4f", "k": "#2a4a68", "orange": "#f29d38"},
        "section_cmap": LinearSegmentedColormap.from_list("aero_heat", AERO_HEAT),
        "plotly_scale": [[i / (len(AERO_HEAT) - 1), c] for i, c in enumerate(AERO_HEAT)],
        "map_outline": "#f2801c", "empty": "#8fb7da",
        # glossy copper under blue glass, on the sky of the plots
        "jacket": {"background": ("#ffffff", "#e2f1fb", "#e4f4ec"), "wall": "#e39a62", "coolant": "#1f9ae0", "ink": "#123a5e",
                   "accent": "#3aaa4f", "glass": 0.2, "gloss": 1.0, "shadow": 0.22},
    },
    "lcars": {
        # black screens with lavender frames and peach lettering; the default colours of matplotlib (C0 to C3) are swapped as well
        "figure": "#000000", "axes": "#000000", "text": "#ff9966", "frame": "#9999cc", "grid": "#26263d", "legend": "#000000",
        "colors": {"b": "#9999ff", "r": "#ff5555", "g": "#66cc99", "k": "#ffcc99", "orange": "#ff9900",
                   "C0": "#9999ff", "C1": "#ff9900", "C2": "#66cc99", "C3": "#ff5555"},
        "fonts": ("Antonio", "Bahnschrift"),
        # colours of the bars of the Isp chart on the Engine tab, from far off the peak to the peak, and of its line
        "score_cmap": LinearSegmentedColormap.from_list("lcars_score", ["#26265c", "#5c5cad", "#9999cc", "#cc99cc", "#ff9966", "#ff9900"]),
        "ink": "#ffcc99",
        "section_cmap": LinearSegmentedColormap.from_list("lcars_heat", LCARS_HEAT),
        "plotly_scale": [[i / (len(LCARS_HEAT) - 1), c] for i, c in enumerate(LCARS_HEAT)],
        "map_outline": "#ffffff", "empty": "#9999cc",
        # a display of light on the black of the console: peach wall, periwinkle coolant, edges that glow
        "jacket": {"background": ("#000000", "#000000"), "wall": "#ff9966", "coolant": "#99ccff", "ink": "#ff9966", "accent": "#ff9900",
                   "glass": 0.12, "gloss": 0.35, "shadow": 0.0, "edges": 0.9},
    },
    "light": {"section_cmap": "magma", "plotly_scale": "Magma", "map_outline": "#e8590c", "empty": "#8a93a3", "text": "#1d2330",
              "jacket": {"background": ("#ffffff", "#eef1f5"), "wall": "#c98a5b", "coolant": "#3d9fd8", "ink": "#1d2330", "accent": "#e8590c",
                         "glass": 0.18, "gloss": 0.6, "shadow": 0.16}},
}
for _name, _colors in MAP_COLORS.items():
    PALETTES[_name]["map_cmap"] = LinearSegmentedColormap.from_list(_name + "_map", _colors)

# line colours of the nozzle plot: wall, centre line, family II, family I inside the nozzle, family I through the exit
NOZZLE_LINES = {
    "dark": ("#7ec8e3", "#5a7faa", "#e05c5c", "#8878cc", "#4aadad"),
    "aero": ("#0f6cbd", "#7aa7cc", "#ef7b5a", "#8f7fd6", "#2fb3a1"),
    "lcars": ("#ff9900", "#9999cc", "#cc6666", "#cc99cc", "#99ccff"),
    "light": ("#1f4e79", "#7f7f7f", "#d62728", "#9467bd", "#17becf"),
}


def palette(theme):
    return PALETTES.get(theme, PALETTES["light"])


def _same(c1, c2):
    try:
        return np.allclose(to_rgba(c1), to_rgba(c2))
    except ValueError:
        return False


_font_cache = {}


def _font(names):
    """First of the fonts installed for matplotlib, None if none is (matplotlib would warn on every text otherwise)"""
    if names not in _font_cache:
        from matplotlib import font_manager
        installed = {f.name for f in font_manager.fontManager.ttflist}
        _font_cache[names] = next((name for name in names if name in installed), None)
    return _font_cache[names]


def _recolor(color, colors):
    for basic, new in colors.items():
        if _same(color, basic):
            return new
    return None


def style_figure(fig, theme):
    """Gives a finished matplotlib figure the look of the theme. Can be called more than once."""
    p = PALETTES.get(theme)
    if p is None or "figure" not in p:
        # the light theme is matplotlib as it is. A figure that was cleared keeps its background, so one left dark by another theme
        # gets its white back
        fig.patch.set_facecolor("white")
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
        plain = getattr(ax, "_tcd_plain", False)   # heatmaps: the cells are the plot, no gradient or grid over them
        if not colorbar and not twin:
            ax.set_facecolor(p["axes"])
        if not colorbar and not twin and not plain:
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
        if not getattr(text, "_tcd_keep", False):          # the line of an empty plot keeps its faint colour
            text.set_color(p["text"])
    family = _font(p["fonts"]) if "fonts" in p else None
    if family is not None:
        from matplotlib.text import Text
        # DejaVu Sans for the glyphs the font lacks, e.g. the minus sign. Mathtext ($10^{-3}$ on log axes) takes no fallback, so it
        # keeps the font of matplotlib
        families = [family, "DejaVu Sans"]
        for text in fig.findobj(Text):
            if "$" not in text.get_text():
                text.set_fontfamily(families)
        for ax in fig.axes:
            for axis in ("x", "y"):
                if getattr(ax, "get_%sscale" % axis)() != "linear":
                    continue
                try:
                    ax.tick_params(axis=axis, labelfontfamily=families)    # also the ticks made later when zooming (matplotlib 3.8)
                except (TypeError, ValueError):
                    pass
    return fig


def placeholder(fig, text, theme):
    """An empty figure in the look of the theme, with a line of text in its middle: what a plot shows until there is something to plot"""
    p = palette(theme)
    fig.clear()
    line = fig.text(0.5, 0.5, text.upper() if theme == "lcars" else text, ha="center", va="center", fontsize=11,
                    color=p.get("empty", "#8a93a3"))
    line._tcd_keep = True
    return style_figure(fig, theme)


def luminance(color):
    """Perceived brightness of a colour, 0 (black) to 1 (white): tells if text on it should be dark or light"""
    r, g, b = to_rgba(color)[:3]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def plotly_layout(theme):
    """Colours of the plotly 3D view for the theme: (template, paper colour, scene colour, grid colour, font colour)."""
    if theme == "aero":
        return "plotly_white", "#f2f9ff", "#f2f9ff", "#c5def0", "#123a5e"
    if theme == "light":
        return "plotly_white", "#ffffff", "#ffffff", "#dddddd", "#222222"
    if theme == "lcars":
        return "plotly_dark", "#000000", "#000000", "#33334d", "#ff9966"
    return "plotly_dark", None, None, None, None
