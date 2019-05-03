#Written by Radim Pavlík
#Run in python3 

from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter.filedialog import askopenfilename


import time
import struct
import socket
import sys
import numpy

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import os




UseFile = None
FileOpened = False
SocketCreated = False
MeasuringIsRunning = False
RequestSend = False



BUFFER_SIZE = (65536*2) # #4096

# time stamps
time_old = 0
time_new = 0

recv_counter =0


def open_file(event):
	global UseFile
	global FileOpened
	name = askopenfilename(initialdir="/C:/",
												 filetypes =(("Binary File", "*.bin"),("All Files","*.*")),
												 title = "Choose a file."
												)

	print("Chosen file: ",name)
	UseFile = open(name,'wb')
	FileOpened = True  

def handle_nonblocking_socket():
	global BUFFER_SIZE
	global RequestSend
	global time_old
	global time_new 
	global recv_counter

	draw_graph_every_X_rep =200

	try:
		data = s.recv(BUFFER_SIZE, socket.MSG_DONTWAIT)
		if (data > bytes(0)):
			time_old = time_new
			time_new = time.time()
			recv_counter = recv_counter + 1
			#print("Time before two data blocks received : " +str(time_new - time_old) )
			
			#store received data
			UseFile.write(data)
			RequestSend = False
			if (recv_counter >= draw_graph_every_X_rep):
				recv_counter = 0
				VisualizationDataPlot(data)

		else:
			print("0-bytes received")
	except socket.error:
		return None

def VisualizationDataPlot(dataString_to_plot):
	global PlotFigure
	global PlotAxis
	global PlotLine
	global XAxis_max
	global converted_data
	global Persistance
	global time_old
	global time_new  

	#get value from voltage conversion coefficient
	V_coefficient = int(VoltageConversionCoefficient.get())
	converted_data = numpy.fromstring(dataString_to_plot, dtype=numpy.int16)
	print(str(time_new - time_old),";",converted_data.size )
	if (Persistance.get() != True):	
		PlotAxis.clear() 
	converted_data = (converted_data/V_coefficient)+(int(VoltageOffset.get()))
	casy_k_ose = numpy.arange(0,(float(TimeConversionCoefficient.get())*converted_data.size),float(TimeConversionCoefficient.get()))

	PlotAxis.plot(casy_k_ose,converted_data)
	PlotAxis.axes.set_xlim(0,XAxis_max)
	PlotAxis.axes.set_ylim(int(Yosamin.get()),int(Yosamax.get()))
	PlotAxis.set_title('Received Data Visualisation')
	PlotAxis.set_ylabel("Voltage [mV]")
	PlotAxis.set_xlabel("Time [uS]")
	PlotLine.draw()
	
	

def receive_measurement():
	global UseFile
	global FileOpened

	if FileOpened:
		handle_nonblocking_socket()
	else:
		#print("File for data storing is not opened!")
		return None



def close_file():
	global UseFile
	global FileOpened

	if UseFile is not None:
		UseFile.close()
		FileOpened = False
		print("File closed") 
	
def start_measuring(event):
	global FileOpened
	global SocketCreated
	global Force

	if not FileOpened:
		print("No file opened for data storing!")
		create_new_file()

	print("Starting connection")
	if (SocketCreated == False):
		create_socket()
	socket_created = True
	decode_rpIP_addr()
	connect_to_rp()
	send_set_configuration()
	send_measure_request()
	continuous_measurement()
		

def create_new_file():
	global FileOpened
	global UseFile
	print("Creating new file: formatted %Y%m%d-%H%M%S")
	filename = time.strftime("%Y%m%d-%H%M%S")
	print("filename: "+ filename+".bin")
	UseFile= open(filename+".bin","wb")
	FileOpened = True


def create_socket():
	global s 
	try:
		s = socket.socket( socket.AF_INET, socket.SOCK_STREAM) #IPV4 , TCP
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)#
	except socket.error:
		print("Failed to create socket TCP / IPV4")

def decode_rpIP_addr():
	global remote_ip
	global port
	global host

	host = IPEntry.get()  
	port = int(PortEntry.get())
	try:
		remote_ip = socket.gethostbyname(host)
	except socket.gaierror:
		print("Hostname could not be resolved")

