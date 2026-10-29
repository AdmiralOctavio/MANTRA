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

import os
import numpy as np
from matplotlib import pyplot as plt

from .output import red_bold
from .stress import x_ranges


GROWTH = 1.2                                                        # largest ratio of neighbouring steps of a graded contour


def graded_stations(x_min, x_max, x_t, fine, coarse, zone, growth=GROWTH):
    # x of the sections [m] from x_min up to (not including) x_max, like the uniform grid: one at the throat x_t, the step fine within
    # zone of it, growing by the factor growth per section beyond, up to coarse
    sides = []
    for direction, limit in ((-1, x_min), (1, x_max)):
        pos, h, side = x_t, fine, []
        while True:
            if abs(pos - x_t) >= zone - 1e-12:
                h = min(h * growth, coarse)
            pos += direction * h
            if (direction < 0 and pos < limit - 1e-12) or (direction > 0 and pos > limit - 1e-12):
                break
            side.append(pos)
        sides.append(side)
    return np.array(sides[0][::-1] + [x_t] + sides[1])


class ChamberGeometry():
    """[Summary]
    Class to calculate the combustion chamber geometry based on a Rao nozzle. 
    Only full nozzle geometries are currently implemented (no truncated nozzles). 
    Contour can be polttend and saved (recommended).
    """
    def __init__(self, D_c, D_t, D_e, L_cyl, r_1, r_2, r_n, phi_conv, phi_div, phi_e, step_size=0.001):
        self.D_c = D_c                                              # chamber diameter [m]
        self.D_t = D_t                                              # throat diameter [m]
        self.D_e = D_e                                              # exit diamter [m]
        self.L_cyl = L_cyl                                          # cylindircal chamber length [m]
        self.r_1 = r_1                                              # converging section inlet radius [m]
        self.r_2 = r_2                                              # beginning of throat radius  [m]
        self.r_n = r_n                                              # end of throat radius [m]
        self.phi_conv = phi_conv * np.pi / 180                      # convergence angle [deg]    
        self.phi_div = phi_div * np.pi / 180                        # divergence angle [deg]
        self.phi_e = phi_e * np.pi / 180                            # exit angle of parabolic nozzle
        self.expansion_ratio = D_e**2 / D_t**2                      # expansion ratio (Ae/At)
        self.dx = step_size                                         # step size for the discretisation [-]

    @classmethod
    def from_contour(cls, x, y, step_size=0.001, expansion_ratio=None, anchor_throat=False, throat_step=None, throat_zone=0.0):
        # chamber geometry from a contour given as arrays of x and radius [m], e.g. the nozzle of the Method of Characteristics solver,
        # instead of the Rao parameters or the Contour.csv file. The expansion ratio is taken from the contour unless it is given.
        # throat_step: smaller step [m] within throat_zone [m] of the throat, growing to step_size away from it (see contour())
        chamber = cls.__new__(cls)
        chamber.dx = step_size                                      # step size for the discretisation [-]
        chamber.anchor_throat = anchor_throat                       # one section exactly at the throat, see contour()
        chamber.throat_step = throat_step if throat_step and throat_step < step_size else None
        chamber.throat_zone = throat_zone
        chamber.contour_input = (np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        if expansion_ratio is None:
            expansion_ratio = (chamber.contour_input[1][np.argmax(chamber.contour_input[0])] / np.min(chamber.contour_input[1]))**2
        chamber.expansion_ratio = expansion_ratio                   # expansion ratio (Ae/At)
        chamber.contour()
        return chamber

    def contour(self):
        # generate chamber countour x, y coordiantes
        
        # Cylindrical section
        '''
        x_cyl = np.arange(0, self.L_cyl, self.dx)
        y_cyl = np.ones(len(x_cyl)) * self.D_c / 2

        # Converging section radius (at least 3 points)
        n1 = max([round(self.r_1 * self.phi_conv / self.dx), 3])     # number of discretisations in the radius
        t = np.linspace(0, self.phi_conv, n1, endpoint=True)
        
        # x and y coordinates of the converging section radius
        L_r1 = self.r_1 * np.sin(self.phi_conv)
        x_B = self.L_cyl + self.r_1 * np.sin(t)
        y_B = (self.D_c / 2 - self.r_1) + self.r_1 * np.cos(t)
        

        # x and y coordinates of linear converging section
        L_con = ((self.D_c / 2 - self.r_1 + self.r_1 * np.cos(self.phi_conv)) - (self.D_t / 2 + self.r_2 - self.r_2 * np.cos(-self.phi_conv))) / np.tan(self.phi_conv)
        x_C = np.arange((self.L_cyl + L_r1 + self.dx), (self.L_cyl + L_r1 + L_con), self.dx)
        y_C = (self.D_c / 2 - self.r_1 + self.r_1 * np.cos(self.phi_conv)) - np.tan(self.phi_conv) * np.arange(self.dx, L_con, self.dx)


        # Converging radius up to throat (at least 3 points)
        n2 = max([round(self.r_2 * self.phi_conv / self.dx), 3])      # number of discretisations in the radius
        t = np.linspace(- self.phi_conv, 0, n2, endpoint=False)

        # x and y coordiantes of converging radius
        L_r21 = self.r_2 * np.sin(self.phi_conv)
        x_D = self.L_cyl + L_r1 + L_con + L_r21 + self.r_2 * np.sin(t)
        y_D = self.D_t / 2 + self.r_2 - self.r_2 * np.cos(t)


        # Throat radius (at least 3 points)
        n3  = max([round(self.r_n * self.phi_div / self.dx), 3])      # number of discretisations in the radius
        t = np.linspace(0, self.phi_div, n3, endpoint=True)

        # x and y coordiantes of throat radius
        L_r22 = self.r_n * np.sin(self.phi_div)
        x_E = self.L_cyl + L_r1 + L_con + L_r21 + self.r_n * np.sin(t)
        y_E = self.D_t / 2 + self.r_n - self.r_n * np.cos(t)

        # parabolic RAO nozzle, starting from end of radius
        P1x = x_E[-1]
        P1y = y_E[-1]
        # remove repeat points
        x_E = x_E[:-1]
        y_E = y_E[:-1]

        # parabola factors 
        a2  = (np.tan(self.phi_e)**(-1) - np.tan(self.phi_div)**(-1)*self.D_e*0.5 / P1y) * (1 - self.D_e*0.5 / P1y)**(-1)
        a1  = (np.tan(self.phi_div)**(-1) - a2) / (2 * P1y)
        a3  = P1x - a1 * P1y**2 - a2 * P1y
        P2x = a1 * (self.D_e*0.5)**2 + a2 * (self.D_e*0.5) + a3

        # number of points along exit parabola (at least 3)
        n4 = max(round((P2x - P1x)/self.dx), 3)
        
        y_F = np.linspace(P1y, self.D_e/2, n4, endpoint=True)
        x_F = a1 * y_F**2 + a2 * y_F + a3
 
        self.x = np.concatenate((x_cyl, x_B, x_C, x_D, x_E, x_F), axis=0)
        self.y = np.concatenate((y_cyl, y_B, y_C, y_D, y_E, y_F), axis=0)

        # create 2 dimensional array containing all coordinates
        xy = [[self.x[i], self.y[i]] for i in range(len(self.x))]
        self.geometry = np.vstack(xy)
        plt.plot(self.x, self.y)
        plt.axis('equal')
        plt.show()
        '''
        
        # This is meant to be able to import external CSV chamber contours
        # the contour file next to this file, whatever folder the program is started from
        if getattr(self, 'contour_input', None) is not None:
            # contour passed in directly with from_contour, already in meters
            x, y = self.contour_input
        else:
            xy = np.genfromtxt(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Contour.csv'), delimiter = ',')
            xy = xy / 1000  # convert to meters

            x = xy[:,0]
            y = xy[:,1]

        # Clean and sort
        valid = np.isfinite(x) & np.isfinite(y)
        x = x[valid]
        y = y[valid]

        order = np.argsort(x)
        x = x[order]
        y = y[order]

        # Resample to uniform spacing dx
        if getattr(self, 'throat_step', None):
            # finer near the throat: throat_step within throat_zone of the throat, then growing by GROWTH per section up to dx. Always
            # with a section at the throat
            x_uniform = graded_stations(x.min(), x.max(), x[np.argmin(y)], self.throat_step, self.dx, self.throat_zone)
        elif getattr(self, 'anchor_throat', False):
            # grid through the throat (smallest radius), so that one section lies exactly at the throat. Starting the grid at the
            # first point of the contour generally misses the throat by up to dx/2, which makes the throat area of the thermal model
            # larger than that of the contour
            x_t = x[np.argmin(y)]
            x_uniform = x_t + self.dx * np.arange(np.ceil((x.min() - x_t) / self.dx - 1e-9), np.ceil((x.max() - x_t) / self.dx - 1e-9))
        else:
            x_uniform = np.arange(x.min(), x.max(), self.dx)
        y_uniform = np.interp(x_uniform, x, y)

        self.x = x_uniform
        self.y = y_uniform
        self.geometry = np.vstack([self.x, self.y]).T


    def plot_contour(self, path=False):
        plt.plot(self.x*1e3, self.y*1e3, color='b')
        plt.plot(self.x*1e3, -self.y*1e3, color='b')
        plt.xlabel('x_coordinate [mm]')
        plt.ylabel('y_coordinate [mm]')
        plt.title('Chamber Contour')
        plt.axis('equal')
        plt.grid()
        if path != False:
            plt.savefig(path + '/chamber_contour.png', dpi=400)
            plt.close()
        else:
            plt.show()



class CoolingGeometry():
    """[Summary]
    Class to calculate the cooling channel shapes along the chamber contour. Currently limited to rectangular channels.
    The input parameters 'h_c', 'psi', 't_w_i' and 'helix_angle' can be input as functions of the axial chamber coordinate.
    The channels are straight and axial for a helix angle of 0, otherwise they wind around the chamber axis at the helix angle [deg],
    measured from the axial direction at the centre of the channel. The 2D sections are then cross sections perpendicular to the channels:
    'psi' is the same in both, but channels and ribs are narrower by cos(helix angle) than along the circumference of the chamber.
    The location of thermocouples can be set to log the temperature of the 2D thermal sim at certain chamber locations.
    This is meant for program validation purposes and can be disabled in config.py.
    """
    def __init__(self, chamber_geometry, h_c, psi, t_w_i, t_w_o, n_channels, helix_angle=0.0):
        self.geom       = chamber_geometry                                 # points along the chamber contour [x,y]
        self.n_channels = n_channels                                       # number of cooling channels
        
        # some inputs can be functions of x coordinates 
        if type(h_c) == float:
            # check if input is a single float
            self.h_c = np.ones(len(self.geom[:,1])) * h_c               # height of the cooling channels [m]
        elif callable(h_c):
            # check if h_c is a function pointer
            self.h_c = h_c(self.geom[:,0])                              # height of cooling channel as function of x 
        else: 
            raise ValueError('h_c must be a float or a function of x coordinate')
        
        if type(psi) == float:
            # check if phi is a single float
            self.psi = np.ones(len(self.geom[:,1])) * psi                # ratio of coverage of the cooling channels to solid wall
        elif callable(psi):
            # check if psi is a function pointer
            self.psi = psi(self.geom[:,0])                               # psi as a fucntion of chamber length if it is indeed  a fucntion
        else: 
            raise ValueError('psi must be a float or a function of x coordinate')

        if type(t_w_i) == float:
            # check if inner wall thickness is a single float
            self.t_w_i = np.ones(len(self.geom[:,1])) * t_w_i              #  inner chamber wall thickness [m]  
        elif callable(t_w_i):
            # check if psi is a function pointer
            self.t_w_i = t_w_i(self.geom[:,0])                               # t_w_i as a fucntion of chamber length if it is indeed  a fucntion
        else: 
            raise ValueError('t_w_i must be a float or a function of x coordinate')
        
        self.t_w_o = np.ones(len(self.geom[:,1])) * t_w_o              # outer chamber wall thickness [m]

        if isinstance(helix_angle, (int, float)):
            # check if the helix angle is a single number
            self.beta = np.ones(len(self.geom[:,1])) * np.radians(helix_angle)        # helix angle of the cooling channels [rad], 0 for axial channels
        elif callable(helix_angle):
            # check if the helix angle is a function pointer
            self.beta = np.radians(helix_angle(self.geom[:,0])) * np.ones(len(self.geom[:,1]))
        else:
            raise ValueError('helix_angle must be a float or a function of x coordinate')

        if np.any(self.beta < 0) or np.any(self.beta >= np.pi / 2):
            raise ValueError('helix_angle must be at least 0 and below 90 degrees')

        # angular sections of the 2D section mesh, which is the cross section perpendicular to the channels: narrower by cos(beta) for helical channels
        self.psi_c = 2 * np.pi * self.psi / n_channels * np.cos(self.beta)             # radial section of single cooling channel
        self.psi_w = 2 * np.pi * (1 - self.psi) / n_channels * np.cos(self.beta)       # raidal section of single uncooled wall segment


    def channel_geometry(self):
        # generate the cooling channel geometry; area, hydraulic diameter and wall thickness
        self.r_i = self.geom[:,1] + self.t_w_i                                      # inner radius of cooling channels
        self.r_o = self.geom[:,1] + self.t_w_i + self.h_c                           # outer radius of cooling channels

        self.A_c = 0.5 * self.psi_c * (self.r_o**2 - self.r_i**2) * self.n_channels   # flow area of all cooling channels, perpendicular to the flow [m^2]
        self.U_c_top = self.psi_c * self.r_o										# circumference of top cooling channels
        self.U_c_bottom = self.psi_c * self.r_i										# circumference of bottom cooling channels
        self.U_c_side = self.h_c * 2												# circumference of side cooling channels
        self.U_c = (self.U_c_top + self.U_c_bottom + self.U_c_side)*self.n_channels # cooling channel circumference [m]
        self.D_h = 4 * self.A_c / self.U_c											# cooling channel hydraulic diameter [m]

        # A helix of radius r at the angle beta to its axis is curved with the radius r / sin(beta)^2, around the chamber axis. Infinite for axial
        # channels; the curvature of the chamber contour itself is not included
        r_m = 0.5 * (self.r_i + self.r_o)                                           # radius of the centre of the cooling channels [m]
        with np.errstate(divide='ignore'):
            self.R_curv = r_m / np.sin(self.beta)**2                                # radius of curvature of the cooling channels [m]

        # angular position of the channels around the chamber axis [rad], from the first point of the contour: the channel advances
        # by tan(beta) / r_m per length of the contour
        ds = np.hypot(np.diff(self.geom[:,0]), np.diff(self.geom[:,1]))
        dtheta = 0.5 * (np.tan(self.beta[1:]) / r_m[1:] + np.tan(self.beta[:-1]) / r_m[:-1]) * ds
        self.twist = np.concatenate(([0.0], np.cumsum(dtheta)))


    def check_size(self, min_size):
        # Warning for cooling channels narrower or lower than min_size [m], which can not be depowdered reliably after printing. The width is
        # taken at the bottom of the channel, where it is narrowest, perpendicular to the channel for helical channels
        width = self.psi_c * self.r_i
        small = np.where((width < min_size * (1 - 1e-9)) | (self.h_c < min_size * (1 - 1e-9)))[0]
        if len(small) == 0:
            return

        x = self.geom[:,0] * 1e3
        i_w, i_h = np.argmin(width), np.argmin(self.h_c)
        print(red_bold('WARNING: cooling channels smaller than %g x %g mm in %d of %d sections, x = %s [mm]' % (min_size * 1e3, min_size * 1e3, len(small), len(x), x_ranges(x, small))))
        print(red_bold('They may not be depowdered reliably. Narrowest channel %.2f mm wide at x = %.1f [mm], lowest channel %.2f mm high at x = %.1f [mm]'
                       % (width[i_w] * 1e3, x[i_w], self.h_c[i_h] * 1e3, x[i_h])))
        print('')


    def set_thermocouples(self, x, r):
        # set a number of thermocouples for validation purposes
        # loc refers to which boundary on the 2D mesh the thermocouple rests on 
        # input arrays for lnghtwise (x) and radial coordinates (r) 
        # creates an array of dictionaries for all thermocouples in the cooridnate system of the 2D sections
        thermocouples = []

        def closest_node(node):
        # find closest index to thermocouple location
            dist = (self.geom[:,0] - node)**2
            idx = np.argmin(dist)                    # calculates clostes chamber index to TC location
            return idx

        for i in range(len(r)):
            idx = closest_node(x[i])                # axial location index

            section_x = r[i] * np.sin((self.psi_c[idx] + self.psi_w[idx])/2)
            section_y = r[i] * np.cos((self.psi_c[idx] + self.psi_w[idx])/2)
            
            thermocouples.append([idx, section_x, section_y])

        self.thermocouples = np.vstack(thermocouples)

        

if __name__ == "__main__":
    # test functionality of the Chamber and Cooling Geometry Classes

    D_c = 69.05e-3
    D_t = 24.14e-3
    D_e = 50.7e-3
    L_cyl = 74.77e-3
    r_2 = 10e-3
    r_1 = 72e-3
    r_n = 5e-3
    phi_conv = 30
    phi_div = 19
    phi_e  = 14

    cg = ChamberGeometry(D_c, D_t, D_e, L_cyl, r_1, r_2, r_n, phi_conv, phi_div, phi_e, step_size=0.003)
    cg.contour()
    cg.plot_contour()

    n = 8 
    h_c = 3e-3
    phi = 1/3
    t_w_i = 1e-3
    t_w_o = 1e-3

    c = CoolingGeometry(cg.geometry, h_c, phi, t_w_i, t_w_o, n)
    c.channel_geometry()


