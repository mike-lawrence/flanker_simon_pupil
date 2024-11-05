########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class()
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
# debug.silence()

from ble_api_python.headset import get_headset, AxemHeadset
import sys
import copy
import time
import sdl2.ext
import numpy as np

class timing_alarm(object):
	def __init__(self,name):
		self.name = name
		self.last_check_time = None
		self.num_passing_since_last_alarm = 0
	def check(self,alarm_dt,len_dat=None):
		now = time.perf_counter()
		if self.last_check_time is not None:
			dt = now - self.last_check_time
			if dt>alarm_dt:
				if len_dat is not None:
					debug.print('WARNING: '+self.name+' took too long ('+str(round(dt,3))+'s) with '+str(self.num_passing_since_last_alarm)+' passes since last alarm; len(dat):'+str(len_dat),critical=True)
				else:
					debug.print('WARNING: '+self.name+' took too long ('+str(round(dt,3))+'s) with '+str(self.num_passing_since_last_alarm)+' passes since last alarm.',critical=True)
				self.num_passing_since_last_alarm = 0
			else:
				self.num_passing_since_last_alarm += 1
		self.last_check_time = now

debug.print("Searching for headset...")
headset_id = False
while not headset_id:
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind=='stop':
			debug.print('Stopping')
			sys.exit()
	headset_id = get_headset()
	if not headset_id:
		debug.print("Could not find a valid Axem headset!")

debug.print('Headset found')

debug.print('Creating AxemHeadset object')
headset = AxemHeadset(headset_id)
debug.print('Connecting to headset')
headset.connect()
fw_version_str = ".".join([str(x) for x in headset.info.firmware])
debug.print("Connected to headset!")
debug.print(" - Firmware version: {0}".format(fw_version_str))
debug.print(" - Address: {0}".format(headset_id))
debug.print(" - UUID: {0}".format(headset.info.uuid))

tx_dict['ble'].put(kind='info',payload=headset.info)

while True:
	sdl2.SDL_PumpEvents() # keeps process priority high
	sdl2.ext.get_events() #ditto?
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		do_stop = False
		if message.kind=='stop':
			do_stop = True
		elif message.kind=='keepalive':
			now = time.perf_counter()
			if (now-time_of_last_keepalive)>1:
				do_stop = True
		if do_stop:
			debug.print("Disconnecting from headset")
			headset.disconnect()
			debug.print('Stopping')
			sys.exit()
	if not rx_dict['ble'].empty():
		message = rx_dict['ble'].get()
		if message.kind=='levels':
			headset.write_levels(message.payload['emits'],message.payload['gains'])
		debug.print('Levels sent to headset')
		break


debug.print('Starting recording...')
headset.start_recording()
tx_dict['ble'].put(kind='started',payload=time.perf_counter())
debug.print('Recording started')

data_time_alarm = timing_alarm('data')
loop_time_alarm = timing_alarm('loop')
last_level_update_time = time.perf_counter()
time_of_last_keepalive = time.perf_counter()
while True:
	sdl2.SDL_PumpEvents() # keeps process priority high
	sdl2.ext.get_events() #ditto?
	dat = headset.get_path_data()
	if len(dat):
		tx_dict['ble'].put(kind='data',payload=dat)
		data_time_alarm.check(.3,dat['time'].shape[0])
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		do_stop = False
		if message.kind=='stop':
			do_stop = True
		elif message.kind=='keepalive':
			now = time.perf_counter()
			if (now-time_of_last_keepalive)>1:
				do_stop = True
		if do_stop:
			debug.print("Stopping recording")
			headset.stop_recording()
			debug.print("Disconnecting from headset")
			headset.disconnect()
			debug.print('Stopping')
			sys.exit()
	# now = time.perf_counter()
	# if (now-last_level_update_time)>1:
	# 	headset.write_levels(0,0)
	# 	post_write_time = time.perf_counter()
	# 	write_duration = post_write_time - now
	# 	last_level_update_time = post_write_time
	# 	debug.print('Levels sent to headset ('+str(round(write_duration,3))+'s)')
	if not rx_dict['ble'].empty():
		message = rx_dict['ble'].get()
		if message.kind=='levels':
			headset.write_levels(message.payload['emits'],message.payload['gains'])
		debug.print('Levels sent to headset')
	# loop_time_alarm.check(.01)
