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

### Channel splits
The number of channels can change along the chamber, e.g. fewer channels around the throat, where the circumference is small and the channels
would otherwise become too narrow to print, and more channels in the chamber and the nozzle, where they are wider. In the desktop app the
'Channel splits' table on the Cooling tab lists the changes as the axial position x and the number of channels from there on towards the nozzle
exit; 'Number of channels' is the number at the injector end. In config.py 'n' can be a function of the axial coordinate like 'h_c' and 'psi'.
Every section is solved with the number of channels at its position. The fill factor 'psi' keeps its meaning, so where the number of channels
doubles each channel and rib is half as wide: the flow area stays the same, the hydraulic diameter becomes smaller, and the coolant velocity,
Reynolds number and heat transfer coefficient follow from it. The change takes place between two sections. The flow in the junction itself, where
a rib starts in the middle of a channel or ends between two, is not modelled: neither its pressure loss nor the new thermal boundary layer on the
new rib. Each channel should split into a whole number of channels (e.g. 15 into 30, not 20 into 30); a warning is shown otherwise. In
'sections_3d.html' each run of sections with the same number of channels is drawn on its own.

The STEP model includes the splits, which need a whole number of channels from each channel. The ribs lie on one grid of angles, so the ribs of the
fewer channels run through the transition and the others start (or end) in the middle of a channel. Over 'Split transition' (5 mm by default,
rounded to whole steps of the thermal model and shorter where the next split or the end of the chamber is closer) the new ribs grow from a blunt
leading edge, 5 % of their width, to their full width, their corner fillets with them, and the ribs that run through narrow just as fast. The
channels beside a new rib keep the width they have after the split all through the transition, so the channel divides gradually without pinching.
The transition starts at the first section of the thermal model with the more channels (or ends at the last one, where the channels merge) and
lies on that side, so no channel of the STEP model is narrower than the channels the thermal model checks against 'min_channel_size'; a note
says so if one is narrower anyway. A channel that divides is one body in the model. The thermal model itself does not include the transition.

The ribs, channels and walls are lofted in pieces, one for every transition and one for each stretch between them: a single loft through the
closely spaced sections of a transition and the sections of the thermal model swings far out of the chamber wall. The pieces are fused into
one body each. The walls are lofted through circles in the same pieces so that the ribs and channels fit them, to within about 0.02 mm.


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
contour in 3D: the wall with all cooling channels of the chamber and their ribs, coloured by temperature. The wall is transparent so the cooling
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

### Creep Rupture Screening
For materials with a Larson-Miller curve in materials.py, 'creep.py' screens every section for creep rupture under the primary stresses, at the
highest temperature of the hot gas side wall and for the total firing time (firing time x number of firings, set with the wall material):

* The stress rupture data are a Larson-Miller curve, LMP = T (C + log10 t_r) with T in K and the time to rupture t_r in hours, interpolated
  linearly in log(stress). A factor on the rupture stress takes printed parts from data of wrought material.
* Creep relaxes the peak of the elastic bending stress, so the rupture is governed by the reference stress of the limit load (R5 method):
  sig_ref = sig_bend / 4 + sqrt(sig_bend^2 / 16 + sig_membrane^2) for the inner wall as a beam with fixed ends (hinges at both ends and in the
  middle, interaction M / M_p + (N / N_p)^2 = 1). That is half the elastic bending stress for bending alone.
