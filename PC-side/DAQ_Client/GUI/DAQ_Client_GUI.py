#Written by Radim Pavlík

from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter.filedialog import askopenfilename


import time
import struct
import socket
import sys




UseFile = None
FileOpened = False
SocketCreated = False
MeasuringIsRunning = False
RequestSend = False

BUFFER_SIZE = (65536*2) # #4096

# time stamps
time_old = 0
time_new = 0




def open_file(event):
	global UseFile
	global FileOpened
	name = askopenfilename(initialdir="/C:/",
												 filetypes =(("Binary File", "*.bin"),("All Files","*.*")),
												 title = "Choose a file."
												)

	print (name)
	UseFile = open(name,'wb')
	FileOpened = True  

def handle_nonblocking_socket():
	global BUFFER_SIZE
	global RequestSend
	global time_old
	global time_new 

	try:
		data = s.recv(BUFFER_SIZE, socket.MSG_DONTWAIT)
		if (data > bytes(0)):
			time_old = time_new
			time_new = time.time()
			print("Time before two data blocks received : " +str(time_new - time_old) )
			#store received data
			UseFile.write(data)
			RequestSend = False
		else:
			print("0-bytes received")
	except socket.error:
		return None


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

	s.connect((remote_ip, port))
	print("Socket Connected to " + host + " using IP " + remote_ip + " by port " + str(port))
	StatusLabel = Label(root, text = 'Online', font=("Helvetica, 16"), fg="green")	
	StatusLabel.grid(row=0,column =2,sticky=E)	
	

def send_set_configuration():
	global s
	Trigger = int(TrigEntry.get()) # osetrit rozsah moznosti! if Trigger v intervalu jinak error a zavřit spojeni
	PreTrigger = int(PreTrigEntry.get())  #
	
	print("Trigger po konverzi je" + str(Trigger))
	print("PreTrigger po konverzi je" + str(PreTrigger))
	
	#print(struct.pack('<I', 1<<30 | Trigger))

	PreTrigger = struct.pack('<h',PreTrigger)
	PreTriggerFlag = struct.pack('<H',2<<14) 

	Trigger = struct.pack('<h',Trigger)
	TriggerFlag = struct.pack('<H',1<<14)
	

	PreTrig= b"".join([PreTrigger, PreTriggerFlag])
	Trig = b"".join([Trigger, TriggerFlag])
	
	#vytisknout
	print(Trig)
	#print(PreTriggerFlag)

	s.send(PreTrig) #
	s.send(Trig) #
	
	print("Configuration sended to RP server")

def close_connection(event):
	global s

	s.send(struct.pack('<I', 3<<30))
	print("Zaviram spojeni:")
	print(s)
	SocketCreated = False # test
	close_file()
	SHUT_RD = socket.SHUT_RD
	s.shutdown(SHUT_RD)
	s.close()
	print("Connection to server closed")
	StatusLabel = Label(root, text = 'Offline', font=("Helvetica, 16"), fg="red")
	StatusLabel.grid(row=0,column =2,sticky=E)

def send_measure_request():
	global s
	global RequestSend
	s.send(struct.pack('<I', 0<<30))
	#if s.send valid then : RequestSend = True
	RequestSend = True
	print("measure request sended")  

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



root = Tk() #main window
root.title("DAQ-client-app")

frame= Frame(root)

Label(root, text="Trigger Level:").grid(row=0, sticky=W, padx=4)
TrigEntry = Entry(root)
TrigEntry.grid(row=0,column=1, sticky=E,pady=4)
TrigEntry.delete(0,END)
TrigEntry.insert(0, "0")

Label(root, text="PreTrigger Length:").grid(row=1, sticky=W, padx=4)
PreTrigEntry = Entry(root)
PreTrigEntry.grid(row=1,column=1, sticky=E,pady=4)
PreTrigEntry.delete(0,END)
PreTrigEntry.insert(0, "0")

Label(root, text="RP IP Address:").grid(row=2, sticky=W, padx=4)
IPEntry = Entry(root)
IPEntry.grid(row=2,column=1, sticky=E,pady=4)
IPEntry.delete(0,END)
IPEntry.insert(0, "10.42.0.203")

Label(root, text="RP Port:").grid(row=3, sticky=W, padx=4)
PortEntry = Entry(root)
PortEntry.grid(row=3,column=1, sticky=E,pady=4)
PortEntry.delete(0,END)
PortEntry.insert(0, "1001")

OpenButton = Button(root,text="Open file:")
OpenButton.grid(row=4, sticky=W)
OpenButton.bind("<Button-1>", open_file)

StopButton = Button(root,text="Stop Measuring")
StopButton.grid(row=5, sticky=W)
StopButton.bind("<Button-1>", close_connection)

StartButton2 = Button(root,text="Start Measuring")
StartButton2.grid(row=6, sticky=W)
StartButton2.bind("<Button-1>", start_measuring)

StatusLabel = Label(root, text = 'Offline', font=("Helvetica, 16"), fg="red")
StatusLabel.grid(row=0,column =2,sticky=E)


root.mainloop()
