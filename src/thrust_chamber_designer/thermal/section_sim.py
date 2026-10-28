#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3							#                                          
#####################################################################

from fipy import CellVariable, FaceVariable, Gmsh2D, TransientTerm, DiffusionTerm, ImplicitSourceTerm
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.tri import Triangulation
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, MultipleLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .output import Settings2D
from .section_mesh import get_section_mesh


class HeatEquationSolver():
    """[Summary]
    2D transient thermal sim of the chamber wall cross section. Assumes zero flux boundary conditions at the points of symmetry.
    Steady state is reached when the difference between temperatures at subsequent time steps is lower than a tolerance. 
    Settings object is used to pass informatiion about mesh resolution, time step etc. 
    Class is created for each section of the chamber, creates a mesh, sets boundary condtions and solves a 2D heat equation. 
    Information from the previous time step is used for updating the boundary conditions and thermal conductivity of the material.
    The thermal diffusivity is assumed constant with temperature.
    """
    def __init__(self, idx, gas, material, cooling_geometry, halpha_func, halpha_c_func, q_rad, coolant_temperature, ambient_temperature, path, settings, boiling_func=None, film=None):
        self.idx              = idx                      # location along the chamber contour
        self.gas              = gas                      # isentropic gas object
        self.material         = material                 # material object
        self.cooling_geometry = cooling_geometry         # cooling channel geometry object                    
        self.halpha_func      = halpha_func              # hot gas side heat transfer coefficient function pointer
        self.halpha_c_func    = halpha_c_func            # coolant side heat transfer coefficient function pointer
        self.boiling_func     = boiling_func             # coolant side heat flux with nucleate boiling function pointer, None for forced convection only
        self.q_rad            = q_rad                    # radiative heat flux [W/m^2]
        self.T_c              = coolant_temperature      # coolant temperature [K]
        self.T_amb            = ambient_temperature      # ambient temperature around the thruster [K]
        self.settings         = settings
        self.path             = path                     # folder path for figures
        self.film             = film                     # film cooling object, only used for the figures; None or False without film cooling
        self.boltzmann        = 5.67e-8			         # stefan boltzmann constant


    def heat_trans_coeffs(self, mesh, phi):
        # determine boundary heat transfer coefficients for coolant and chamber side
        self.halpha, self.T_hg = self.halpha_func(np.mean(phi.faceValue[mesh.physicalFaces["ChamberWall"]]), self.idx)                    # uses maxumum wall temperature to determine halpha
        self.halpha_c_bottom   = self.halpha_c_func(np.mean(phi.faceValue[mesh.physicalFaces["CoolantBottomWall"]]), self.idx, 'bottom')            # uses maximum wall temperature at cooling channel bottom wall for viscosity correction in halpha_c function (if applicable)
        self.halpha_c_top      = self.halpha_c_func(np.mean(phi.faceValue[mesh.physicalFaces["CoolantTopWall"]]), self.idx, 'top')            # uses maximum wall temperature at cooling channel bottom wall for viscosity correction in halpha_c function (if applicable)
        self.halpha_c_side     = self.halpha_c_func(np.mean(phi.faceValue[mesh.physicalFaces["CoolantSideWall"]]), self.idx, 'side')            # uses maximum wall temperature at cooling channel bottom wall for viscosity correction in halpha_c function (if applicable)


    def coolant_walls(self, mesh, T):
        # Heat transfer coefficient and coolant temperature of the boundary condition q = h * (T - T_c) for the faces at the cooling channel walls,
        # zero for all other faces. T is the temperature at the faces. With nucleate boiling the heat flux is not linear in the wall temperature:
        # the boiling curve is replaced by its tangent at T, so that updating the boundary condition between two solves is a Newton iteration
        h   = np.zeros(len(T))
        T_c = np.zeros(len(T))

        for wall, halpha_c in (("CoolantBottomWall", self.halpha_c_bottom), ("CoolantTopWall", self.halpha_c_top), ("CoolantSideWall", self.halpha_c_side)):
            h[np.array(mesh.physicalFaces[wall])]   = halpha_c
            T_c[np.array(mesh.physicalFaces[wall])] = self.T_c

        if self.boiling_func is not None:
            walls      = h > 0
            q, dq_dT   = self.boiling_func(T[walls], h[walls])
            h[walls]   = dq_dT
            T_c[walls] = T[walls] - q / dq_dT

        return h, T_c


    def boundary_conditions(self, mesh, phi, x, y):
        self.heat_trans_coeffs(mesh, phi)
        halpha_c, T_c = self.coolant_walls(mesh, np.array(phi.faceValue))
		
        # parameters are multiplied with mesh face normals
        halpha          = self.halpha * mesh.exteriorFaces                   	# heat transfer coefficient of combustion gas
        halpha_c        = FaceVariable(mesh=mesh, value=halpha_c)              # heat transfer coefficient of the coolant, tangent to the boiling curve with nucleate boiling
        q_rad           = self.q_rad * mesh.exteriorFaces                      # radiative heat flux
        T_c             = FaceVariable(mesh=mesh, value=T_c)                   # coolant temperature
        T_hg            = self.T_hg * mesh.exteriorFaces                       # gas temperature near the inner chamber wall
        T_amb           = self.T_amb * mesh.exteriorFaces                      # ambient temperature around the engine
        k               = self.material.k(phi.faceValue)                       # thermal conductivity of the material (dependent on temperature)

        # Set up heat flux boundary conditions
        # q = -k delta T

        phi.faceGrad.constrain(
            [(-1 / k * halpha_c * (phi.faceValue - T_c)) * mesh.faceNormals],
            mesh.physicalFaces["CoolantTopWall"],
        )
        phi.faceGrad.constrain(
            [(-1 / k * halpha_c * (phi.faceValue - T_c)) * mesh.faceNormals],
            mesh.physicalFaces["CoolantSideWall"],
        )
        phi.faceGrad.constrain(
            [(-1 / k * halpha_c * (phi.faceValue - T_c)) * mesh.faceNormals],
            mesh.physicalFaces["CoolantBottomWall"],
        )

        # hot gas side heat transfer on the inner chamber wall, including contribution from radiation
        phi.faceGrad.constrain(
            [(1 / k * (halpha * (T_hg - phi.faceValue) + q_rad)) * mesh.faceNormals],
            mesh.physicalFaces["ChamberWall"],
        )

        # Radiation boundary condition on the outside wall
        phi.faceGrad.constrain(
            [(-self.boltzmann * self.material.eps / k * (phi.faceValue ** 4 - T_amb ** 4)) * mesh.faceNormals],
            mesh.physicalFaces["OuterWall"],
        )


    def boundary_coefficients(self, mesh, phi):
        # The boundary conditions k * dT/dn = h * (T_ref - T) + q as heat sources of the cells at the wall, implicit in the wall temperature,
        # so the solution can not oscillate. Returns h and h * T_ref + q at the faces, zero for faces inside the wall, and the thermal
        # conductivity at all faces. Everything that depends on the temperature (heat transfer coefficients, thermal conductivity,
        # radiation to ambient) is evaluated with the current temperature field
        chamber = np.array(mesh.physicalFaces["ChamberWall"])
        outer   = np.array(mesh.physicalFaces["OuterWall"])

        self.heat_trans_coeffs(mesh, phi)

        T     = np.array(phi.faceValue)                        # temperature at the faces
        k     = self.material.k(T)                             # thermal conductivity of the material (dependent on temperature)
        h, T_ref = self.coolant_walls(mesh, T)                 # heat transfer coefficient and temperature of the gas or coolant at the boundary, zero for faces inside the wall
        q     = np.zeros(len(T))                               # heat flux which does not depend on the wall temperature

        h[chamber], T_ref[chamber], q[chamber] = self.halpha, self.T_hg, self.q_rad

        # radiation boundary condition on the outside wall, written as a heat transfer coefficient
        h[outer]     = self.boltzmann * self.material.eps * (T[outer]**2 + self.T_amb**2) * (T[outer] + self.T_amb)
        T_ref[outer] = self.T_amb

        return h, h * T_ref + q, k


    def steady_state(self, mesh, phi):
        # Solves the steady state temperature field directly, without marching in time. The boundary conditions are updated
        # between the solves until the temperature field stops changing
        for step in range(self.settings.max_iter):
            h, hT, k = self.boundary_coefficients(mesh, phi)
            implicit = (FaceVariable(mesh=mesh, value=h) * mesh.faceNormals).divergence
            explicit = (FaceVariable(mesh=mesh, value=hT) * mesh.faceNormals).divergence
            eq = DiffusionTerm(coeff=FaceVariable(mesh=mesh, value=k)) - ImplicitSourceTerm(coeff=implicit) + explicit == 0

            T_old = np.array(phi)
            eq.solve(var=phi)
            self.diff = np.max(np.abs(np.array(phi) - T_old))

            # safety net for boiling curves with kinks (beyond the CHF), which can make the update cycle between two states: under-relaxed after
            # 100 iterations. The termination criterion stays on the full update, so converged results do not depend on it
            if step >= 100:
                phi.setValue(T_old + 0.3 * (np.array(phi) - T_old))

            if self.settings.print_result:
                print('iteration: ', step + 1, '	T max: ', round(float(np.max(np.array(phi))), 3), ' [K]')

            # termination critera when the temperature field does not change anymore
            if self.diff < self.settings.tolerance:
                break

        else:
            print('No convergence reached after ', self.settings.max_iter, ' iterations. Error of last iteration is ', self.diff)


    def wall_temperatures(self, mesh, phi):
        # Temperatures for the wall stress analysis: temperature difference through the inner wall at the centre line of the cooling channel
        # and the mean temperatures of the inner wall, the ribs between the channels and the outer wall, with their cross section areas
        x_f = np.array(mesh.faceCenters[0])
        T_f = np.array(phi.faceValue)

        def centre_line(wall):
            # the centre line of the cooling channel is the symmetry line of the mesh at x = 0
            faces = np.where(np.array(mesh.physicalFaces[wall]))[0]
            return float(T_f[faces[np.argmin(np.abs(x_f[faces]))]])

        self.T_wall_hot  = centre_line("ChamberWall")
        self.T_wall_cold = centre_line("CoolantBottomWall")

        x, y = np.array(mesh.cellCenters)
        r    = np.sqrt(x**2 + y**2)
        A    = np.array(mesh.cellVolumes)
        T    = np.array(phi)

        r_i   = self.cooling_geometry.geom[self.idx, 1] + self.cooling_geometry.t_w_i[self.idx]      # inner radius of the cooling channels
        r_o   = r_i + self.cooling_geometry.h_c[self.idx]                                            # outer radius of the cooling channels
        inner = r <= r_i
        outer = r >= r_o
        rib   = ~inner & ~outer

        self.A_inner, self.A_rib, self.A_outer = (float(np.sum(A[part])) for part in (inner, rib, outer))
        self.T_inner, self.T_rib, self.T_outer = (float(np.sum(T[part] * A[part]) / np.sum(A[part])) for part in (inner, rib, outer))


    def transient(self, mesh, phi):
        # Marches in time from ambient temperature up to the run time. The boundary conditions are implicit in the wall temperature as in
        # the steady state and are updated every time step, so long time steps can not make the solution oscillate. The time step grows
        # from its initial value by the factor adaptive_up to at most 1/50 of the run time, the last step ends exactly at the run time.
        # The heat capacity is constant, the thermal conductivity depends on the temperature. The equation is built once, only the values
        # of its coefficients are updated every time step
        dt_max = self.settings.run_time / 50
        dt     = self.settings.time_step
        time   = 0

        k  = FaceVariable(mesh=mesh, value=0.0)
        h  = FaceVariable(mesh=mesh, value=0.0)
        hT = FaceVariable(mesh=mesh, value=0.0)
        eq = (TransientTerm(coeff=self.material.rho * self.material.Cp) == DiffusionTerm(coeff=k)
              - ImplicitSourceTerm(coeff=(h * mesh.faceNormals).divergence) + (hT * mesh.faceNormals).divergence)

        while time < self.settings.run_time - 1e-12:
            dt = min(dt, dt_max, self.settings.run_time - time)
            h_value, hT_value, k_value = self.boundary_coefficients(mesh, phi)
            h.setValue(h_value)
            hT.setValue(hT_value)
            k.setValue(k_value)
            eq.solve(var=phi, dt=dt)
            time += dt
            dt   *= self.settings.adaptive_up

            if self.settings.print_result:
                print('time: ', round(time, 3), ' [s]	T max: ', round(float(np.max(np.array(phi))), 3), ' [K]')


    def vertex_field(self, mesh, phi):
        # temperature field of the section on the mesh vertices: vertex coordinates [m], triangle vertex ids of each cell and the cell values
        # averaged onto the vertices, so the field can be shaded smoothly
        tri = np.asarray(mesh._orderedCellVertexIDs).T
        vx, vy = (np.asarray(v) for v in mesh.vertexCoords)
        counts = np.bincount(tri.ravel(), minlength=len(vx))
        T_vertex = np.bincount(tri.ravel(), weights=np.repeat(phi.value, 3), minlength=len(vx)) / np.maximum(counts, 1)

        return vx, vy, tri, T_vertex


    def plot_section(self, mesh, phi, cmap='magma'):
        vx, vy, tri, T_vertex = self.vertex_field(mesh, phi)

        # mirror about the symmetry plane at x = 0 to show the full cooling channel, then add the facing half
        # of each neighbouring channel by rotating about the chamber axis by one channel pitch, in [mm]
        pitch = self.cooling_geometry.psi_c[self.idx] + self.cooling_geometry.psi_w[self.idx]
        rotate = lambda x, y, a: (np.cos(a) * x + np.sin(a) * y, -np.sin(a) * x + np.cos(a) * y)
        copies = [(vx, vy), (-vx, vy), rotate(-vx, vy, pitch), rotate(vx, vy, -pitch)]
        vx, vy = 1000 * np.concatenate([c[0] for c in copies]), 1000 * np.concatenate([c[1] for c in copies])
        tri = np.vstack([tri + i * len(T_vertex) for i in range(len(copies))])
        T_vertex = np.tile(T_vertex, len(copies))

        fig, ax = plt.subplots()
        plot = ax.tripcolor(Triangulation(vx, vy, tri), T_vertex, shading='gouraud', cmap=cmap)
        ax.set_aspect('equal')
        ax.set_xlabel('x [mm]')
        ax.set_ylabel('y [mm]')
        # use the same tick spacing on both axes, sized to fit the shorter (y) axis
        tick_step = np.diff(MaxNLocator(nbins=3, steps=[1, 2, 5, 10]).tick_values(vy.min(), vy.max()))[0]
        ax.xaxis.set_major_locator(MultipleLocator(tick_step))
        ax.yaxis.set_major_locator(MultipleLocator(tick_step))
        divider = make_axes_locatable(ax)
        fig.colorbar(plot, cax=divider.append_axes('right', size='3%', pad=0.1), label=phi.name)
        self.plot_tracker(divider.append_axes('bottom', size='45%', pad=0.6))
        fig.savefig(self.path + "/" + str(self.idx) + ".png", bbox_inches='tight')
        plt.close(fig)

    def plot_tracker(self, ax):
        # small outline of the chamber contour with the position of this section along it, in [mm]
        x, r = 1000 * self.cooling_geometry.geom[:, 0], 1000 * self.cooling_geometry.geom[:, 1]
        x_s, r_s = x[self.idx], r[self.idx]

        ax.fill(np.concatenate((x, x[::-1])), np.concatenate((r, -r[::-1])), facecolor='0.92', edgecolor='0.5', linewidth=1)

        if self.film:
            # gaseous film along the wall, fading out with its effectiveness
            segments = [np.column_stack((x[i:i+2], sign * r[i:i+2])) for i in range(len(x) - 1) for sign in (1, -1)]
            colors   = [(*to_rgb('tab:cyan'), float(eta)) for eta in np.repeat(self.film.eta[:-1], 2)]
            ax.add_collection(LineCollection(segments, colors=colors, linewidth=3, capstyle='butt', clip_on=False))

            # liquid film from each ring of ports to where the wall falls dry
            for (idx, *_), x_dry in zip(self.film.ports, self.film.x_dry):
                x_l = np.append(x[(x >= x[idx]) & (x < 1000 * x_dry)], 1000 * x_dry)
                r_l = np.interp(x_l, x, r)
                for sign in (1, -1):
                    ax.plot(x_l, sign * r_l, color='tab:blue', linewidth=3, solid_capstyle='butt', clip_on=False)

            ax.legend(handles=[Line2D([], [], color='tab:blue', linewidth=3, label='Liquid film'),
                               Line2D([], [], color='tab:cyan', linewidth=3, label='Gaseous film')],
                      fontsize=7, frameon=False, loc='center left', bbox_to_anchor=(1.0, 0.5))
        ax.plot([x_s, x_s], [-r_s, r_s], color='0.5', linewidth=0.8, linestyle='--')
        ax.plot(x_s, r_s, 'o', color='tab:red', markersize=5, clip_on=False)
        beta = np.degrees(self.cooling_geometry.beta[self.idx])
        ax.text(x_s, -np.max(r), 'x = %.1f mm' % x_s + (', helical channels at %.0f deg, section perpendicular to the channel' % beta if beta > 0 else ''),
                fontsize=8, va='top', ha='center')
        ax.set_aspect('equal')
        ax.axis('off')

    def run_sim(self):
        # generate mesh
        mesh = get_section_mesh(self.settings.cell_size, self.idx, self.cooling_geometry)
        # set solution variable and intial guess
        phi = CellVariable(name="Temperature [K]", mesh=mesh, value=float(self.T_amb))

        # create mesh nodes and boundary conditrions
        x, y = mesh.faceCenters

        # the steady state is solved directly, time stepping is only used if a run time is set
        if self.settings.run_time == 'steady_state':
            self.steady_state(mesh, phi)
        else:
            self.transient(mesh, phi)

        # boundary fluxes of the final temperature field, used for the results below
        self.boundary_conditions(mesh, phi, x, y)

        #self.phi = phi
        self.outer_wall_temp = max(phi.faceValue[mesh.physicalFaces["OuterWall"]])
        self.inner_wall_temp = max(phi.faceValue[mesh.physicalFaces["ChamberWall"]])
        self.coolant_wall_temp = max(max(phi.faceValue[mesh.physicalFaces[wall]]) for wall in ("CoolantBottomWall", "CoolantTopWall", "CoolantSideWall"))
		
		# boundary fluxes along normal vectors
        dT_dn_c_top    = np.sqrt(phi.faceGrad[0][mesh.physicalFaces["CoolantTopWall"]]**2 + phi.faceGrad[1][mesh.physicalFaces["CoolantTopWall"]]**2)
        dT_dn_c_bottom = np.sqrt(phi.faceGrad[0][mesh.physicalFaces["CoolantBottomWall"]]**2 + phi.faceGrad[1][mesh.physicalFaces["CoolantBottomWall"]]**2)
        dT_dn_c_side   = np.sqrt(phi.faceGrad[0][mesh.physicalFaces["CoolantSideWall"]]**2 + phi.faceGrad[1][mesh.physicalFaces["CoolantSideWall"]]**2)
        dT_dn_chamber  = np.sqrt(phi.faceGrad[0][mesh.physicalFaces["ChamberWall"]]**2 + phi.faceGrad[1][mesh.physicalFaces["ChamberWall"]]**2)
        dT_dn_outer    = np.sqrt(phi.faceGrad[0][mesh.physicalFaces["OuterWall"]]**2 + phi.faceGrad[1][mesh.physicalFaces["OuterWall"]]**2)
		
		# q = k * dT_dn
        self.q_c_top     = self.material.k(phi.faceValue[mesh.physicalFaces["CoolantTopWall"]]) * dT_dn_c_top
        self.q_c_bottom  = self.material.k(phi.faceValue[mesh.physicalFaces["CoolantBottomWall"]]) * dT_dn_c_bottom
        self.q_c_side    = self.material.k(phi.faceValue[mesh.physicalFaces["CoolantSideWall"]]) * dT_dn_c_side
        self.q_chamber   = self.material.k(phi.faceValue[mesh.physicalFaces["ChamberWall"]]) * dT_dn_chamber
        self.q_outer	 = self.material.k(phi.faceValue[mesh.physicalFaces["OuterWall"]]) * dT_dn_outer

        # highest local heat flux into the coolant, in the corner of the channel. It depends on the mesh and is only saved for information
        self.q_c_max = float(max(max(self.q_c_top), max(self.q_c_bottom), max(self.q_c_side)))
		
		# total coolant side heat transferred [W/m]
        A        = np.asarray(mesh.scaledFaceAreas)
        self.Q_c = 2 * sum(float(np.sum(np.asarray(q) * A[np.array(mesh.physicalFaces[wall])]))
                           for q, wall in ((self.q_c_top, "CoolantTopWall"), (self.q_c_bottom, "CoolantBottomWall"), (self.q_c_side, "CoolantSideWall")))

        # mean heat flux into the coolant at the bottom of the channel, the wall above the hot gas side, which is compared with the critical heat flux
        bottom = np.array(mesh.physicalFaces["CoolantBottomWall"])
        self.q_c_bottom_mean = float(np.sum(np.asarray(self.q_c_bottom) * A[bottom]) / np.sum(A[bottom]))

        self.wall_temperatures(mesh, phi)
        self.field = self.vertex_field(mesh, phi)          # temperature field of the section, saved for the 3D plot

        if self.settings.save_fig:
            # save section temperature profile
            self.plot_section(mesh, phi)

        if self.settings.log_thermocouples:
            # log temperature value at thermocouple locations for validation purposes
            if self.idx in self.settings.thermocouples[:,0]:

                # find which thermocouple is nearest
                TC = np.where(self.idx == self.settings.thermocouples[:,0])[0][0]

                def closest_node(node, nodes):
                    #determine link between TC position and mesh nodes
                    dist = (nodes - node)**2
                    return np.argmin(dist)
                
                # get x position in this section mesh
                x_mesh = closest_node(self.settings.thermocouples[TC, 1], x[mesh.physicalFaces["SideWall"]])
                print('Thermocouple location:    ', self.idx)
                self.T_TC = phi.faceValue[mesh.physicalFaces["SideWall"]][x_mesh]
                print('Thermocouple temperature: ', self.T_TC)
		
		
		
if __name__ == "__main__":

    import config
    import os
	
    try:
        os.mkdir('TestSectionThermalSim')
    except:
        pass
		
    def halpha_func(T, idx):
        return 1600, 2400

    def halpha_c_func(T, idx, wall=None):
        return 1113

    q_rad = 0
    T_c = 288
    T_amb = 288
    idx = 1
	
    solver = HeatEquationSolver(
        idx,
        config.gas,
        config.material,
        config.cooling_geom,
        halpha_func,
        halpha_c_func,
        q_rad,
        T_c,
        T_amb,
        path='TestSectionThermalSim',
        settings=config.settings
    )

    solver.run_sim()

