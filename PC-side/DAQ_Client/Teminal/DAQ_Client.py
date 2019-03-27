import time
import struct
import socket

import atexit

def exit_handler():
	s.close()
	print("Application is ending!")

    
  
    

atexit.register(exit_handler)


TCP_IP = '10.42.0.203' #'169.254.233.198'  #'169.254.233.198' #'127.0.0.1' 
TCP_PORT = 1001
BUFFER_SIZE = 65536

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))

TriggerLvl = 10
PreTrigger = 5


time_old = 0
time_new = 0

requested = False


def Setup():
	s.send(struct.pack('<I', 1<<30 | TriggerLvl )) #
	s.send(struct.pack('<I', 2<<30 | PreTrigger )) #number of samples
	

def Request():
	global requested
	if (requested == False):
		s.send(struct.pack('<I', 0<<30))
		print("Request Send")
		requested= True
	
def Receive():
	global time_old
	global time_new
	global requested

	data = s.recv(BUFFER_SIZE)
	if (data < bytes(0) and socket.errno != socket.EAGAIN):
		print("Connection terminated")
		s.close()
	elif (data > bytes(0)):
		requested = False
		#print(data)
		time_old = time_new
		time_new = time.time()
		print("Time before two data blocks received : " +str(time_new - time_old) )
		print("END")

Setup()

while True:
	Request()
	
	Receive()
	
	#time.sleep(0.0001)
	#time.sleep(1)

s.close()




