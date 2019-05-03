# run in python3 
# written by : Radim Pavlik

import time
import struct
import socket

import atexit

import array
import matplotlib.pyplot as plt

import numpy

def exit_handler():
	s.close()
	print("Application is ending!")

    
atexit.register(exit_handler)


TCP_IP = '10.42.0.203' #'169.254.233.198'  #'169.254.233.198' #'127.0.0.1' 
TCP_PORT = 1001
BUFFER_SIZE = 65536

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))

time_old = 0
time_new = 0

probehlo_akvizic = 0
hodnoty = array.array('i')

requested = False
 
VoltageConversionCoefficient = 8 # (14bit sign Range/2)/mV .. (16384/2)/1000 # = 1mV cca 8,192 float :/
VoltagePlotOffset_mV = 0 # calibration of non symetricity

TimeConversionCoefficient = 0.008 #uS => 1sample (RP 125 Msps => 1sample = (1/125E6)= 8E-9 Sec = 8nS)


def Setup():
	global VoltageConversionCoefficient

	TriggerLvl = -500 #mV
	TriggerLvL_converted = int(TriggerLvl*VoltageConversionCoefficient)
	print("Trigger Level converted=",TriggerLvL_converted," Trigger Level wanted=",TriggerLvl,"mV")
	
	PreTrigger = 2 # samples

	ForcedTrigger = 0 # 0=Disabled, 1=Enabed
	ChannelSelect = 1 #0=CH1, 1=CH2

	TriggerLvL_converted = struct.pack('<h',TriggerLvL_converted)
	TriggerFlag = struct.pack('<H',1<<13)
	Trig = b"".join([TriggerLvL_converted, TriggerFlag])
	s.send(Trig)

	s.send(struct.pack('<I', 2<<29 | PreTrigger ))   # number of samples
	s.send(struct.pack('<I', 5<<29 | ForcedTrigger)) # if there is necessary to manualy trigger event
	s.send(struct.pack('<I', 4<<29 | ChannelSelect )) # select the channel
	

def Request():
	global requested
	if (requested == False):
		s.send(struct.pack('<I', 0<<30))
		#print("Request Send")
		requested= True
	
def Receive():
	global time_old
	global time_new
	global requested
	global probehlo_akvizic
	global hodnoty
	global VoltageConversionCoefficient
	global VoltagePlotOffset_mV
	global TimeConversionCoefficient

	data = s.recv(BUFFER_SIZE)
	
	if (data < bytes(0) and socket.errno != socket.EAGAIN):
		print("Connection terminated")
		s.close()
	elif (data > bytes(0)):
		requested = False
		#print(data)
		#ukladej data pro potrebu grafu
		probehlo_akvizic = probehlo_akvizic+1
		#print(hodnoty)
		#data = numpy.array(data, 'i')
		time_old = time_new
		time_new = time.time()
		#pro kazde 100 mereni
		if( probehlo_akvizic >= 100 ):			
			probehlo_akvizic = 0
			hodnoty = numpy.fromstring(data, dtype=numpy.int16)
			hodnoty = (hodnoty/VoltageConversionCoefficient) + VoltagePlotOffset_mV # rescale and offset of received values
			casy_x = numpy.arange(0,(TimeConversionCoefficient*hodnoty.size),TimeConversionCoefficient)
			#tisk hodnoty/v grafu
			plt.plot(casy_x,hodnoty)
			xmin=0
			xmax=10 #uS
			ymin=-1000 #mV
			ymax=1000 #mV
			plt.xlim([xmin,xmax])
			plt.ylim([ymin,ymax])
			plt.ylabel('Voltage [mV]')
			plt.xlabel('Time [uS]')
			plt.show()
			#print("Time before two data blocks received : " +str(time_new - time_old) )
			print(str(time_new - time_old),";",hodnoty.size )
			#print("END")
			

Setup()

while True:
	#Setup() # neni nutne volat opakovane pokud se parametry nemeni
	Request()
	Receive()

	#time.sleep(0.0001)
	#time.sleep(1)

s.close()




