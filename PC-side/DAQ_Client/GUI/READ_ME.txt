# TO START DAQ client app use following command:
# 'python3 DAQ_Client_GUI.py'

# USAGE:
#1) fill setup, change valid ip address or hostname and port(default 1001)
(IF LINUX IS USED THEN in function RP_Config_Linux(event): change --working-directory='/Path' to path where is your "DAQ_RedPitaya/Config_scripts/Linux/bin/RP_DAQ_CONNECT" located -> no need to manualy start server and load bitstream) 
#2) open file for data storing 
# (if no file is selected, script will create a file after 'start measuring' is initiated. File will be named as current time and date)
#3) start measuring 
#4) stop measuring
