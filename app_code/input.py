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
os.nice(-10)


def exit_safely():
	sys.exit()


#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

button_names = {
	'2': {
		'1':'dpad-up'
		, '2':'dpad-down'
		, '4':'dpad-left'
		, '8':'dpad-right'
		, '16':'start'
		, '32':'back'
		, '64':'left-stick'
		, '128':'right-stick'
	}
	, '3': {
		'1':'LB'
		, '2':'RB'
		, '4':'xbox'
		, '8':''
		, '16':'A'
		, '32':'B'
		, '64':'X'
		, '128':'Y'
	}
}
last_buttons_down = {
	'2': {
		'1':False
		, '2':False
		, '4':False
		, '8':False
		, '16':False
		, '32':False
		, '64':False
		, '128':False
	}
	, '3': {
		'1':False
		, '2':False
		, '4':False
		, '8':False
		, '16':False
		, '32':False
		, '64':False
		, '128':False
	}
}


button_col_info = {
	't1' : {}
	, 't2' : {}
	, 'button' : {
		'mapping': {
			'LB': 1
			, 'RB': 2
			, 'A': 3
			, 'B' : 4
			, 'X' : 5
			, 'Y'  :6
		}
	}
	, 'state' : {
		'mapping': {
			'down': 1
			, 'up': 2
		}
	}
}

# add column number:
for i,k in enumerate(button_col_info.keys()):
	button_col_info[k]['col_num'] = i+1

tx_dict['writer'].put(kind="attr",payload={"dset_name":"buttons","value":{'col_names':[k for k in button_col_info.keys()],'col_info':button_col_info}})

#define a useful function for processing button input
def process_buttons(button_set,t1,t2,data,last_buttons_down):
	buttons_down = copy.deepcopy(last_buttons_down)
	state = data[button_set]
	events = []
	for i in [128,64,32,16,8,4,2,1]:
		if state>=i:
			buttons_down[str(button_set)][str(i)] = True
			state = state - i
		else:
			buttons_down[str(button_set)][str(i)] = False
		if buttons_down[str(button_set)][str(i)]!=last_buttons_down[str(button_set)][str(i)]:
			button_name = button_names[str(button_set)][str(i)]
			if buttons_down[str(button_set)][str(i)]:
				new_state = 'down'
				tx_dict['exp'].put(kind='button',payload={'button':button_name})
				# tx_dict['eyelink'].put(kind='button',payload={'button':button_name})
				debug.print(f'Button {button_name} pressed')
			else:
				new_state = 'up'
			tx_dict['writer'].put(
				kind = "data"
				, payload = {
					"dset_name" : 'buttons'
					, "value" : np.array(
						[[
							t1
							, t2
							, button_col_info['button']['mapping'][button_name] 
							, button_col_info['state']['mapping'][new_state] 
						]]
						, dtype = np.float64
					)
				}
			)
	return buttons_down


trigger_col_info = {
	't1' : {}
	, 't2' : {}
	, 'trigger' : {
		'mapping': {
			'left': 1
			, 'right': 2
		}
	}
	, 'value' : {}
}

# add column number:
for i,k in enumerate(trigger_col_info.keys()):
	trigger_col_info[k]['col_num'] = i+1

tx_dict['writer'].put(kind="attr",payload={"dset_name":"triggers","value":{'col_names':[k for k in trigger_col_info.keys()],'col_info':trigger_col_info}})

def process_triggers(t1,t2,data,last_data):
	for trigger_num in [4,5]:
		trigger_name = ['left','right'][trigger_num-4]
		value = data[trigger_num]
		last_value = last_data[trigger_num]
		if value!=last_value:
			# debug.print(f"Trigger {trigger_name} value: {value}")
			# debug.print(f"Trigger code: {trigger_col_info['trigger']['mapping'][trigger_name]}")
			tx_dict['writer'].put(
				kind = "data"
				, payload = {
					"dset_name" : 'triggers'
					, "value" : np.array(
						[[
							t1
							, t2
							, trigger_col_info['trigger']['mapping'][trigger_name] 
							, value
						]]
						, dtype = np.float64
					)
				}
			)
			if (value>127) & (last_value<127):
				tx_dict['exp'].put(kind='trigger',payload={'response':trigger_name,'time':t2})
				debug.print(f'Trigger {trigger_name} pressed')


def check_for_stop():
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()

# try:
# last_data = None
last_data = [0, 20, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
# start_time = get_time()
# while (get_time() - start_time) < 10:
while True:
	check_for_stop()
	while rx_dict['input_watcher'].empty():
		check_for_stop()
	
	message = rx_dict['input_watcher'].get()
	t1 = message.payload['t1']
	t2 = message.payload['t2']
	data = message.payload['data']

	#process the data from the buttons
	button_set = 3
	if last_data[button_set]!=data[button_set]: #check buttons associated with state 3
		last_buttons_down = process_buttons(
			button_set = button_set
			, t1 = t1
			, t2 = t2
			, data = data
			, last_buttons_down = last_buttons_down
		)
	#process the data from the triggers
	process_triggers(
		t1 = t1
		, t2 = t2
		, data = data
		, last_data = last_data
	)
	#write/overwrite last_data with current data
	last_data = copy.deepcopy(data)

"""
Results from exploring the output from the gamepad:
0: always 0
1: always 20
2: 1=up, 2=down, 4=left, 8=right, 16=start, 32=back, 64=left stick, 128 = right stick
3: 1=left shoulder, 2=right shoulder, 4 = X, 16=A, 32=B, 64=X, 128=Y
4: left trigger
5: right trigger
6: left stick x
7: left stick angle: 0/255@north, 127@east, 0/255@south, 128@west
8: at extremes, reflects left y, but weirdly non-linear between
9: left stick angle: 0/255@west, 127 @ north, 0/255 @ east, 128 @ south
10: influenced by both sticks, 255 when right stick @east
11: right stick angle: 0/255@north, 127@east, 0/255@south, 128@west
12: influenced by both sticks, 0 when right stick @south
13: right stick angle: 0/255@west, 127 @ north, 0/255 @ east, 128 @ south
14: always 0
15: always 0
16: always 0
17: always 0
18: always 0
19: always 0
"""