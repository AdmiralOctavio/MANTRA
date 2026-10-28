#####################################################################
#                           PyRocket								#
# 2D Regenertive Cooling Simulation for Bipropellant Rocket Engines #
#                                                                   #
# Creator:  Joanthan Neeser                                         #
# Date:     15.12.2022                                              #
# Version:  2.3  													#
# License:	GNU GENERAL PUBLIC LICENSE V3							#                                          
#####################################################################

import os
import sys
import numpy as np
import csv


def red_bold(text):
    # red bold text for warnings in the terminal, plain text if the output is written to a file
    if not sys.stdout.isatty():
        return text
    if os.name == 'nt':
        os.system('')                                               # switches on the colour codes in the Windows console
    return '\033[1;31m' + text + '\033[0m'


# settings for 2D transient thermal sims 
class Settings2D:
    def __init__(self, cell_size, time_step, tolerance, max_iter, save_fig, print_result, run_time, start_idx=-1, adaptive_up=1.4, log_thermocouples=False, thermocouples=0):
        self.cell_size    = cell_size                               # cell size in 2D section solver, will heavily impact performance
        self.time_step    = time_step                               # time step in 2D section solver use 5e2 for IN718 and 5e3 for CuCrZr
        self.tolerance    = tolerance                               # maximum temperature differnece between time steps
        self.max_iter     = max_iter		   				     	# maximum number of iterations before termination
        self.save_fig     = save_fig                                # save figures to folder in Output Class
        self.print_result = print_result                            # print intermittant maximum temperatures, useful for DEBUGGING
        self.run_time     = run_time                                # 'steady_state' or termination time for sim
        self.start_idx    = start_idx							    # starting index, use 0 for injector side and -1 for nozzle
        self.adaptive_up  = adaptive_up                             # adaptive time step (step up)
        self.log_thermocouples = log_thermocouples                  # bool if temperature at specific locations is to be logged
        self.thermocouples = thermocouples                          # set thermocouple locations for validation purposes

    def output_msg(self):
        print('#############################################')
        print('     Starting Cooling Channel Simulation     ')
        print('#############################################')
        print('')
        print('Section mesh resolution:         ', round(self.cell_size, 6), ' [m]')
        print('Transient simulation time step:  ', round(self.time_step, 4), ' [s]')
        print('')

# output class for section sims

class Output1D:
    def __init__(self, geometry, folder_path="SectionImages"):
        self.geometry    = geometry
        self.halpha      = np.ndarray(len(self.geometry[:, 1]))
        self.halpha_c    = np.ndarray(len(self.geometry[:, 1]))
        self.q_rad       = np.ndarray(len(self.geometry[:, 1]))
        self.q           = np.ndarray(len(self.geometry[:, 1]))
        self.T_wall_i    = np.ndarray(len(self.geometry[:, 1]))
        self.T_c         = np.ndarray(len(self.geometry[:, 1]))
        self.P_c         = np.ndarray(len(self.geometry[:, 1]))
        self.Re          = np.ndarray(len(self.geometry[:, 1]))
        self.v_coolant   = np.ndarray(len(self.geometry[:, 1]))
        self.T_hg        = np.ndarray(len(self.geometry[:, 1]))
        self.T_wall_c    = np.ndarray(len(self.geometry[:, 1]))
        self.T_sat       = np.ndarray(len(self.geometry[:, 1]))
        self.q_c_max     = np.ndarray(len(self.geometry[:, 1]))
        self.q_chf       = np.ndarray(len(self.geometry[:, 1]))
        self.q_c_bottom  = np.ndarray(len(self.geometry[:, 1]))
        self.chf_state   = np.zeros(len(self.geometry[:, 1]), dtype=int)
        self.fields      = [None] * len(self.geometry[:, 1])                 # temperature field of every section, for the 3D plot

        # wall temperatures and stresses from StressAnalysis.py, stresses stay nan for materials without a yield strength
        self.stress_keys = ['dT_wall', 'T_inner', 'T_rib', 'T_outer', 'sig_p_bend', 'sig_p_membrane', 'sig_grad', 'sig_mis_hoop', 'sig_mis_axial', 'sig_secondary', 'sig_y', 'X', 'Y', 'strain_range']
        for key in self.stress_keys:
            setattr(self, key, np.full(len(self.geometry[:, 1]), np.nan))
        self.regime      = [''] * len(self.geometry[:, 1])
        self.folder_path = folder_path
		
    def output_msg(self):
        print('Folder Path: 	', self.folder_path)
        print('')

    def write_fields(self):
        # 2D temperature field of every section: vertex coordinates [m], triangles and vertex temperatures [K], for the 3D plot
        data = {}
        for i, field in enumerate(self.fields):
            if field is not None:
                vx, vy, tri, T = field
                data['x' + str(i)], data['y' + str(i)] = vx.astype(np.float32), vy.astype(np.float32)
                data['tri' + str(i)], data['T' + str(i)] = tri.astype(np.int32), T.astype(np.float32)
        np.savez_compressed(self.folder_path + '/section_fields.npz', **data)

    def write_csv(self):
        # open the file in the write mode
        f = open(self.folder_path + "/sim_data.csv", "w+")
        writer = csv.writer(f)

        # write header row
        writer.writerow(
            [
                " section index",
				" x coordinate [mm]",
                " halpha [W/m^2/K]",
                " halpha_c [W/m^2/K]",
                " q_rad [W/m^2]",
                " q_total [W/m^2]",
                " T_wall_i [K]",
                " T_coolant [K]",
                " P_coolant [Pa]",
                " Re_coolant",
                " v_coolant [m/s]",
                " T_hg (cinjarev) [K]",
                " T_wall_coolant [K]",
                " T_sat_coolant [K]",
                " q_coolant_max [W/m^2]",
                " q_CHF [W/m^2]",
                " dT_inner_wall [K]",
                " T_inner_wall_mean [K]",
                " T_rib_mean [K]",
                " T_outer_wall_mean [K]",
                " sigma_pressure_bending [Pa]",
                " sigma_pressure_membrane [Pa]",
                " sigma_gradient [Pa]",
                " sigma_mismatch_hoop [Pa]",
                " sigma_mismatch_axial [Pa]",
                " sigma_secondary [Pa]",
                " sigma_yield [Pa]",
                " Bree X",
                " Bree Y",
                " strain range",
                " Bree regime",
                " q_coolant_bottom_mean [W/m^2]",
                " beyond CHF (0 no, 1 post-CHF branch, 2 solved without boiling)",
            ]
        )

        for i in range(len(self.geometry[:, 1])):
            writer.writerow(
                [
                    i,
					self.geometry[i,0]*1000,
                    self.halpha[i],
                    self.halpha_c[i],
                    self.q_rad[i],
                    self.q[i],
                    self.T_wall_i[i],
                    self.T_c[i],
                    self.P_c[i],
                    self.Re[i],
                    self.v_coolant[i],
                    self.T_hg[i],
                    self.T_wall_c[i],
                    self.T_sat[i],
                    self.q_c_max[i],
                    self.q_chf[i],
                ]
                + [getattr(self, key)[i] for key in self.stress_keys]
                + [self.regime[i]]
                + [self.q_c_bottom[i], self.chf_state[i]]
            )

        f.close()
