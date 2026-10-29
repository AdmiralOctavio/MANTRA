> This is the README of PyRocket from the Rocket-Engine-Thermal-Simulator repository, kept unchanged because it documents the
> thermal model. In this repository the modules have new names: `CEAClass.py` is `core/chemistry.py`, `PropLibrary.py` is
> `core/prop_library.py`, `config.py` and `run.py` are `thermal/example_config.py`, and the other modules are in `thermal/`
> (`RegenCooling.py` is `regen.py`, `SectionThermalSim.py` is `section_sim.py`, `SectionMesh.py` is `section_mesh.py`,
> `GeomClass.py` is `geometry.py`, `CoolantClass.py` is `coolant.py`, `MaterialLib.py` is `materials.py`, `FilmCooling.py` is
> `film.py`, `StressAnalysis.py` is `stress.py`, `PlottingFunctions.py` is `plots.py`, `Output.py` is `output.py`,
> `IsentropicRelations.py` is `isentropic_flow.py`, `ValidateCHF.py` is `validate_chf.py`, `UnitTests.py` is `unit_tests.py`).
> The inputs of `config.py` are now set in the desktop app or a design file, and the installation in the main README replaces
> `install_dependencies.sh`: no FORTRAN compiler and no gmsh executable are needed.

# PyRocket
PyRocket is a thermal simulaton program for regeneratively cooled rocket engine thrust chambers. It is designed as a reasonably accurate predictive 
tool to assist in design and allow for integration into basic shape optimisation. The program relies on the use of Nusselt number correlations for 
deterimining the heat transfer coefficients from the hot combustion gases, as well as into the cooling fluid. The temperature inside the chamber 
wall is then determined using a 2D transient thermal simulation based on a Finite Volume method. This is repeated for a set number of sections 
along the chamber contour. The predicted heat flux to the cooling fluid in each section is used to calculate a temperature increase of the cooling fluid. 
Basic wall friction estimates are also used to track coolant pressure drop in the channels. 


## Installation
PyRocket relies on several external libraries, as well as GMSH. The installation of dependencies can be done using the install_dependencies.sh file. 


### Installation on WINDOWS 10
The NASA CEA library ('pip install cea') comes precompiled and needs no FORTRAN compiler, so PyRocket also runs natively on Windows. 
The installation in a Linux subsystem works as follows. 

```bash
    1. as admin, open PowerShell
    2. run: 'wsl --install'
    3. run: 'wsl --install -d Ubuntu-20.04'
    4. run: 'python3 --version' to check the python install (should be above V3.8)

    5. clone PyRocket Files into a folder (locally, not on any network)
    6. open wsl and naviagate to the folder with the PyRocket files 
    7. run: 'sudo bash install_dependencies.sh'
```


### Installation on Ubuntu
The install_dependencies.sh file is set up for installation on Ubuntu, but can easily be altered for use in other Linux distributions. 
```bash
    1. clone PyRocket Files into a folder
    2. open a terminal window and naviagate to the folder with the PyRocket files  
    3. run: 'sudo bash install_dependencies.sh'
```


## Verify Installation
In order to verify that all pacakges were installed correctly, run 'SectionThermalSim.py' in your terminal window. 
```bash
    python3 SectionThermalSim.py
```
This will run a single transient thermal simulation. Do not alter the contents of the config.py file before running. The expected ouput is the maximum temperature
at every time step printed in the terminal window. Additionally a directory called 'TestSectionThermalSim' is created, where an image of the temperature profile 
of the test section is saved. This unit test can be repeated after altering the config.py file for each use case to verify the stability of your new time step and 
mesh resolution settings. 