def connect_to_rp():
	global host
	global remote_ip
	global port
	global s
	global StatusLabel

	s.connect((remote_ip, port))
	print("Socket Connected to " + host + " using IP " + remote_ip + " by port " + str(port))
	StatusLabel = Label(root, text = 'Online', font=("Helvetica, 16"), fg="green")	
	StatusLabel.grid(row=0,column =3,sticky=E)	
	

def send_set_configuration():
	global s
	global ForcedTrigger #Forced trigger
	global SecondChannel #CH2 selection

	Trigger = int(TrigEntry.get()) # osetrit rozsah moznosti! if Trigger v intervalu jinak error a zavřit spojeni
	TriggerLvL_converted = int(Trigger*int(VoltageConversionCoefficient.get()))
	PreTrigger = int(PreTrigEntry.get())  #
	
	print("Trigger pred konverzi je" +(TrigEntry.get()))
	print("Trigger po konverzi je" + str(TriggerLvL_converted))
	print("PreTrigger po konverzi je" + str(PreTrigger))
	print("ForcedTrigger je" +str(ForcedTrigger.get()))
	print("CH2 selekce je" +str(SecondChannel.get()))
	
	#print(struct.pack('<I', 1<<29 | Trigger)) #Varianta pro unsigned int

	#PreTrigger = struct.pack('<h',PreTrigger)
	#PreTriggerFlag = struct.pack('<H',2<<13) # po zmene rozsahu prikazu (3bity) nutne shift pouze o 13 => vice moznosti

	Trigger = struct.pack('<h',TriggerLvL_converted)
	TriggerFlag = struct.pack('<H',1<<13)
	

	#PreTrig= b"".join([PreTrigger, PreTriggerFlag]) #Vysledek 32bit cislo pro signed int
	Trig = b"".join([Trigger, TriggerFlag])          #Vysledek 32bit cislo = index ramce a 16bit sign hodnota 
	
	#vytisknout
	#print(Trig)
	#print(PreTriggerFlag)

	s.send(struct.pack('<I', 2<<29 | PreTrigger)) # pro unsigned int
	s.send(Trig) # slozena signed int varianta
	s.send(struct.pack('<I', 4<<29 | int(SecondChannel.get())))
	s.send(struct.pack('<I', 5<<29 | int(ForcedTrigger.get())))
		
	
	print("Configuration sended to RP server")

def close_connection(event):
	global s
	global StatusLabel

	s.send(struct.pack('<I', 3<<29))
	print("Zaviram spojeni:")
	print(s)
	SocketCreated = False # test
	close_file()
	SHUT_RD = socket.SHUT_RD
	s.shutdown(SHUT_RD)
	s.close()
	print("Connection to server closed")
	StatusLabel = Label(root, text = 'Offline', font=("Helvetica, 16"), fg="red")
	StatusLabel.grid(row=0,column =3,sticky=E)

def send_measure_request():
	global s
	global RequestSend
	s.send(struct.pack('<I', 0<<29))
	#if s.send valid then : RequestSend = True
	RequestSend = True
	#print("measure request sended")  

def continuous_measurement(force = True):
	global MeasuringIsRunning
	global RequestSend

	if force:
		MeasuringIsRunning=True
	if MeasuringIsRunning:
		#if request not send then:  send_measure_request()
		if not RequestSend:
			send_measure_request()
			#
		if RequestSend: 
			receive_measurement()
		root.after(1, continuous_measurement, False) #Callback on self

def X_axis_increment(event):
	global PlotLine
	global PlotAxis
	global PlotLine
	global XAxis_max
	global Step
	Step = int(XosaStep.get())
	#increment X axis limit
	XAxis_max = XAxis_max+Step
	PlotAxis.set_title('Received Data Visualisation')
	PlotAxis.axes.set_xlim(0,XAxis_max)
	PlotAxis.axes.set_ylim(int(Yosamin.get()),int(Yosamax.get()))
	PlotLine.draw()
	#print("X-axis incemented "+str(Step))	

def X_axis_decrement(event):
	global XosaStep
	global PlotLine
	global PlotAxis
	global PlotLine
	global XAxis_max	
	global Step
	Step = int(XosaStep.get())
	#decrement X axis limit
	XAxis_max = XAxis_max-Step
	PlotAxis.set_title('Received Data Visualisation')
	PlotAxis.axes.set_xlim(0,XAxis_max)
	PlotAxis.axes.set_ylim(int(Yosamin.get()),int(Yosamax.get()))
	PlotLine.draw()
	#print("X-axis decremnted "+str(Step))

