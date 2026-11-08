#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3			                #	 
#                                                                   #
#####################################################################

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np

from .stress import REGIMES, bree_regime
from ..plot_style import palette, plotly_layout

class Plotting1D():
    def __init__(self, save_path, geometry, cooling_geom=None, boiling=True, post_chf='fallback', save=True, show=False):
        # geometry: chamber contour [x, y] in m, cooling_geom: CoolingGeometry (only needed for the 3D plot), boiling and post_chf: settings
        # of the run. Every plot returns its figure, which the desktop app shows. Figures are only made with pyplot when they are shown
        self.save_path = save_path
        self.geometry = geometry
        self.cooling_geom = cooling_geom
        self.boiling = boiling
        self.post_chf = post_chf
        self.save = save
        self.show = show
        self.data = np.genfromtxt(save_path+'/sim_data.csv', delimiter=",", skip_header=1)
        # column of the heat flux which is compared with the critical heat flux: mean at the channel bottom, or the highest local value in older files
        self.q_chf_check = 31 if self.data.shape[1] > 31 else 14


    def new_figure(self, **kwargs):
        # pyplot figure if it is shown in a window, otherwise a figure which is not managed by pyplot, for saving or for the desktop app
        return plt.figure(**kwargs) if self.show else Figure(**kwargs)

    def finish(self, fig, name, dpi=600):
        if self.save:
            fig.savefig(self.save_path + '/' + name, dpi=dpi)

        if self.show:
            plt.show()
        return fig


    @staticmethod
    def shade(ax, x, sections, label=None, **kwargs):
        # shades the sections (indices) along x, each from half way to its neighbours, so that sections of different lengths (finer steps at
        # the throat) neither overlap nor leave gaps; neighbouring sections are joined to one span
        edges    = np.concatenate([[x[0] - (x[1] - x[0]) / 2], (x[1:] + x[:-1]) / 2, [x[-1] + (x[-1] - x[-2]) / 2]])
        sections = sorted(int(i) for i in sections)
        for k, i in enumerate(sections):
            if k == 0 or sections[k - 1] != i - 1:
                start = i
            if k + 1 == len(sections) or sections[k + 1] != i + 1:
                ax.axvspan(edges[start], edges[i + 1], linewidth=0, label=label, **kwargs)
                label = None


    def temperature_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,7]-273.15, color='b', label='Coolant bulk temperature')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,6]-273.15, color='r', linestyle='--', label='Inner wall temperature')
        if self.boiling and self.data.shape[1] > 12:
            ax.plot(self.geometry[:,0]*1e3, self.data[:,12]-273.15, color='g', linestyle='-.', label='Cooling channel wall temperature')
            ax.plot(self.geometry[:,0]*1e3, self.data[:,13]-273.15, color='k', linestyle=':', label='Coolant saturation temperature')
            # sections above the critical heat flux are solved without nucleate boiling, the wall temperatures there are not a prediction
            x   = self.geometry[:,0]*1e3
            if self.data.shape[1] > 32:
                # state of each section beyond the CHF: post-CHF branch or solved again without boiling
                post = np.where(self.data[:,32] == 1)[0]
                chf  = np.where(self.data[:,32] == 2)[0]
            else:
                post = []
                chf  = np.where((self.data[:,self.q_chf_check] > self.data[:,15]) & (self.data[:,12] > self.data[:,13]))[0]
            self.shade(ax, x, post, 'Beyond CHF, post-CHF boiling branch', color='orange', alpha=0.15)
            self.shade(ax, x, chf, 'Boiling limit exceeded, solved without boiling', color='r', alpha=0.15)
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel(r'Temperature [$^\circ$C]')
        ax.legend(loc='best')

        return self.finish(fig, 'temperature', dpi=600)
        

    def pressure_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,8]/1e5, color='b', label='Coolant pressure')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Pressure [bar]')
        ax.legend(loc='best')

        return self.finish(fig, 'pressure', dpi=600)
        

    def heat_transfer_coeff_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,2], color='b', label='$h_{alpha}$ gas')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,3], color='r', linestyle='--',  label='$h_{alpha}$ coolant')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Heat transfer coefficient [W/m^2/K]')
        ax.legend(loc='best')
        
        return self.finish(fig, 'halpha', dpi=600)
    

    def heat_flux_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,4]/1e6, color='b', label='q radiation')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,5]/1e6, color='r', linestyle='--', label='q total')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Heat flux [MW/m^2]')
        ax.legend(loc='best')
        
        return self.finish(fig, 'heat_flux', dpi=600)
    

    def chf_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,self.q_chf_check]/1e6, color='b', label='Mean heat flux at the channel bottom' if self.q_chf_check == 31 else 'Highest heat flux at the channel wall')
        if self.q_chf_check == 31:
            ax.plot(self.geometry[:,0]*1e3, self.data[:,14]/1e6, color='b', linestyle=':', linewidth=0.8, label='Highest local heat flux (channel corner, mesh dependent)')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,15]/1e6, color='r', linestyle='--', label='Critical heat flux')
        if self.post_chf == 'meyer':
            ax.plot(self.geometry[:,0]*1e3, self.data[:,15]/1e6 * 1.55, color='g', linestyle='--', label='Second excursion of the post-CHF branch, 1.55x CHF')
        else:
            ax.plot(self.geometry[:,0]*1e3, self.data[:,15]/1e6 * 1.5, color='g', linestyle='--', label='1.5x Critical heat flux')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Heat flux [MW/m^2]')
        ax.legend(loc='best')

        return self.finish(fig, 'chf', dpi=600)


    def wall_delta_plot(self):
        # temperature differences in the wall which drive the thermal stresses
        fig = self.new_figure()
        ax  = fig.add_subplot()
        if self.data.shape[1] <= 19:
            return

        ax.plot(self.geometry[:,0]*1e3, self.data[:,16], color='r', label='Through the inner wall (channel centre line)')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,17]-self.data[:,19], color='b', linestyle='--', label='Inner wall mean - outer wall mean')
        ax.plot(self.geometry[:,0]*1e3, self.data[:,18]-self.data[:,19], color='g', linestyle='-.', label='Rib mean - outer wall mean')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Temperature difference [K]')
        ax.legend(loc='upper left')

        return self.finish(fig, 'wall_delta_T', dpi=600)


    def stress_plot(self):
        # elastic wall stresses of the stress analysis compared to the yield strength at wall temperature
        fig = self.new_figure()
        ax  = fig.add_subplot()
        if self.data.shape[1] <= 29 or np.all(np.isnan(self.data[:,26])):
            return

        x = self.geometry[:,0]*1e3
        ax.plot(x, self.data[:,26]/1e6, color='k', label='Yield strength at wall temperature')
        ax.plot(x, self.data[:,25]/1e6, color='r', linestyle='--', label='Secondary stress (temperature), hot gas side')
        ax.plot(x, self.data[:,22]/1e6, color='orange', linestyle=':', label='of which temperature gradient through the inner wall')
        ax.plot(x, (self.data[:,20]+self.data[:,21])/1e6, color='b', linestyle='-.', label='Primary stress (pressure)')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Stress [MPa]')
        ax.set_ylim(0, 1.45 * np.nanmax(self.data[:,[25, 26]]) / 1e6)      # room for the legend above the curves
        ax.legend(loc='upper left')

        return self.finish(fig, 'stress', dpi=600)


    def bree_plot(self):
        # Bree diagram with one point for every section of the chamber, and the same data along the chamber contour
        if self.data.shape[1] <= 29 or np.all(np.isnan(self.data[:,27])):
            return

        x      = self.geometry[:,0]*1e3
        X, Y   = self.data[:,27], self.data[:,28]
        regime = [bree_regime(X[i], Y[i]) for i in range(len(x))]
        Y_max  = max(4.5, 1.15 * np.nanmax(Y))

        fig = self.new_figure(figsize=(13, 5.5))
        ax1, ax2 = fig.subplots(1, 2)

        # boundaries between the regimes
        hyperbola = np.linspace(1 / Y_max, 0.5, 100)
        ax1.plot([0, 1], [1, 0], color='k', linewidth=1)
        ax1.plot([0, 0.5], [2, 2], color='k', linewidth=1)
        ax1.plot([0.5, 1], [2, 0], color='k', linewidth=1)
        ax1.plot(hyperbola, 1 / hyperbola, color='k', linewidth=1)
        ax1.plot([1, 1], [0, Y_max], color='k', linewidth=1)
        ax1.text(0.45, 0.22, 'E\nelastic', ha='center', va='center', color='dimgray')
        ax1.text(0.5, 1.25, 'S\nshakedown', ha='center', va='center', color='dimgray')
        ax1.text(0.12, 2.0 + 0.3 * (Y_max - 2), 'P\nplastic\ncycling', ha='center', va='center', color='dimgray')
        ax1.text(0.72, 2.0 + 0.3 * (Y_max - 2), 'R\nratcheting', ha='center', va='center', color='dimgray')

        # sections of the chamber, connected in the order of the x coordinate
        ax1.plot(X, Y, color='gray', linewidth=0.8, zorder=2)
        points = ax1.scatter(X, Y, c=x, cmap='viridis', s=28, edgecolors='w', linewidths=0.5, zorder=3)
        fig.colorbar(points, ax=ax1, label='x coordinate [mm]')
        for i, name in ((0, 'injector'), (int(np.argmin(self.geometry[:,1])), 'throat'), (len(x) - 1, 'exit')):
            ax1.annotate(name, (X[i], Y[i]), xytext=(40, 6), textcoords='offset points', fontsize=9, arrowprops=dict(arrowstyle='-', color='gray', linewidth=0.8))
        ax1.set_xlim(0, 1.1)
        ax1.set_ylim(0, Y_max)
        ax1.set_xlabel('X = primary stress / yield strength')
        ax1.set_ylabel('Y = secondary stress / yield strength')
        ax1.set_title('Bree diagram')

        # X and Y along the chamber contour, the background shows the regime of every section
        for key, color in (('E', 'g'), ('S', 'b'), ('P', 'orange'), ('R', 'r'), ('C', 'k')):
            self.shade(ax2, x, [i for i in range(len(x)) if regime[i] == key], key + ': ' + REGIMES[key], color=color, alpha=0.15)
        ax2.plot(x, Y, color='r', label='Y (secondary stress)')
        ax2.plot(x, X, color='b', linestyle='--', label='X (primary stress)')
        ax2.set_ylim(bottom=0)
        ax2.set_xlabel('x coordinate [mm]')
        ax2.set_ylabel('Stress / yield strength')
        ax2.set_title('Along the chamber')
        ax2.legend(loc='best')

        fig.tight_layout()

        return self.finish(fig, 'bree', dpi=300)


    def creep_plot(self):
        # creep rupture screening: reference stress of the primary stresses against the rupture stress for the total firing time, and
        # the life fraction along the chamber, shaded where the rupture life is extrapolated beyond the stresses of the data
        if self.data.shape[1] <= 37 or np.all(np.isnan(self.data[:,35])):
            return

        x    = self.geometry[:,0]*1e3
        D    = np.clip(np.nan_to_num(self.data[:,36], nan=0.0, posinf=1e6), 1e-12, 1e6)
        flag = self.data[:,37]

        fig = self.new_figure(figsize=(13, 5.5))
        ax1, ax2 = fig.subplots(1, 2)

        ax1.plot(x, self.data[:,34]/1e6, color='k', label='Creep rupture stress for the total firing time')
        ax1.plot(x, self.data[:,33]/1e6, color='b', linestyle='-.', label='Reference stress (pressure)')
        ax1.set_ylim(0, 1.3 * np.nanmax(self.data[:,[33, 34]]) / 1e6)
        ax1.set_xlabel('x coordinate [mm]')
        ax1.set_ylabel('Stress [MPa]')
        ax1.set_title('Stresses at the hot gas side wall temperature')
        ax1.legend(loc='upper left')

        for key, color, text in ((1, 'g', 'longer than tested (extrapolated)'), (2, 'r', 'shorter than tested (extrapolated)')):
            self.shade(ax2, x, [i for i in range(len(x)) if flag[i] == key], 'Rupture life ' + text, color=color, alpha=0.12)
        ax2.semilogy(x, D, color='r', label='Life fraction (firing time / rupture time)')
        ax2.axhline(1, color='k', linewidth=1, label='Creep rupture')
        ax2.axhline(0.1, color='k', linewidth=1, linestyle=':', label='Life fraction 0.1')
        ax2.set_ylim(0.1 * np.min(D), max(10, 10 * np.max(D)))
        if np.min(D) <= 1e-12:
            ax2.text(0.98, 0.5, 'Life fractions below 1e-12 are drawn at 1e-12', transform=ax2.transAxes, ha='right', va='center',
                     fontsize=9, color='dimgray')
        ax2.set_xlabel('x coordinate [mm]')
        ax2.set_ylabel('Life fraction [-]')
        ax2.set_title('Creep rupture along the chamber')
        ax2.legend(loc='best')

        fig.tight_layout()

        return self.finish(fig, 'creep', dpi=300)


    def life_plot(self):
        # thermal ratcheting and cyclic life: firings to failure of the ligament (Porowski) and firings to 1 % creep ratchet strain of the
        # elastic core (O'Donnell-Porowski) along the chamber, and the plastic strain per firing with the core stress parameter
        if self.data.shape[1] <= 49 or np.all(np.isnan(self.data[:,47])):
            return

        x     = self.geometry[:,0]*1e3
        top   = 1e7
        clip  = lambda a: np.clip(np.nan_to_num(a, nan=top, posinf=top), 1, top)
        # number of firings of the run: firings to the strain limit times the strain of all firings / limit
        n_run = self.data[:,40] * self.data[:,41] / 0.01
        n_run = n_run[np.isfinite(n_run) & (n_run > 0)]

        fig = self.new_figure(figsize=(13, 5.5))
        ax1, ax2 = fig.subplots(1, 2)

        self.shade(ax1, x, [i for i in range(len(x)) if self.data[i,49] > 0 or self.data[i,42] > 0], 'Data extrapolated', color='orange', alpha=0.12)
        if self.data.shape[1] > 52:
            ax1.fill_between(x, clip(self.data[:,51]), clip(self.data[:,47]), color='r', alpha=0.08, linewidth=0)
            ax1.semilogy(x, clip(self.data[:,51]), color='darkred', linewidth=1.2, label='Ligament failure, start-up bound (closeout still cold)')
        ax1.semilogy(x, clip(self.data[:,47]), color='r', label='Ligament failure (Porowski, steady state)')
        ax1.semilogy(x, clip(self.data[:,45]), color='r', linestyle='--', linewidth=0.8, label='Tensile instability of the thinned ligament')
        ax1.semilogy(x, clip(self.data[:,46]), color='r', linestyle=':', linewidth=0.8, label='Fatigue and creep rupture')
        ax1.semilogy(x, clip(self.data[:,41]), color='b', linestyle='-.', label='1 % creep ratchet strain of the core (O\'Donnell-Porowski)')
        if len(n_run):
            ax1.axhline(np.round(np.median(n_run)), color='k', linewidth=1, label='Firings of the run')
        ax1.set_ylim(1, 10 * top)
        ax1.text(0.98, 0.97, 'Lives above 1e7 firings are drawn at 1e7', transform=ax1.transAxes, ha='right', va='top', fontsize=9, color='dimgray')
        ax1.set_xlabel('x coordinate [mm]')
        ax1.set_ylabel('Firings')
        ax1.set_title('Firings to failure')
        ax1.legend(loc='lower left', fontsize=8)

        ax2.plot(x, self.data[:,43]*100, color='r', label='Plastic hoop strain per firing (Porowski, steady state)')
        if self.data.shape[1] > 52:
            ax2.plot(x, self.data[:,50]*100, color='darkred', linestyle='--', label='Plastic hoop strain per firing, start-up bound')
        ax2.set_xlabel('x coordinate [mm]')
        ax2.set_ylabel('Strain per firing [%]')
        ax2.set_ylim(bottom=0)
        ax3 = ax2.twinx()
        ax3.plot(x, self.data[:,38], color='b', linestyle='-.', label='Core stress parameter Z')
        ax3.axhline(1, color='b', linewidth=0.8, linestyle=':', label='Z = 1: plastic ratcheting')
        ax3.set_ylim(0, max(1.2, 1.1 * np.nanmax(self.data[:,38])))
        ax3.set_ylabel('Z = core stress / yield strength')
        lines = ax2.get_legend_handles_labels()
        lines3 = ax3.get_legend_handles_labels()
        ax2.legend(lines[0] + lines3[0], lines[1] + lines3[1], loc='upper left', fontsize=8)
        ax2.set_title('Ratcheting per firing')

        fig.tight_layout()

        return self.finish(fig, 'life', dpi=300)


    def reynolds_plot(self):
        fig = self.new_figure()
        ax  = fig.add_subplot()
        ax.plot(self.geometry[:,0]*1e3, self.data[:,9], color='b', label='Coolant Re')
        ax.set_xlabel('x coordinate [mm]')
        ax.set_ylabel('Re')
        ax.legend(loc='best')

        return self.finish(fig, 'reynolds', dpi=600)
        

    def section_3d_plot(self, channels=None, opacity=0.35, samples=12, include_plotlyjs='cdn', theme='dark'):
        # include_plotlyjs: 'cdn' loads plotly.js from the internet, True writes it into the html file, which then also works offline
        # theme: 'dark' as in PyRocket, 'light', 'aero' or 'lcars' to match the desktop app (see plot_style.py)
        # channels: number of cooling channels shown, by default all channels of the chamber, which closes the ring
        # 3D view of the 2D sections joined along the chamber contour: a slice of the wall with a number of cooling channels and their ribs,
        # coloured by temperature. The wall is transparent so that the cooling channels can be seen through it. Interactive html file, which
        # opens in a web browser (needs an internet connection for plotly.js)
        try:
            import plotly.graph_objects as go
        except ImportError:
            print('The 3D plot of the sections needs plotly: pip install plotly')
            return
        from matplotlib.tri import LinearTriInterpolator, Triangulation

        try:
            data = np.load(self.save_path + '/section_fields.npz')
        except FileNotFoundError:
            print('No section fields found in ' + self.save_path + ', the 3D plot needs a run of the full chamber')
            return

        geom, cg = self.geometry, self.cooling_geom
        n_sec = np.broadcast_to(np.asarray(cg.n_channels, dtype=int), (len(geom[:,0]),))   # results of older runs have one number
        sections = [i for i in range(len(geom[:,0])) if 'T' + str(i) in data]
        s = np.linspace(0, 1, samples)

        def field(i):
            return data['x' + str(i)].astype(float), data['y' + str(i)].astype(float), data['tri' + str(i)], data['T' + str(i)].astype(float)

        def section_plane(px, py, i):
            # the 2D sections of helical channels are perpendicular to the channels, in the cross section of the chamber they are wider by
            # 1 / cos(beta) around the chamber axis. No change for axial channels
            r, th = np.hypot(px, py), np.arctan2(px, py) / np.cos(cg.beta[i])
            return r * np.sin(th), r * np.cos(th)

        def boundary(i):
            # points along the walls of half a section in its plane [m], as radius and angle from the centre line of the cooling channel
            r_c  = geom[i,1]
            r_ci = r_c + cg.t_w_i[i]
            r_co = r_ci + cg.h_c[i]
            r_o  = r_co + cg.t_w_o[i]
            th_c = cg.psi_c[i] / 2
            th_p = (cg.psi_c[i] + cg.psi_w[i]) / 2
            walls = {'gas': (np.full_like(s, r_c), th_p * s), 'outer': (np.full_like(s, r_o), th_p * s), 'side': (r_c + (r_o - r_c) * s, np.full_like(s, th_p)),
                     'channel top': (np.full_like(s, r_co), th_c * s), 'channel side': (r_co + (r_ci - r_co) * s, np.full_like(s, th_c)),
                     'channel bottom': (np.full_like(s, r_ci), th_c * s)}
            x, y, tri, T = field(i)
            interp = LinearTriInterpolator(Triangulation(x, y, tri), T)
            out = {}
            for wall, (r, th) in walls.items():
                px, py = r * np.sin(th), r * np.cos(th)
                Tw = interp(px, py)
                # points on the arcs can lie just outside the straight mesh edges: nearest vertex there
                nearest = np.argmin((x[:,None] - px[None,:])**2 + (y[:,None] - py[None,:])**2, axis=0)
                out[wall] = (*section_plane(px, py, i), np.where(np.ma.getmaskarray(Tw), T[nearest], np.ma.filled(Tw, 0.0)))
            return out, th_p / np.cos(cg.beta[i])

        def place(px, py, z, angle):
            # point in the plane of a section to 3D [mm]: axial coordinate along x, around the chamber axis by angle, radius upwards
            return z * np.ones_like(px), 1e3 * (px * np.cos(angle) + py * np.sin(angle)), 1e3 * (py * np.cos(angle) - px * np.sin(angle))

        meshes = {'wall': [], 'channel': []}
        def add(group, X, Y, Z, T, tri):
            meshes[group].append((X, Y, Z, T, tri))

        walls = dict(zip(sections, (boundary(i) for i in sections)))
        # the sections in runs with the same number of channels, each drawn on its own: where the channels split, the run ends and the
        # next one starts with the other number of channels
        runs = np.split(np.array(sections), np.flatnonzero(np.diff(n_sec[sections])) + 1)
        for run in runs:
            n_run = int(n_sec[run[0]])
            shown = n_run if channels is None else min(int(channels), n_run)
            ring = shown == n_run                         # all channels: the slice closes around the axis and has no cut faces
            # copies of the half section: mirrored about the centre line of the channel and rotated by whole channel pitches. Helical
            # channels are rotated further by their angular position around the chamber axis
            ks = np.arange(shown) - (shown - 1) / 2
            halves = [(k, m) for k in ks for m in (1, -1)]
            z = geom[run, 0] * 1e3
            for name in ('gas', 'outer', 'side', 'channel top', 'channel side', 'channel bottom'):
                group = 'channel' if name.startswith('channel') else 'wall'
                for k, m in halves:
                    if name == 'side' and (ring or k * m != ks.max()):
                        continue                          # rib centre planes between the copies are inside the slice
                    X, Y, Z, T = [], [], [], []
                    for zi, i in zip(z, run):
                        w, th_p = walls[i]
                        px, py, Tw = w[name]
                        x3, y3, z3 = place(m * px, py, zi, 2 * k * th_p + cg.twist[i])
                        X.append(x3); Y.append(y3); Z.append(z3); T.append(Tw)
                    X, Y, Z, T = (np.concatenate(a) for a in (X, Y, Z, T))
                    # two triangles between neighbouring points of neighbouring sections
                    a = np.arange(len(run) - 1)[:,None] * samples + np.arange(samples - 1)[None,:]
                    a = a.ravel()
                    tri = np.vstack([np.column_stack([a, a + samples, a + samples + 1]), np.column_stack([a, a + samples + 1, a + 1])])
                    add(group, X, Y, Z, T, tri)

            # the first and the last section close the slice
            for i in sorted({run[0], run[-1]}):
                x, y, tri, T = field(i)
                x, y = section_plane(x, y, i)
                th_p = np.pi / n_run
                for k, m in halves:
                    X, Y, Z = place(m * x, y, geom[i,0] * 1e3, 2 * k * th_p + cg.twist[i])
                    add('wall', X, Y, Z, T, tri)
        counts = sorted({int(n) if channels is None else min(int(channels), int(n)) for n in n_sec[sections]})

        T_all = np.concatenate([part[3] for group in meshes.values() for part in group])
        template, paper, scene, grid, font = plotly_layout(theme)
        fig = go.Figure()
        for group, alpha in (('channel', 1.0), ('wall', opacity)):
            parts, n, X, Y, Z, T, tris = meshes[group], 0, [], [], [], [], []
            for x3, y3, z3, Tp, tri in parts:
                X.append(x3); Y.append(y3); Z.append(z3); T.append(Tp); tris.append(tri + n); n += len(x3)
            X, Y, Z, T, tri = (np.concatenate(a) for a in (X, Y, Z, T, tris))
            fig.add_trace(go.Mesh3d(x=X, y=Y, z=Z, i=tri[:,0], j=tri[:,1], k=tri[:,2], intensity=T, coloraxis='coloraxis', opacity=alpha,
                                    flatshading=False, name='cooling channels' if group == 'channel' else 'wall',
                                    hovertemplate='x = %{x:.1f} mm<br>T = %{intensity:.0f} K<extra>%{fullData.name}</extra>'))

        fig.update_layout(title='Wall temperature along the chamber, ' + ' to '.join(str(n) for n in (counts[0], counts[-1])[:len(counts)])
                                + (' helical' if np.any(cg.beta > 0) else '') + ' cooling channels',
                          coloraxis=dict(colorscale=palette(theme)['plotly_scale'], cmin=float(T_all.min()), cmax=float(T_all.max()), colorbar=dict(title='Temperature [K]')),
                          scene=dict(xaxis_title='x coordinate [mm]', yaxis_title='[mm]', zaxis_title='radius [mm]', aspectmode='data',
                                     camera=dict(eye=dict(x=0.55, y=-2.3, z=-1.25), center=dict(x=0, y=0, z=0), projection=dict(type='perspective'))),
                          template=template, margin=dict(l=0, r=0, t=40, b=0))
        if paper is not None:
            axis = dict(gridcolor=grid, zerolinecolor=grid, backgroundcolor=scene, showbackground=True, color=font)
            fig.update_layout(paper_bgcolor=paper, font=dict(color=font),
                              scene=dict(bgcolor=scene, xaxis=axis, yaxis=axis, zaxis=axis))
        fig.write_html(self.save_path + '/sections_3d.html', include_plotlyjs=include_plotlyjs, default_width='100%', default_height='96vh')
        if self.show:
            fig.show()
        return fig


def multi_plot(x, data1, data2, data3, data4, label1, label2, label3, label4):
    # x: axial coordinate of the chamber contour [m]
    f, axes = plt.subplots(4, 1)
    #f.subplots_adjust(hspace = 0)

    axes[0].plot(x, data1)
    axes[0].set_ylabel(label1)

    axes[1].plot(x, data2)
    axes[1].set_ylabel(label2)

    axes[2].plot(x, data3)
    axes[2].set_ylabel(label3)

    axes[3].plot(x, data4)
    axes[3].set_ylabel(label4)

    plt.xlabel('x coordinate [m]')
    plt.show()


if __name__ == "__main__":
    from .example_config import build
    config = build()
    plot = Plotting1D(save_path=config.save_path, geometry=config.geometry, cooling_geom=config.cooling_geom, boiling=config.boiling,
                      post_chf=config.post_chf, save=True, show=True)
    plot.temperature_plot()
    plot.pressure_plot()
    plot.heat_transfer_coeff_plot()
    plot.heat_flux_plot()
    plot.reynolds_plot()
    plot.chf_plot()
    plot.wall_delta_plot()
    plot.stress_plot()
    plot.bree_plot()
    plot.creep_plot()
    plot.life_plot()
    plot.section_3d_plot()
