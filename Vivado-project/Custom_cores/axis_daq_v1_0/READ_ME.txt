#Content of this folder is "DAQ core" that should replace "Averager core" in Vivado project Red Pitaya FPGA Project 5 – High-Bandwidth Averager
#This project could be found described in more detail here:"http://antonpotocnik.com/?p=514765" with repository accesible from:"https://github.com/apotocnik/redpitaya_guide/tree/master/projects/5_averager"

#1)In the first step create copy of repositary "https://github.com/apotocnik/redpitaya_guide somewhere in your PC
#2)In order to be able to sucessfully generate and use DAQ core => copy this folder "axis_daq_v1_0" (containing files: "axis_daq.v", "core_config.tcl") 
# to "../redpitaya_guide/cores/"
#3)Follow the instructions from website Project 5 – High-Bandwidth Averager ("http://antonpotocnik.com/?p=514765") and generate 5_averager project.
# Do not forget to modify "make_project.tcl" file!!
#4)In this step all the project cores should be allready sucessfuly generated. That was done via command "source make_cores.tcl" inside Vivado (path "R
../redpitaya_guide" basically where "make_cores.tcl" file is)
#5)Open the newly generated project in Vivado and replace "Averager core" with now accessible "DAQ core".