* The life fraction (Robinson's rule) is the total firing time over the time to rupture, rupture at 1. Its scatter is large: a factor of 10 in life
  is common for creep data, and more for printed material, so a life fraction above about 0.1 deserves attention.

The data cover tens to hundreds of hours, while small engines fire for seconds to minutes. Outside the stresses of the data the curve is extended with
the slope of its ends, and the sections are flagged in the csv file and shaded in 'creep.png'. Towards high stresses the rupture stress goes no further
than the short time tensile strength where the library has it over temperature (IN718, GRCop-42), and no further than the highest stress of the data
otherwise, so that a section above it ruptures at once. Where the rupture life is extrapolated to long times the result reads as "no creep concern",
not as a life.

| Material | Data | C | Printed parts |
|---|---|---|---|
| IN718 | wrought bar, annealed and aged, 593 to 760 C, 100 and 1000 h (Rolled Alloys alloy 718 bulletin) | 20 | 0.9 x stress, estimate |
| GRCop-42 | extruded, 500, 650 and 800 C, 2.5 to 850 h (Gradl et al., AIAA-2019-4228, figure 11) | 15.5, fitted | 0.9 x stress, estimate |
| CuCr1Zr | ITER grade sheet, 500 C only, 4.7 to 530 h (Wang et al., Mater. Sci. Eng. A 2020, ORNL) | 20, assumed | 0.9 x stress, estimate |
| SS316L, SS14404 | L-PBF 316L, 550 to 650 C, 175 to 300 MPa (Wang et al., J. Nucl. Mater. 2021, ORNL) | 17 | data are of printed parts |

No creep data were found that could be trusted for printed Ti-6Al-4V and AlSi10Mg, they are not screened. The CuCr1Zr curve is the least reliable:
the data are of one temperature, and CuCrZr overages and softens above about 400 C, so its creep strength changes faster with temperature than a
single Larson-Miller curve can show. Creep under the thermal (secondary) stresses is not part of the rupture screening: they relax by creep while
the engine runs and reverse at shut down, which thins and bulges the inner wall over many firings (the "doghouse" failure of regeneratively
cooled chambers). This is checked separately, see below.

### Thermal Ratcheting and Cyclic Life
The thermal stresses are set by a strain, not a load: the hot inner wall is held back by the colder closeout, yields in compression when firing,
relaxes by creep, and yields in tension at shut down. On their own they do not rupture the wall within a firing, but the pressure biases every
cycle, so the wall between the ribs (the ligament) bulges into the chamber and thins at the middle of the channel a little with every firing, until
it necks or cracks. The life is a number of firings, not hours. For materials with creep rates and a fatigue curve in materials.py, 'ratchet.py'
checks this in two independent ways for every section, with the firing time and the number of firings of the wall material:

1. **Elastic core stress** (O'Donnell and Porowski, as test B-1 of ASME III Division 5, HBB-T-1332). The Bree model (membrane primary stress, linear
   thermal stress) has an elastic core in the middle of the wall whose stress Z sets the creep ratcheting. With X = (membrane + bending / 1.25) /
   S_y and Y = secondary stress range / S_y, S_y the mean of the yield strengths of the hot and the cold end of the cycle: Z = X in the elastic
   regime (X + Y <= 1), Z = 1 + Y - 2 sqrt((1 - X) Y) in regime S1 ((1 - X) Y <= 1) and Z = X Y in regimes S2 and P; Z >= 1 is plastic
   ratcheting (Porowski and O'Donnell, *Creep ratcheting bounds from extended elastic core concept*, ORNL, OSTI 6027412). The core stress is
   Z x S_y of the cold end; its creep strain at 1.25 times that stress, with the minimum creep rate at the highest wall temperature over all
   firings, is compared with the 1 % strain limit of the base metal. The result is the number of firings to 1 % ratchet strain.
2. **Ligament life** (Porowski, O'Donnell, Badlani et al., NASA CR-165585 (1981) and NASA CR-168261 (1983), J. Spacecraft and Rockets 22 (1985)).
   The ligament is a beam of thickness 2H over the channel width, held by the closeout through the ribs. The hoop plastic strain range is the
   thermal mismatch of ligament and closeout less twice the yield strain, plus the stress relaxed by creep in the firing (all of it above 1000 psi
   pressure difference, Norton relaxation below), plus a correction for the bending of the temperature gradient. Both halves of the cycle bend
   the ligament the same way, with a curvature of strain / H from the normality of the yield surface m + n^2 = 1; with the shear of the
   pressure and the creep deflection of a clamped beam this gives the deflection and the thinning per firing (linear thinning model). The life
   is the first of tensile instability of the thinned ligament (thickness 2H exp(-q), q = 0.2 (S_u / S_y - 1)^0.6) and fatigue plus creep rupture
   damage summed over the firings as the ligament thins (local strain range at the thinnest section, creep rupture under the bending stress at
   the middle of the channel when it redistributes within a firing). The implementation reproduces the worked examples of both reports
   (NARloy-Z at 3000 psi: 0.0145 plastic strain and 0.000146 in thinning per cycle, 49 cycles to instability; OFHC copper at 547 psi: 103 cycles).

The ligament model takes the largest mismatch of ligament and closeout over the cycle. The thermal model only has the steady state, and at start up
the inner wall heats within about a second while the closeout lags, so the peak mismatch can be several times the steady one (in the NASA test
chambers it was the transient that mattered). The ligament life is therefore given twice: for the steady state, and as a start-up bound with the
inner wall at its steady temperature and the closeout still at the temperature at shut down. The real start up lies between the two, closer to the
bound the thicker and less heated the closeout is; a transient thermal analysis would be needed to place it. For a 1 kN N2O / ethanol chamber in
GRCop-42 with a hot printed closeout the steady state gave a mismatch of 0.09 % (no yielding, life far beyond the fatigue data) and the bound 0.47 %
(about 270 firings), which shows how much the answer depends on the start up.

The two are complementary rather than two estimates of the same number. The core stress check bounds the creep ratcheting under a membrane primary
stress and sees no ratcheting in the plastic cycling regime of Bree (Y > 2, X Y < 1). The ligament model has the pressure as a bending stress and a
membrane thermal strain that cycles beyond yield, which ratchets at any pressure difference. Where the inner wall stays elastic they agree that the
life is long; where it yields in every firing the ligament life governs. Both are simplified bounds for screening: hardening that slows the thinning
(as in NARloy-Z) is not credited, the creep laws have no primary creep, and fatigue lives scatter by a factor of 2 to 3. Results are written to the csv
file, plotted in 'life.png' and printed at the end of the run; sections where a creep law or fatigue curve is extrapolated are flagged.

| Material | Creep rates | Fatigue (total strain range) |
|---|---|---|
| IN718 | wrought, heat treatment A, 650 to 760 C (Hayes, Superalloys 1991, table III) | wrought, 360, 550 and 650 C, Manson-Coffin-Basquin fits (Xie, Superalloys 1991, table IV) |
| GRCop-42 | extruded, 500, 650 and 800 C (Gradl et al., AIAA-2019-4228, figure 10) | wrought, RT to 600 C pooled (same paper, figure 2) |
| CuCr1Zr | 216 and 300 C laws (Li, Thomas, Stubbins, Metall. Mater. Trans. A 2000, table II), 500 C (Wang et al. 2020, ORNL) | SAA, RT to 500 C, Coffin-Manson fit (Zhang, Gaganidze, Gorley, CuCrZr material property handbook) |
| SS316L, SS14404 | L-PBF, 550 to 650 C (Wang et al. 2021, ORNL, figure 6) | wrought austenitic steels in air, RT to about 400 C (NUREG/CR-6909) |

For CuCr1Zr and the 316L grades the library now also holds the yield and ultimate strength over temperature (CuCrZr: average fits of the handbook
above; 316L: as built L-PBF along the build direction, Dryepondt et al., Addit. Manuf. 2021, ORNL), and for 316L the modulus and thermal expansion
of EN 10088-1, so the wall stress analysis runs for them as well. The liner temperatures of small engines are often below the test temperatures of
the creep data; the rates are then extrapolated in 1 / T and flagged. The CuCrZr lots differ in heat treatment, so its temperature dependence is
the least certain, and the 500 C fatigue tests of CuCrZr lie a factor of 2 to 3 below its fit.

### Throttling
'throttle.py' analyses a finished design while throttling. The contour stays, and an operating point is a chamber pressure and a core O/F.
The rest follows from these two, and the thermal model runs on each point unchanged:

* The mass flow through the throat is that of the design times Pc / Pc_design times c*_design / c*, with the c* of CEA at the point and the c* efficiency of the design. A fuel rich point with a lower c* needs more flow for the same chamber pressure.
* The split into oxidiser, fuel and film is the mass budget at the new core O/F with the film fractions of the design. The injection velocity of the films follows the fuel feed, as the orifices are fixed.
* The throttle valve is taken to be upstream of the channels, so the jacket pressure falls with the chamber pressure: p_inlet = Pc + dp_design (feed / feed_design)^2, the fuel injector and the channels acting as one fixed area with the pressure drop of the design point (coolant inlet pressure less chamber pressure). A staged injector has less area at low flow, so this is the lowest pressure the jacket can see. 'jacket_inlet_pressure' is the place for the curve of a real injector.

The O/F schedule is not an input, it is read off a map: every chamber pressure of 'pc_fractions' is solved with every O/F of 'of_ratios' (8 steps from the design
O/F towards fuel rich by default). A point keeps the limits if no section fails (above 17 bar of coolant pressure the post-CHF branch can be used up to 1.55 times
the CHF, below 17 bar every section above the CHF fails), the coolant itself does not reach saturation, and its subcooling stays above 'min_subcooling' (20 K, about
the lowest of the ethanol CHF tests). 'allow_post_chf' set to False also rejects the post-CHF branch. The schedule takes the highest O/F which keeps the limits
at each chamber pressure, and a point must also be rich enough for the next point down, because O/F is interpolated between them in operation. Otherwise the
engine would reach the next point too lean, which matters most where the coolant falls below 17 bar and the post-CHF branch ends. The design point keeps the design O/F
if it keeps the limits. A schedule of your own can be added with 'schedule' as (chamber pressure fraction, O/F) points, and is solved with the others.

The map is solved twice, with the film as modelled and without credit for it: same flows and pressures, but the wall does not see the film. This bounds the result and
is not an option to leave out. Going fuel rich extends the liquid film a long way, for the 600 N example it reaches the throat at O/F 2.8 and the end of the nozzle at about 2.2, while the
model is not validated at and downstream of the throat. On the map of that engine the deepest points need O/F 2.8 with film credit and 2.0 without, so the
film decides the schedule. The true limit lies between the two until hot fire data places the film. The map runs on a coarse mesh ('map_step_size',
'map_cell_size_factor'), and the schedules are solved again on the mesh of the design.

Each result in 'throttle_map.csv' and 'throttle_schedule.csv' has the thermal limits, the stress and life results, and an estimate of the thrust with attached flow, scaled to the thrust of
the design. 'stiffness_fuel' and 'stiffness_ox' are the injector pressure drop over chamber pressure relative to the design point, for one fixed area and an incompressible
liquid. They are rough for nitrous oxide, but show which side loses its stiffness first: going fuel rich helps the fuel side and takes it away from the oxidiser side. The terminal table
notes the points where the film passes the throat, the throat coolant velocity is below the 3 m/s of the CHF tests, most sections are below Re = 2300 (where 'gnielinski-rough' holds the
heat transfer of Re = 2300, which is optimistic), the coolant is below 17 bar, or the exit pressure is below 40 % of ambient pressure.

Not included: the c* efficiency stays that of the design, although it will usually fall with low injector pressure drop and fuel rich mixtures; the film fractions stay those of the design,
although staging an injector changes the split; the sections are steady state, so transients between throttle points and the start of the second stage are not covered; nozzle
flow separation is only flagged, and coking, soot, ignition and combustion stability of fuel rich mixtures are outside this model.

### Using Material Library
Four common rocket engine chamber matierals can be selected from MaterialLib.py, 'Ti-6Al-4V', 'IN718', 'CuCr1Zr' and 'SS 1.4404'. These can be selected in config.py.
If a differnet material is desired, it can be added in MaterialLib.py, similar to the existing examples. Youngs modulus, poisson ratio, thermal expansion 
coefficient (mean value from ambient temperature), yield and ultimate strength can be set as functions of temperature with 'temperature_dependent'. 
The wall stress analysis needs all of them and is skipped for materials without a yield strength. The creep rupture screening needs a Larson-Miller
curve, set as `material.creep = LarsonMiller(C, LMP, stress, factor)` (see creep.py), and only the pressures and the geometry otherwise.
The ratcheting and cyclic life checks need the yield and ultimate strength, the Larson-Miller curve, minimum creep rates as
`material.norton = NortonCreep({T: (stresses, rates)})` and a strain controlled fatigue curve as
`material.fatigue = FatigueCurve({T: strain_range_of_cycles}, N_range)` (see ratchet.py).


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


    