def Axis_update(event):
	global PlotLine
	global PlotAxis
	global PlotLine
	global XAxis_max
	#PlotAxis.set_title('Received Data Visualisation')
	PlotAxis.axes.set_xlim(0,XAxis_max)
	PlotAxis.axes.set_ylim(int(Yosamin.get()),int(Yosamax.get()))
	PlotLine.draw()
		

def RP_Config_Linux(event):
	global ConfigStatusLabel
	global ConfigStatus_var
	os.system("gnome-terminal.real --name='DAQ-server-ON' --working-directory='/home/redpitaya/Desktop/DAQ_RedPitaya_GIT/DAQ_RedPitaya/Config_scripts/Linux/bin/' --command './RP_DAQ_CONNECT'")
	#os.system("gnome-terminal.real --name='DAQ' --working-directory='/home/redpitaya/Desktop/DAQ_RedPitaya_GIT/DAQ_RedPitaya/PC-side/DAQ_Client/GUI' --command 'python3 test.py'")
	#ConfigStatus_var.set("RP-server-ON")

def Clear_plot(event):
	global PlotAxis
	global PlotLine
	PlotAxis.clear()
	PlotAxis.set_title('Received Data Visualisation')
	PlotAxis.set_ylabel("Voltage [mV]")
	PlotAxis.set_xlabel("Time [uS]")
	PlotLine.draw()

def TestValue(event):
	global Persistance
	print(Persistance.get())

root = Tk() #main window
root.title("DAQ-client-app")

frame= Frame(root)



Label(root, text="Trigger Level [mV]:").grid(row=0, column=1, sticky=W, padx=5)
TrigEntry = Entry(root)
TrigEntry.grid(row=0,column=2, sticky=E,pady=4)
TrigEntry.delete(0,END)
TrigEntry.insert(0, "500")

Label(root, text="PreTrigger Length (num of samples):").grid(row=1,column=1, sticky=W, padx=5)
PreTrigEntry = Entry(root)
PreTrigEntry.grid(row=1,column=2, sticky=E,pady=4)
PreTrigEntry.delete(0,END)
PreTrigEntry.insert(0, "5")

Label(root, text="RP (IP address or hostname):").grid(row=2,column=1, sticky=W, padx=5)
IPEntry = Entry(root)
IPEntry.grid(row=2,column=2, sticky=E,pady=4)
IPEntry.delete(0,END)
IPEntry.insert(0, "10.42.0.203")

Label(root, text="RP (server port):").grid(row=3,column=1, sticky=W, padx=5)
PortEntry = Entry(root)
PortEntry.grid(row=3,column=2, sticky=E,pady=4)
PortEntry.delete(0,END)
PortEntry.insert(0, "1001")

OpenButton = Button(root,text="Open file:")
OpenButton.grid(row=4, column=1, sticky=W)
OpenButton.bind("<Button-1>", open_file)

ConfigButton = Button(root,text="Config-RP-Server LINUX")
ConfigButton.grid(row=4, column=2, sticky=W)
ConfigButton.bind("<Button-1>", RP_Config_Linux)

#ConfigStatus_var = StringVar()
#ConfigStatus_var.set("RP-server-OFF")

#ConfigStatusLabel = Label(root, textvariable = ConfigStatus_var, font=("Helvetica, 16"), fg="red")
#ConfigStatusLabel.grid(row=4,column =3,sticky=E)

StopButton = Button(root,text="Stop Measuring")
StopButton.grid(row=6, column=1, sticky=W)
StopButton.bind("<Button-1>", close_connection)

StartButton2 = Button(root,text="Start Measuring")
StartButton2.grid(row=7,column=1, sticky=W)
StartButton2.bind("<Button-1>", start_measuring)

StatusLabel = Label(root, text = 'Offline', font=("Helvetica, 16"), fg="red")
StatusLabel.grid(row=0,column =3,sticky=E)

