########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class()
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
if 'rx_dict' not in locals():
	from file_forker import q_class
	rx_dict = {'exp' : q_class(name='exp_to_self',tx='exp',rx='self') }
	tx_dict = {'exp' : q_class(name='self_to_exp',tx='self',rx='exp') }

import time
import zarr
import shutil
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
# os.nice(-10)

#get current time for data file name
if not os.path.exists('../data'):
	os.mkdir('../data')


time_str = time.strftime('%Y_%m_%d_%H_%M_%S')
data_dir = '../data/_' + time_str
os.mkdir(data_dir)
store_path = data_dir + '/data.zarr'
store = zarr.DirectoryStore(store_path)
zgrp_root = zarr.group(store)

for tx in tx_dict.values():
	tx.put(kind='store_path',payload=store_path)

store_path_prefix = '' # might be updated by experiment
any_data_written = False
#debug.print('file ready')

dset_dict = {}
attrs_dict = {}
file_list = []
stop_when_queue_empty = False
while len(rx_dict)>0:
	time.sleep(.01)
	#iterate over sources and deal with any new data
	for source,rxq in list(rx_dict.items()): #list() required for later pop
		if not rxq.empty():
			if stop_when_queue_empty:
				debug.print('still digesting items in queue from '+source)
			msg = rxq.get()
			if (msg.kind=='stop') & (source=='parent'):
				stop_when_queue_empty = True
				rx_dict.pop('parent')
				debug.print('Stopping when queues are empty.')
			elif msg.kind=='file':
				file_list.append(msg.payload)
				#debug.print('file received')
			elif msg.kind=='store_path_prefix':
				store_path_prefix = msg.payload
			elif msg.kind=='attr':
				dset_name = msg.payload['dset_name']
				debug.print(f'dset_name: {dset_name}')
				new_attrs = msg.payload['value']
				if dset_name not in zgrp_root.array_keys():
					attrs_dict[dset_name] = {}
					attrs_dest = attrs_dict[dset_name]
				else:
					attrs_dest = zgrp_root[dset_name].attrs
				for key,value in new_attrs.items():
					if key in attrs_dest:
						debug.print('key "'+key+'" already exists in dataset"'+dset_name+'"; value will be overwritten.')
					attrs_dest[key] = value
			elif msg.kind=='data':
				dset_name = msg.payload['dset_name']
				data = msg.payload['value']
				any_data_written = True
				#if data is new, initialize the dataset
				if dset_name not in zgrp_root.array_keys():
					zgrp_root.create_dataset(
						dset_name
						, shape = data.shape
						, dtype = data.dtype
						#, chunks = ???
					)
					zgrp_root[dset_name][:] = data
					#write any attrs previously stored in attrs_dict
					if dset_name in attrs_dict:
						for key,value in attrs_dict[dset_name].items():
							zgrp_root[dset_name].attrs[key] = value
						pop_junk = attrs_dict.pop(dset_name)
					# send notice to all receivers that this data is now present
					for tx in tx_dict.values():
						tx.put(kind='data',payload={'store_path':'../data/_' + store_path,'dset_name':msg.payload['dset_name'] })
				#if data is not new, append
				else:
					zgrp_root[dset_name].append(data)
			else:
				debug.print(f'Unrecognized message kind: {msg.kind}')
				# pass
		#queue is empty:
		elif stop_when_queue_empty:
			rx_dict.pop(source)

#just in case (doc say it's not necessary), delete & close groups & store
del(zgrp_root)
store.close()
del(store)

#delete store if no data was written
if not any_data_written:
	shutil.rmtree(store_path)
#move store if a prefix was received
else:
	if store_path_prefix!='':
		os.rename(
			data_dir
			, '../data/' + store_path_prefix + '_' + time_str
		)
		data_dir = '../data/' + store_path_prefix + '_' + time_str + '/'
	for file in file_list:
		if os.path.exists(file):
			shutil.move(file,data_dir)
		else:
			debug.print('file not found: '+file)
	#change directory to '../data/' + store_path_prefix + '_' + time_str
	os.chdir(data_dir)
	#compress store_path usinng 7z
	os.system('7z a -tzip data.zarr.zip data.zarr/. > /dev/null') #run 7z and suppress stdout (but will still show stderr)
	#delete store_path
	shutil.rmtree('data.zarr')
	# rename
	shutil.move('data.zarr.zip',store_path_prefix + '_' + time_str+'.zarr.zip')

#stop
debug.print('Stopping')
sys.exit()
