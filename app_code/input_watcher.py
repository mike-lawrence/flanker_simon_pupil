# dev = usb.core.find(idVendor=0x057e, idProduct=0x2009) 

from file_forker import debug_class
debug = debug_class('eyelink')
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
if 'rx_dict' not in locals():
	from file_forker import q_class
	rx_dict = {
		'parent' : q_class(tx='parent',rx='self') 
	}
	tx_dict = {
		'parent' : q_class(tx='self',rx='parent') 
		, 'exp' : q_class(tx='self',rx='exp') 
		, 'eyelink' : q_class(tx='self',rx='eyelink') 
		, 'writer' : q_class(tx='self',rx='writer') 
	}


import usb
import sys
import time
import copy
import numpy as np
import os
import ctypes

# Constants for real-time policies
SCHED_FIFO = 1
SCHED_RR = 2

def set_realtime_priority(pid, priority=50):
    # Ensure priority is within the allowable range (1-99)
    if not (1 <= priority <= 99):
        raise ValueError("Real-time priority must be between 1 and 99")
    
    # Create a sched_param structure
    class sched_param(ctypes.Structure):
        _fields_ = [("sched_priority", ctypes.c_int)]
    
    param = sched_param(priority)
    
    # Set the real-time scheduling policy
    libc = ctypes.CDLL("libc.so.6")
    result = libc.sched_setscheduler(pid, SCHED_FIFO, ctypes.byref(param))
    if result != 0:
        raise OSError("Failed to set real-time priority")

# Set real-time priority for the current process
pid = os.getpid()
# set_realtime_priority(pid, priority=50)
# os.nice(-20)


#find, claim & configure the gamepad
dev = None
while dev is None:
	dev = usb.core.find(idVendor=0x045e, idProduct=0x028e) 
	if dev is None:
		debug.print("Could not find the gamepad. Is it plugged in?")
		time.sleep(1)

num_interfaces = 1 #dev.get_active_configuration().bNumInterfaces

# Loop over all interfaces in the device and detach kernel driver if necessary
for i in range(num_interfaces):
	if dev.is_kernel_driver_active(i):
		try:
			dev.detach_kernel_driver(i)
			debug.print(f"Detached kernel driver from interface {i}")
		except usb.core.USBError as e:
			debug.print(f"Could not detach kernel driver from interface {i}: {str(e)}")



dev.set_configuration()
for i in range(num_interfaces):
	try:
		usb.util.claim_interface(dev, i)
		debug.print(f"Claimed interface {i}")
	except usb.core.USBError as e:
		debug.print(f"Could not claim interface {i}: {str(e)}")

read_endpoint = dev[0][(0, 0)][0]  # note interface 1 is the read interface (faster 500Hz polling rate)
write_endpoint = dev[0][(0, 0)][1] #note: interface 0 is the write interface

#turn off the player-number LEDs
dev.write(write_endpoint,"\x01\x03\x00",0)
debug.print("Turned off player-number LEDs")

def exit_safely():
	# first release the interfaces
	for i in range(num_interfaces):
		try:
			usb.util.release_interface(dev, i)
			debug.print(f"Released interface {i}")
		except usb.core.USBError as e:
			debug.print(f"Could not release interface {i}: {str(e)}")
	# then reattach the kernel drivers
	for i in range(num_interfaces):
		if not dev.is_kernel_driver_active(i):
			try:
				dev.attach_kernel_driver(i)
				debug.print(f"Attached kernel driver from interface {i}")
			except usb.core.USBError as e:
				debug.print(f"Could not attach kernel driver from interface {i}: {str(e)}")
	sys.exit()


#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

# Testing the polling rate:
# num_failure = 0
# num_success = 0
# last_time = get_time()
# start_time = get_time()
# try:
# 	while (get_time() - start_time) < 10:
# 		try:
# 			data = dev.read(read_endpoint.bEndpointAddress, read_endpoint.wMaxPacketSize, timeout=1)
# 			now = get_time()
# 			# debug.print(f"Data: {data}")
# 			debug.print(f"Time since last data: {now - last_time}")
# 			last_time = now
# 			num_success += 1
# 		except usb.core.USBError as e:
# 			# num_failure += 1
# 			if num_failure > 10:
# 				debug.print("Too many USB errors. Exiting.")
# 				break
# 			if e.errno == 110:  # Timeout error code
# 				# debug.print("Timeout, no data yet.")
# 				pass
# 			else:
# 				debug.print(f"USB Error: {e}")
# except:
# 	pass
# finally:
# 	exit_safely()



while True:
	#check if there are any messages from the parent process
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()
	# #check if there are any messages from the parent process
	# while not rx_dict['exp'].empty():
	# 	message = rx_dict['exp'].get()
	# 	if message.kind == 'max_nice':
	# 		os.nice(-10)
	# 	elif message.kind == 'reg_nice':
	# 		os.nice(10)
	#check if there's any data from the gamepad
	try:
		t1 = get_time()
		data = dev.read(read_endpoint.bEndpointAddress,read_endpoint.wMaxPacketSize,1)
		t2 = get_time()
		if len(data)==20:
			tx_dict['input'].put(
				kind = 'data'
				, payload = {
					't1' : t1
					, 'data' : data
					, 't2' : t2
				}
			)
	except usb.core.USBError as e:
		pass
		# debug.print(f"USB Error: {e}")
		# continue #skips the rest of the loop
		# if e.args != ('Operation timed out',):
		# 	debug.print(f"USB Error: {e}")
	except Exception as e:
		debug.print(f"Error: {e}")
		# continue
# except KeyboardInterrupt:
# 	pass
# except Exception as e:
# 	debug.print(f"Error: {e}")
# finally:
# 	exit_safely()

