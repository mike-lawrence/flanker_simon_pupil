########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class()
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])

#library imports
import sys
if sys.platform=='darwin':
	import appnope
	appnope.nope()

import psutil
import numpy as np
import time
import json
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

#encode & send header to writer
sys_info = {
	'num_physical_cores':psutil.cpu_count(logical=False)
	, 'num_logical_cores':psutil.cpu_count(logical=True)
	#, 'num_available_cores':len(psutil.Process().cpu_affinity())
	, 'core_max_frequency':psutil.cpu_freq().max
}

if psutil.sensors_battery() is None:
	sys_info['power_plugged'] = True
else:
	sys_info['power_plugged'] = psutil.sensors_battery().power_plugged

# col_names = 'time,mem,'+','.join(['cpu'+str(i) for i in range(psutil.cpu_count())])
col_names = ['time','mem','cpu']
tx_dict['writer'].put(kind="attr",payload={"dset_name":"system_stats","value":{'col_names':col_names,'sys_info':json.dumps(sys_info)}})



while True:
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			sys.exit()
	time.sleep(.1)
	tx_dict['writer'].put(kind="data",payload={"dset_name":'system_stats',"value":np.array([[time.perf_counter(),psutil.virtual_memory().percent,psutil.cpu_percent()]],dtype=np.float64)})