PlotFigure = plt.Figure(figsize=(7,5), dpi =100)
PlotAxis = PlotFigure.add_subplot(111)
PlotLine = FigureCanvasTkAgg(PlotFigure, root)
PlotLine.get_tk_widget().grid(row=0,column=0, rowspan= 16, pady=4, padx=4)
PlotAxis.set_title('Received Data Visualisation')
XAxis_max = 100
PlotAxis.axes.set_xlim(0,XAxis_max)
PlotAxis.axes.set_ylim(-1100,1100)
PlotAxis.set_ylabel("Voltage [mV]")
PlotAxis.set_xlabel('Time [uS]')
#PlotAxis.plot([0.1,0.5,1,2,3,4,5,6,7,8])


XosaplusButton = Button(root,text="X axis+")
XosaplusButton.grid(row=8, column= 3, sticky=W)
XosaplusButton.bind("<Button-1>", X_axis_increment)

XosaminusButton = Button(root,text="X axis-")
XosaminusButton.grid(row=8, column= 4, sticky=W)
XosaminusButton.bind("<Button-1>", X_axis_decrement)

Label(root, text="X axis step:").grid(row=8, column=1, sticky=W, padx=5)
XosaStep = Entry(root)
XosaStep.grid(row=8,column=2, sticky=E,pady=4)
XosaStep.delete(0,END)
XosaStep.insert(0, "10")

Label(root, text="Y axis min:").grid(row=9, column=1, sticky=W, padx=5)
Yosamin = Entry(root)
Yosamin.grid(row=9,column=2, sticky=E,pady=4)
Yosamin.delete(0,END)
Yosamin.insert(0, "-1100")

Label(root, text="Y axis max:").grid(row=10, column=1, sticky=W, padx=5)
Yosamax = Entry(root)
Yosamax.grid(row=10,column=2, sticky=E,pady=4,padx=4)
Yosamax.delete(0,END)
Yosamax.insert(0, "1100")


XosaminusButton = Button(root,text="Update Axis setup")
XosaminusButton.grid(row=11, column= 1, sticky=W)
XosaminusButton.bind("<Button-1>", Axis_update)

PlotClearButton = Button(root,text="Clear Plot")
PlotClearButton.grid(row=12, column=1, sticky=W)
PlotClearButton.bind("<Button-1>", Clear_plot)

Persistance= IntVar()
PersistanceChButton = Checkbutton(root, text="Persistance", variable=Persistance, onvalue=True, offvalue=False)
PersistanceChButton.grid(row=11,column=2, sticky=W, padx=4)

ForcedTrigger= IntVar()
ForcedTriggerChButton = Checkbutton(root, text="Forced Trigger", variable=ForcedTrigger, onvalue=True, offvalue=False)
ForcedTriggerChButton.grid(row=6,column=2, sticky=W)

SecondChannel= IntVar()
SecondChannelChButton = Checkbutton(root, text="Second Channel (CH2)", variable=SecondChannel, onvalue=True, offvalue=False)
SecondChannelChButton.grid(row=7,column=2, sticky=W)

Label(root, text="Voltage conversion coefficient \n(14bit sign int Range/2)/1000 [mV]:").grid(row=13, column=1, sticky=W, padx=5)
VoltageConversionCoefficient = Entry(root)
VoltageConversionCoefficient.grid(row=13,column=2, sticky=E,pady=4)
VoltageConversionCoefficient.delete(0,END)
VoltageConversionCoefficient.insert(0, "8")


Label(root, text="Voltage Y-Axis offset +/- [mV] :").grid(row=14, column=1, sticky=W, padx=5)
VoltageOffset = Entry(root)
VoltageOffset.grid(row=14,column=2, sticky=E,pady=4)
VoltageOffset.delete(0,END)
VoltageOffset.insert(0, "0")

Label(root, text="Time conversion coefficient\n (1/RP_samplFreq)*100 [uS]:").grid(row=15, column=1, sticky=W, padx=5)
TimeConversionCoefficient = Entry(root)
TimeConversionCoefficient.grid(row=15,column=2, sticky=E,pady=4)
TimeConversionCoefficient.delete(0,END)
TimeConversionCoefficient.insert(0, "0.008")

TestButton = Button(root,text="TestButton")
TestButton.grid(row=16, column=1, sticky=W)
TestButton.bind("<Button-1>", TestValue)


root.mainloop()
C