## Using PyRocket
PyRocket is designed to be used with nearly arbitrary combinations of propellants, cooling fluids and chamber materials. All inputs are changed in config.py 
New propellants can be set in PropLib.py, with new matierals added in MaterialLib.py. The selected coolant must be a fluid present in 
[CoolProp](http://www.coolprop.org/fluid_properties/PurePseudoPure.html). A debug mode can be set in config.py to examine the results of the 2D transient simulation to verfiy the chosen mesh and time 
step settings. Run the full simulation by executing 'run.py' in your terminal window. 

```bash
    python3 run.py
```

### Debug mode
Set the 'print_result' option to True in config.py in order to display more detialed information on the each transient thermal simulation. The output will show each time 
step and the resulting maximum temperature. This can show non convergence, in the form of reasonable, but oscillating values, or obvious numerical errors in the 
simulation. In the case of non convergence, the time step can be lowered, or the mesh resolution can be increased. Additionally the maximum iteration count
can be increased if necessary. 


### Setting up chamber geometries
The combustion chamber is defined using a series of parameters in config.py that describe the cylindrical chamber section, and the converging and diverging sections 
respectively. The variable convention here alligns closely with [RPA](https://www.rocket-propulsion.com/index.htm), with the notable differnece, that R1 and R2 are 
exchanged in this program. A plot of the chamber contour is saved in the target directory before each run. The variable 'step_size' in config.py determines the 
number of sections by imposing a minimum resolution in axial direction. In the desktop app and design files, a smaller step at the
throat (ThermalSettings.throat_step) can be used within a zone around the throat (throat_zone), growing by 1.2 times per section up
to step_size away from it. The coolant heat balance, pressure drop, film cooling and helix twist use the actual distance between
neighbouring sections, so the sections need not be evenly spaced.  


### Setting up cooling channel geometries
The basic program is set up for a rectangular cooling channel geometry with cooling channel areas as a fraction of local circumference. The basic properties of the cooling 
geometry, such as area and hydraulic diameter are computed in GeomClass.py. The mesh for each chamber section is created in SectionMesh.py, with the final thermal 
simulation and evaluation of results in SectionThermalSim.py. The following naming convention is used for the individual faces (this is relevant for allocating 
boundary conditions and evaluating results).

Boundary Name 		| Description
------------------- | -------------------------------------------------------------
ChamberWall   		| Inner chamber wall in contact with combustion gases
OuterWall     	 	| Outer wall of combustion chamber
CoolantBottomWall	| Wall of the cooling channel closest to the inner chamber wall
CoolantTopWall		| Wall of the cooling channel closest to the outer chamber wall 
CoolantSideWall		| Wall of the cooling channel rib

If the geometry of the cooling channels is fundamentally changed, several functions in several files need to be altered. In order to edit the basic properties, such as 
area and hydraulic diameter, edit the 'CoolingGeometry' class in GeomClass.py. In order to alter the mesh itself, edit the SectionMesh.py file. The 2D mesh geometry is 
produced using [GMSH](https://gmsh.info/). Several tutorials exist on how to use GMSH. Lastly, SectionThermalSim.py needs to be edited. This extends to the faces on which 
boundary conditions are applied, as well as the faces over which boundary fluxes along normal vectors are calculated. These can be found starting in line 52 and 126 respectively. 
Changes to the mesh can be verified by running SectionThermalSim.py

Powder has to be removed from the channels of printed chambers, which is not reliable for very small channels. If the channels anywhere along the
contour are narrower or lower than 'min_channel_size' in config.py (1 mm by default), a warning in red is printed at the end of the run with the
sections concerned and the smallest width and height. The width is taken at the bottom of the channel, where it is narrowest, and perpendicular to
the channel for helical channels.


### Helical cooling channels
Setting 'helical' to True in config.py winds the cooling channels around the chamber axis instead of running them straight along it. 'helix_angle' is the
angle between the channels and the chamber axis in degrees, at the centre of the channel. Like 'h_c', 'psi' and 't_w_i' it can be a function of the axial
coordinate, e.g. to steepen the helix towards the throat. With 'helical' set to False the angle is ignored and the channels are axial. The number of channels
and the fill factor 'psi' keep their meaning: 'psi' is the fraction of the circumference covered by the channels, which is the same in the cross section of the
chamber and in the cross section perpendicular to the channels. With a helix angle beta:

* the 2D sections are the cross sections perpendicular to the channels, in which the heat is conducted. Channels and ribs are narrower by cos(beta) than along the circumference. This is the width used for the flow area, the hydraulic diameter and the bending of the inner wall between two ribs in the stress analysis. The oblique cut of the chamber wall is slightly flatter than the chamber radius, this is neglected.
* the flow area is smaller by cos(beta), so the coolant is faster for the same mass flow, with higher heat transfer coefficients and pressure drop.
* the channels are longer than the contour by 1 / cos(beta). The coolant picks up the heat of the same chamber wall over the longer channel, the pressure drop is calculated over the length of the channel.
* the channels are curved around the chamber axis with the radius r / sin(beta)^2. The secondary flow (Dean vortices) increases the friction factor by [Re (D_h / 2R)^2]^0.05 after Ito (1959). It drives the coolant towards the concave top wall of the channel, away from the axis, and away from the convex bottom wall on the hot gas side. After Taylor the heat transfer coefficient of the top wall is multiplied and that of the bottom wall divided by the same factor; the side walls keep the value of a straight channel. Both are held at 1 below Re (D_h / 2R)^2 = 1. For a coolant at Re = 10000 in a channel of 1.2 mm hydraulic diameter, 9.6 mm from the axis, the factor is 1.05 at 30 deg and 1.12 at 45 deg. The curvature of the chamber contour itself is not included, neither for axial nor for helical channels.

The section images note the helix angle and show the cross section perpendicular to the channels. In 'sections_3d.html' the sections are widened by
1 / cos(beta) back to the cross section of the chamber and rotated by the angular position of the channels, so the slice winds around the chamber.
At the end of the run the length of the channels and the number of turns around the chamber axis are printed.


### 2D section solver 
A transient thermal simulation is run on each section of the combustion chamber geomerty. Setting up the finite volume system and boundary conditions is done using 
[FiPy](https://www.ctcms.nist.gov/fipy/). The thermal simualtion takes advantage of symmetry in circumferetial direction, with the flux over the symmetry walls being zero. 

```math
\frac{\partial T}{\partial t} = \alpha \nabla T
```

With 

```math
 q = - k \frac{\partial T}{\partial x}
```

A constant thermal diffusivity is assumed, witht the thermal conductivity dependent on temerpature. The convective heat flux boundary conditions take the form of 

```math
\frac{\partial T}{\partial x} = \frac{1}{k} h_{\alpha} (T_{external} - T_{wall})
```

In varying forms this BC is applied to the boundaries: 'ChmaberWall', 'CoolantBottomWall', 'CoolantTopWall' and 'CoolantSideWall' . The radiation boundary condition
is expressed as

```math
\frac{\partial T}{\partial x} = \frac{\sigma \epsilon}{k} (T_{ambient}^4 - T_{wall}^4)
```

and is applied to the 'OuterWall' boundary. The heat equation is solved for each time step, after which the boundary conditions are updated using the results 
of the previous time step before solving the next time step. The simulation is either terminated when the maximum temperature reaches steady state (within a set tolerance),
or after a set maximum number of iterations is reached. All settings for the 2D thermal sim are found in config.py. During a full run of the program, the boundary flux over
all boundaries is calculated and used to determine the total heat flux, as well as the temperature increase of the cooling fluid as it passes throug each section. 

## Liquid Film Cooling Model
Optional addition of film cooling to supplement regenerative cooling. This is an implementation of the analytical 0D liquid film cooling model proposed by [Shine et al](https://www.researchgate.net/publication/256718300_A_new_generalised_model_for_liquid_film_cooling_in_rocket_combustion_chambers).The model relies on an energy balance between the convective and radiative heat transfer of the combustion gases and the evaporation of the coolant. The model produces an estimate of the liquid film length and assumes that the temperature rise of the wall under the liquid film is very small. The liquid film cooling length and the resultant reduction in convective heat transfer coefficient are passed to the regenerative cooling method. The wall under the liquid film does not see the combustion gas: its convective heat evaporates the film, so the wall faces coolant at saturation temperature there and is heated by radiation only. Downstream of the liquid film the evaporated coolant forms a gaseous film, which lowers the gas temperature at the wall. Its effectiveness follows the turbulent boundary layer model of Librizzi and Cresci (see Goldstein, Film Cooling, 1971) and decays with the distance from the end of the liquid film. Reactions between the coolant and the combustion gas are not considered. Besides the film from the injector face, rings of film cooling ports can be placed anywhere along the chamber contour ('film_ports' in config.py). The liquid film of each ring is calculated with the local conditions of the combustion gas, and the gaseous films of several rings are combined as proposed by Sellers. Ports in the chamber wall take their coolant from the cooling channels, so less coolant is left for the rest of the channel. The liquid film model is not validated for the high gas velocities at and downstream of the throat. 

### Plotting Options 
Results of the full chamber simulation are saved in the target directory as a csv file. A select set of saved data is automatically plotted by calling 'PlottingFunctions.py'.
These include the heat transfer coefficients, coolant properties, as well as maximum wall temperature. 

The 2D temperature field of every section is saved in 'section_fields.npz'. From it 'sections_3d.html' shows the sections joined along the chamber
contour in 3D: a slice of the wall with three cooling channels and their ribs, coloured by temperature. The wall is transparent so the cooling
channels can be seen through it. The file opens in a web browser, where the view can be rotated and zoomed and the temperature is shown under the
cursor (it needs plotly in Python, and an internet connection to load plotly.js). The number of channels and the transparency can be changed with
the arguments of 'section_3d_plot' in 'PlottingFunctions.py'.


### Chamber Side Heat Transfer Coefficient Models
The heat flux to the combustion chamber is dominated by convective heat transfer, with some contribution from radiation. Three Nusselt number correlations can be chosen for 
the convective heat transfer coefficients. 

* 'cinjarev'
* 'standard-bartz'
* 'modified-bartz'
		
Especially for small chamber geomerties, the 'cinjarev' correlation is recommended.


### Coolant Side Heat Transfer Coefficient Models
Similar to the hot gas side, the convection of heat to the cooling fluid can be estimated using one of four Nusselt number correlations. 

* 'gnielinski'
* 'gnielinski-rough'
* 'dittus-boelter'
* 'dittus-boelter-simple'

These correlations have different ranges of applicability in terms of Reynolds number. Check the comments in RegenCooling.py for details. 'gnielinski' covers laminar,
transitional and turbulent flow: below Re = 2300 it uses developing laminar flow at constant wall temperature, which does not depend on the roughness, and between
Re = 2300 and 4000 it interpolates linearly to the turbulent correlation. 'gnielinski-rough' uses the turbulent correlation down to Re = 2300 and holds it at that
value for lower Re, for rough (e.g. 3D printed) channels which become turbulent at lower Reynolds numbers than smooth tubes. The 'dittus-boelter' correlations are
only valid above Re = 1e4. The 'dittus-boelter' correlation also features a viscosity correction for the near-wall fluid film. In practice the 'gnielinski' models are
the most accurate, if applicable, as they include the surface roughness through the friction factor, especially relevant for 3D printed designs. 


### Nucleate Boiling and Critical Heat Flux
Cooling channel walls above the saturation temperature of the coolant are cooled by subcooled nucleate boiling ('boiling' in config.py). The heat flux follows
the correlation of Liu and Winterton (1991), which combines forced convection with the nucleate pool boiling correlation of Cooper. It is evaluated at every
face of the channel walls in the 2D section, since the bottom of a channel can boil while the top does not. Boiling keeps the wall 10 to 30 K above the
saturation temperature, which is much colder than with forced convection alone. Most of the heat then enters the coolant through the bottom of the channel.
For coolant mixtures the saturation properties (bubble point, boiling range, densities, enthalpy of evaporation) are taken from the bubble and dew line of
the mixture in CoolProp, and the boiling heat transfer is reduced with the correction of Thome and Shakir (1987).

Nucleate boiling breaks down at the critical heat flux (CHF), where a vapour film starts to separate the coolant from the wall. The mean heat flux at the
bottom of the cooling channel, where the heat from the hot gas side enters the coolant, is compared to the CHF in every section. Both are saved in the csv
file and plotted ('chf.png'). The highest local heat flux, in the corner between the bottom and the side of the channel, is saved and plotted for
information only: it grows with mesh refinement, while the mean at the channel bottom converges. Three correlations can be chosen with 'chf_method' in config.py:

* 'meyer': correlation of Meyer, Linne and Rousar (NASA TM-1998-206612) for ethanol, based on the product of coolant velocity and subcooling with a correction for pressure. It reproduces their 38 tests in electrically heated tubes (2.4 mm diameter, 10 to 48 bar, 3 to 23 m/s, 18 to 200 K subcooling) within 20 %. The coolant only enters with its saturation temperature. Water in the ethanol is expected to increase the CHF, so the correlation should be on the safe side for ethanol-water mixtures.
* 'gambill': superposition of Gambill (1963) of the CHF of pool boiling and the heat flux of forced convection, for any coolant. It uses the properties of the coolant mixture at saturation. On average it is 44 % below the ethanol measurements of Meyer et al.
* 'hall-mudawar': correlation of Hall and Mudawar (2000) for subcooled water in tubes of 0.25 to 15 mm diameter, evaluated with the properties of the coolant mixture at saturation and the hydraulic diameter of the channel. On the ethanol measurements of Meyer et al. it is too high by a factor of 0.8 dT_sub^0.25 / v^0.2 (subcooling in K, velocity in m/s), which is 1.6 on average and grows with subcooling. For coolants based on ethanol the result is divided by this factor, which reproduces the 38 tests as well as the 'meyer' correlation does. The correlation is not too high for water, so the corrected value is probably still on the safe side for ethanol-water mixtures. It is the only method which is tied to the ethanol measurements and also follows the mixture properties and the channel size.

The comparison of the three methods with the ethanol tests, including the correction factor of 'hall-mudawar', can be reproduced with 'ValidateCHF.py'.

What happens beyond the CHF is chosen with 'post_chf' in config.py:

* 'fallback': nucleate boiling is not counted on. A section whose mean heat flux at the channel bottom exceeds the CHF is solved again with forced
  convection only. This is the most conservative choice and gives an upper bound of the wall temperature as long as there is no film boiling: the
  wall gets much hotter than with boiling, and the coolant takes up less heat.
* 'meyer': the boiling curve continues beyond the CHF as measured for ethanol at high pressure by Meyer, Linne and Rousar (NASA TM-1998-206612,
  figure 6). Above 17 bar (250 psia) their tubes did not go into film boiling at the CHF: the wall temperature rose by 50 to 200 F, and the heat flux
  then kept rising with the wall temperature up to a second excursion at about 1.6 times the CHF (35 bar, 11 m/s, test 23). Below 17 bar the tubes went
  into film boiling and several burnt out. The measured branch is used face by face in the 2D section: up to the CHF of the section the heat flux
  follows nucleate boiling, then it stays at the CHF over a first excursion of 45 K and rises linearly by one CHF per 295 K of wall temperature.
  A section whose mean heat flux at the channel bottom exceeds 1.55 times the CHF is solved again with forced convection only, as with 'fallback'.
  Below 17 bar coolant pressure the treatment is the same as 'fallback'. Only valid for coolants based on ethanol.

The post-CHF branch comes from a single plotted test with SDA-3C ethanol (95 % ethanol, 5 % isopropyl alcohol) in a uniformly heated stainless steel
tube of 2.4 mm diameter. Meyer et al. describe the other tests above 17 bar as behaving the same way, with irregular wall temperatures and pitched sounds
from the test section, which can be a sign of flow instability. Water in the coolant, the rough rectangular channels heated from one side and other
velocities and subcooling are not covered by the measurements. Treat 1.55 times the CHF as a limit and do not design for it.

Sections beyond the CHF are listed at the end of the run and shaded in 'temperature.png': orange on the post-CHF branch, red where they were solved
again without boiling. The state of every section is saved in the last column of the csv file (0 below the CHF, 1 on the post-CHF branch, 2 solved
without boiling). The CHF correlations come from uniformly heated round tubes. A channel which is heated from one side has a higher heat flux at the
bottom than at the top and sides, so comparing its bottom wall with the CHF of a uniformly heated tube is still on the safe side.

Beyond the CHF the slope of the boiling curve changes abruptly, which can make the iteration of the 2D section cycle between two states. The boundary
condition of faces beyond the CHF is therefore linearised with the secant to the bubble point of the coolant instead of the tangent, and the
iteration is under-relaxed after 100 iterations as a safety net. Converged results do not depend on either.

### Wall Stress Analysis
For every section the temperature differences which drive the thermal stresses are taken from the 2D temperature field: the difference through the inner
wall at the centre line of the cooling channel and the mean temperatures of inner wall, ribs and outer wall. They are saved in the csv file and plotted
('wall_delta_T.png'). If the material has a yield strength in MaterialLib.py, 'StressAnalysis.py' estimates the elastic stresses at the hot gas side of
the inner wall for steady state firing, with the wall free of stress at ambient temperature:

* primary stresses (pressure): bending of the inner wall between two ribs under the pressure difference of coolant and hot gas (beam with fixed ends), and the hoop membrane stress of gas and coolant pressure carried by inner and outer wall together.
* secondary stresses (temperature): the hot inner wall is held back by the colder ribs and outer wall in axial and hoop direction (mismatch), and the temperature difference through the inner wall bends it (gradient). Both are compressive at the hot gas side and are combined to a von Mises equivalent stress.

With X = primary stress / yield strength and Y = secondary stress / yield strength (yield strength at the highest temperature of the hot gas side wall)
every section is classified in the Bree diagram: elastic (X + Y < 1), shakedown (Y < 2 and X + Y/4 < 1, yields in the first firings only), plastic cycling
(Y > 2 and X Y < 1, yields in every firing, life limited by low cycle fatigue) or ratcheting (the wall deforms further with every firing). The stresses
are plotted in 'stress.png', the Bree diagram with one point per section in 'bree.png', and a summary is printed at the end of the run.

This is a screening estimate and no replacement for a structural analysis. Sections do not interact, and loads from thrust, mounting and manifolds, the
start up and shut down transients, stress concentrations at the channel corners and creep are not included. The Bree diagram assumes an elastic - perfectly
plastic material with a constant yield strength. Wall temperatures of sections above the critical heat flux are not a prediction, and neither are their stresses.

### Using Material Library
Four common rocket engine chamber matierals can be selected from MaterialLib.py, 'Ti-6Al-4V', 'IN718', 'CuCr1Zr' and 'SS 1.4404'. These can be selected in config.py.
If a differnet material is desired, it can be added in MaterialLib.py, similar to the existing examples. Youngs modulus, poisson ratio, thermal expansion 
coefficient (mean value from ambient temperature), yield and ultimate strength can be set as functions of temperature with 'temperature_dependent'. 
The wall stress analysis needs all of them and is skipped for materials without a yield strength.


### Creating New Propellant Blends
In config.py any fuel and oxidiser present in the thermo database of [NASA CEA](https://github.com/nasa/cea) can be input by its species name, e.g. 'N2O', 'O2(L)' or 'C2H5OH(L)'. 
If a new propellant is desired, it can be created from its atoms and enthalpy of formation, as shown in the PropLibrary.py file. Several examples are already present of new chemicals, as well as propellant blends. 


## Returning cooling channels 
Some regeneratively cooled chamber designs feature cooling channles that first move along the chamber in one direction and return through another set of channels
along the coutour. In order to implement such a design feature in PyRocket, the simulation needs to be run twice. First, set the cooling geomety, with the full
number of channels (irrespecive of their direction) and double the coolant mass flow. This ensures both the appropriate coverage of the cooling channels, as well as 
the correct Reynolds number in the channels. By setting 'start_idx' in config.py to 0 the flow of coolant starts at the injector. Run this simulation. 
Using the results from the first run, 'start_idx' is set back to -1 (to start coolant flow at the nozzle) and the starting temperature and pressure of the coolant 
is set to the final values of the first simulation. The simulation can then be run again for the returning channels. The two simulation runs then provide a reasonably accurate 
estimates of the temperatures around both sets of cooling channels. 


## Optimisation and Parametric Sweeps 
PyRocket can be used to optimise a cooling channel geometry, as well as determining the impact of certain parameters on cooling performance. A sequential optimisation 
routine can be implemented using scipy.optimize.minimize. Using a Monte Carlo approach or parametric sweeps can be run in parallel using python multiprocessing. 
This approach is recommended in most cases as single case run times typically exceed 5 mins and are intrinsically difficult to parallelise. 

## Program Validation
PyRocket has been validated using data gathered on 22 N N2O/Hydrocarbon thrusters. Using data from nine steady state tests, an average total heat flux 
error of 8.3% with a standard deviation of 5.6% was determined. The wall temperature has been validated at discrete locations with a mean error of 11.2% and a standard deviation of 10%.
For Validation purposes the axial and radial coordinate of thermocouples along the camber can be set in config.py. The temperature at that location will then be displayed in the 
terminal output for the simulation. Set 'log_TC' to True to enable the output.  


## Common Issues

### Single section takes more than 10 seconds to solve

This only applies to transient simulations with a set 'run_time'. The steady state is solved directly without time stepping: the boundary conditions are 
part of the equation and the temperature dependent coefficients are updated between the solves until the temperature field stops changing. 

With a run time the section is marched in time from ambient temperature ('transient' in 'SectionThermalSim.py'). The boundary conditions are implicit in the wall temperature as in the steady state, so the solution can not oscillate. The time step starts at 'time_step' and grows by the factor 'adaptive_up' to at most 1/50 of the run time, so a section takes about 60 solves (about 1 s). A full transient run takes 2 to 3 minutes; sections above the critical heat flux are solved twice. If this is too slow, increase 'cell_size' or set 'save_fig' to False.

### Coolant is boiling

The coolant properties are calculated with [CoolProp](http://www.coolprop.org/) in 'CoolantClass.py'. Two-phase flow is not modelled, so the simulation 
stops with a ValueError once the coolant reaches its bubble point. Increase the coolant pressure or mass flow, or reduce the heat load. 
This is about the bulk of the coolant, boiling at the walls of the cooling channels is covered by the nucleate boiling model. With the boiling model
switched on the simulation does not stop: the coolant is kept just below its saturation temperature as a liquid and a warning is given at the end of
the run. Results downstream of this point are not valid.
For mixtures CoolProp only provides density, heat capacity and the boiling range. Viscosity and thermal conductivity are mixed from the pure fluid 
values, with a correction for the high viscosity of ethanol-water mixtures. Other strongly non-ideal mixtures need their own correction in 'CoolantClass.py'


    
