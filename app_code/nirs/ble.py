########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class()
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
# debug.silence()

import time
import numpy as np
import sys
import math
from collections import OrderedDict
from copy import deepcopy

writer_ready = False
while not writer_ready:
	time.sleep(0.1) #to reduce cpu load
	#handle messages received from writer
	if not rx_dict['writer'].empty():
		msg = rx_dict['writer'].get()
		if msg.kind=='store_path':
			writer_ready = True
	#handle messages received from parent
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind=='stop':
			debug.print('Stopping')
			sys.exit()


class uint8_counter(object):
	def __init__(self):
		self.state = None
		self.next_state = None
		self.last_state = None
		self.total = 0
	def set_last_and_next(self):
		self.next_state = self.wrap_safe(self.state+1)
		self.last_state = self.wrap_safe(self.state-1)
	def initialize(self,state):
		# self.state = self.wrap_safe(state-1)
		self.state = self.wrap_safe(state)
		self.set_last_and_next()
		# debug.print({'counter initialized':{'last':self.last_state,'state':self.state,'next':self.next_state}})
		debug.print({'counter initialized':{'state':self.state}})
	def wrap_safe(self,value):
		if value==256:
			value = 0
		elif value==-1:
			value = 255
		return(value)
	def increment(self):
		self.state = self.wrap_safe(self.state+1)
		self.set_last_and_next()
		self.total += 1
		# debug.print({'counter incremented':{'last':self.last_state,'state':self.state,'next':self.next_state}})
		debug.print({'counter incremented':{'state':self.state}})

class conductor_class(object):
	def __init__(self,tx_dict,rx_dict):
		self.tx_dict = tx_dict
		self.rx_dict = rx_dict
		self.counter = uint8_counter()
		self.max_supported_emit = 4e2
		self.target_range_max = 3e3
		self.target_range_min = 1e3
		self.gain_mults = {0:1,1:2,2:5,3:10,4:20,5:25}
		self.gain_mults_np = np.array([v for v in self.gain_mults.values()])
		self.emits = None
		self.gains = None
		self.recording_start_time = None
		self.num_samples_on_last_check = None
		self.latest_samples = None
		self.latest_single_sample = None
		self.time_of_latest_sample = None
		self.time_of_last_level_send = None
		self.latest_pod1_counter = None
		self.latest_pod2_counter = None
		self.pod_counters_match = None
		self.pod_counters_match_next_expected = None
		self.counter_updated_since_last_levels_update = False
		self.sample_check_counter = 0
		self.last_check_time = None
		self.time_since_last_check = None
	def initialize_headset(self):
		info = None
		while info is None:
			if not self.rx_dict['ble_bg'].empty():
				message = self.rx_dict['ble_bg'].get()
				if message.kind=='info':
					info = message.payload
		self.emitter_names = info.measurements
		self.path_names = info.paths
		self.emits = OrderedDict(zip(self.emitter_names,[300]*len(self.emitter_names)))
		self.gains = OrderedDict(zip(self.path_names,[0]*len(self.path_names)))
		self.last_emits = self.emits
		self.last_gains = self.gains
		self.emitter_paths_map = OrderedDict()
		for emitter in self.emitter_names:
			self.emitter_paths_map[emitter] = { v:i for i, v in enumerate(self.path_names) if emitter==(v[:2]+'_'+v[6:]) } 
		tx_dict['writer'].put(kind="attr",payload={"dset_name":"emits","value":{'col_names':self.emitter_names}})
		tx_dict['writer'].put(kind="attr",payload={"dset_name":"gains","value":{'col_names':self.path_names}})
		tx_dict['writer'].put(kind="attr",payload={"dset_name":"levels_times","value":{'col_names':['time']}})
		tx_dict['writer'].put(kind="attr",payload={"dset_name":"nirs","value":{'col_names':self.path_names}})
	def check_for_samples(self):
		# debug.print('Checking for samples...')
		self.num_samples_on_last_check = 0
		self.latest_samples = None
		if not self.rx_dict['ble_bg'].empty():
			message = self.rx_dict['ble_bg'].get()
			if message.kind=='data':
				self.latest_samples = message.payload
		now = time.perf_counter()
		if self.last_check_time is not None:
			self.time_since_last_check = round(now - self.last_check_time,3)
			if self.time_since_last_check>1:
				debug.print('WARNING: '+str(self.time_since_last_check)+'s since last check',critical=True)
		self.last_check_time = now
		if self.latest_samples is not None:
			self.sample_check_counter += 1
			self.send_data_to_writer()
			if self.latest_samples['paths'].shape!=(1,len(self.path_names)):
				# debug.print({'shape of latest samples':self.latest_samples['paths'].shape[0]})
				self.num_samples_on_last_check = self.latest_samples['paths'].shape[0]
			else:
				self.num_samples_on_last_check = 1
			for i in range(self.num_samples_on_last_check):
				if self.time_of_latest_sample is None:
					time_since_last_sample = None
				else:
					time_since_last_sample = round(self.latest_samples['time'][i] - self.time_of_latest_sample,2)
				debug.print({'batch':self.sample_check_counter,'size':self.num_samples_on_last_check,'dt_check':self.time_since_last_check,'dt_sample':time_since_last_sample,'pod1':self.latest_samples['cal_updates_pod1'][i],'pod2':self.latest_samples['cal_updates_pod2'][i],'S4_D4_LO':self.latest_samples['paths'][i][22]})
			self.time_of_latest_sample = self.latest_samples['time'][-1]
			self.latest_pod1_counter = self.latest_samples['cal_updates_pod1'][-1]
			self.latest_pod2_counter = self.latest_samples['cal_updates_pod2'][-1]
			self.pod_counters_match = self.latest_pod1_counter==self.latest_pod2_counter
			self.latest_single_sample = self.latest_samples['paths'][-1]
			if self.pod_counters_match and (self.counter.state is not None):
				if self.latest_pod1_counter!=self.counter.state:
					self.pod_counters_match_next_expected = self.latest_pod1_counter==self.counter.next_state
					if self.pod_counters_match_next_expected:
						debug.print('Next counter detected, incrementing from '+str(self.counter.state)+' to '+str(self.counter.next_state))
						self.counter.increment()
						self.counter_updated_since_last_levels_update = True
					else:
						debug.print('WARNING: unexpected pod counter',critical=True)
						debug.print({'expected':self.counter.next_state,'found':self.latest_pod1_counter})
		# debug.print('Done checking for samples')
	def check_for_stop(self):
		if not self.rx_dict['parent'].empty():
			message = self.rx_dict['parent'].get()
			if message.kind=='stop':
				debug.print('Stopping')
				sys.exit()
	def wait_for_next_sample(self):
		self.num_samples_on_last_check = 0
		while self.num_samples_on_last_check==0:
			self.check_for_samples()
			self.check_for_stop()
	# def wait_for_next_counter(self):
	# 	debug.print('Waiting for next counter')
	# 	debug.print({'current':self.counter.state,'next':self.counter.next_state})
	# 	done = False
	# 	self.num_samples_since_last_counter = 0
	# 	while not done:
	# 		self.wait_for_next_sample()
	# 		if self.pod_counters_match:
	# 			if self.pod_counters_match_next_expected:
	# 				done = True
	# 		if not done:
	# 			self.num_samples_since_last_counter += self.num_samples_on_last_check
	# 	self.counter.increment()
	# 	debug.print({'num_samples_since_last_counter':self.num_samples_since_last_counter})
	def send_data_to_writer(self):
		for dtype_descr in self.latest_samples.dtype.descr:
			if dtype_descr[0]=='paths':
				dset_name = 'nirs'
			else:
				dset_name = 'nirs_'+dtype_descr[0]
			self.tx_dict['writer'].put(kind="data",payload={"dset_name":dset_name,"value":self.latest_samples[dtype_descr[0]]})
	def wait_for_recording_start(self):
		while self.recording_start_time is None:
			if not self.rx_dict['ble_bg'].empty():
				message = self.rx_dict['ble_bg'].get()
				if message.kind=='started':
					self.recording_start_time = message.payload
	def initialize_counter(self):
		debug.print('Intitializing counter')
		while self.counter.state is None:
			self.wait_for_next_sample()
			if self.pod_counters_match:
				self.counter.initialize(self.latest_pod1_counter)
		debug.print('Counter initialized')
	def send_levels_to_writer(self):
		tx_dict['writer'].put(
			kind = "data"
			, payload = {
				"dset_name": 'emits'
				, "value": np.array([v for v in self.emits.values()],dtype='int16').reshape((1,len(self.emitter_names)))
			}
		)
		tx_dict['writer'].put(
			kind = "data"
			, payload = {
				"dset_name": 'gains'
				, "value": np.array([v for v in self.gains.values()],dtype='int16').reshape((1,len(self.path_names)))
			}
		)
		tx_dict['writer'].put(
			kind = "data"
			, payload = {
				"dset_name": "levels_times"
				, "value": np.array([[time.perf_counter()]],dtype='float64')
			}
		)
	def send_levels_to_headset(self):
		debug.print('Sending levels to headset...')
		# debug.print(self.emits['S4_LO'])
		# debug.print([v for v in self.emits.values()][14])
		# debug.print(self.gains['S4_D4_LO'])
		# debug.print([v for v in self.gains.values()][22])
		# self.headset.write_levels(
		# 	[v for v in self.emits.values()]
		# 	,[v for v in self.gains.values()]
		# )
		self.tx_dict['ble_bg'].put(kind='levels',payload={
			'emits': [v for v in self.emits.values()]
			,'gains': [v for v in self.gains.values()]
		})
		debug.print('Levels sent to headset')
	def send_levels_to_bg_and_writer(self):
		debug.print('Updating levels...')		
		# if self.time_of_last_level_send is not None:
		# 	debug.print('Waiting for minimum update time delta to elapse...')
		# 	while (self.time_of_latest_sample-self.time_of_last_level_send)<2:
		# 		self.wait_for_next_sample()
		self.send_levels_to_writer()
		self.send_levels_to_headset()
		self.time_of_last_level_send = time.perf_counter()
		self.counter_updated_since_last_levels_update = False
		self.last_emits = deepcopy(self.emits)
		self.last_gains = deepcopy(self.gains)
		debug.print('Levels updated')
	def get_best_gain(self,nirs,gain):
		nirs_div_gain = nirs*1.0/self.gain_mults_np[gain]
		expected_nirs_given_all_gains = self.gain_mults_np*nirs_div_gain
		gain_mult_test = expected_nirs_given_all_gains > self.target_range_max
		if np.all(gain_mult_test):
			best_gain = 0
		elif not np.any(gain_mult_test):
			best_gain = 5
		else:
			best_gain = np.argmax(gain_mult_test) - 1
		return(best_gain)
	def auto_level_short(self,emitter):
		this_levels_changed = False
		nirs_key = [v for v in self.emitter_paths_map[emitter].values()][0]
		gain_key = [k for k in self.emitter_paths_map[emitter].keys()][0]
		nirs = self.latest_single_sample[nirs_key]
		emit = self.emits[emitter]
		gain = self.gains[gain_key]
		best_gain = self.get_best_gain(nirs,gain)
		if self.target_range_min <= nirs <= self.target_range_max:
			#we're in the right range, so just adjust gain
			if gain!=best_gain:
				self.gains[gain_key] = best_gain
				self.levels_changed |= True
				this_levels_changed = True
		elif nirs<self.target_range_min:
			#too low, prioritize more emit, then gain
			if emit<self.max_supported_emit:
				self.emits[emitter] += math.ceil((self.max_supported_emit-emit)/2)
				self.levels_changed |= True
				this_levels_changed = True
			elif gain!=best_gain:
				self.gains[gain_key] = best_gain
				self.levels_changed |= True
				this_levels_changed = True
		elif nirs>self.target_range_max:
			#too high, prioritize less gain then less emit
			if gain!=best_gain:
				self.gains[gain_key] = best_gain
				self.levels_changed |= True
				this_levels_changed = True
			elif emit>0:
				self.emits[emitter] = 1+math.floor(emit/2)
				self.levels_changed |= True
				this_levels_changed = True
		if this_levels_changed and (emitter=='S4_LO'):
			debug.print('Levels changed')
			debug.print({'emitter':emitter})
			debug.print({'nirs':nirs})
			debug.print({'old emit':emit})
			debug.print({'new emit':self.emits[emitter]})
			debug.print({'old gain':gain})
			debug.print({'new gain':self.gains[gain_key]})
	def auto_level_long(self,emitter):
		this_levels_changed = False
		nirs = {k:self.latest_single_sample[v] for k,v in self.emitter_paths_map[emitter].items()}
		# debug.print({'nirs':nirs})
		emit = self.emits[emitter]
		# debug.print({'old emit':emit})
		gain = {k:self.gains[k] for k,v in self.emitter_paths_map[emitter].items()}
		# debug.print({'old gain':gain})
		best_gains = {k:self.get_best_gain(nirs[k],gain[k]) for k in nirs.keys()}
		ok = [self.target_range_min<=v<=self.target_range_max for v in nirs.values()]
		too_low = [v<self.target_range_min for v in nirs.values()]
		too_high = [v>self.target_range_max for v in nirs.values()]
		# debug.print({'emitter':emitter,'emit':emit,'gain':gain,'nirs':nirs,'ok':ok})
		if all(ok):
			#check if gain can be increased to place the data closer to the target range max
			for k in gain.keys():
				if self.gains[k]!=best_gains[k]:
					self.gains[k] = best_gains[k]
					self.levels_changed |= True
					this_levels_changed = True
		elif all(too_low) or (any(too_low) and any(ok)):
			#too low, prioritize more emit, then more gain
			if emit<self.max_supported_emit:
				self.emits[emitter] += math.ceil((self.max_supported_emit-emit)/2)
				self.levels_changed |= True
				this_levels_changed = True
			else:
				for k in gain.keys():
					if self.gains[k]!=best_gains[k]:
						self.gains[k] = best_gains[k]
						self.levels_changed |= True
						this_levels_changed = True
		elif all(too_high) or (any(too_high) and any(ok)):
			#too high, prioritize less gain, then less emit
			any_gain_changed = False
			for k in gain.keys():
				if self.gains[k]!=best_gains[k]:
					self.gains[k] = best_gains[k]
					any_gain_changed = True
					self.levels_changed |= True
					this_levels_changed = True
			if not any_gain_changed and emit>0:
				self.emits[emitter] = 1+math.floor(emit/2)
				self.levels_changed |= True
				this_levels_changed = True
		else:
			#one too low, one too high
			# prioritize more emit, then more gain
			emit_changed = False
			if emit<self.max_supported_emit:
				self.emits[emitter] += math.ceil((self.max_supported_emit-emit)/2)
				self.levels_changed |= True
				this_levels_changed = True
				emit_changed = True
			for k in gain.keys():
				if self.gains[k]!=best_gains[k]:
					self.gains[k] = best_gains[k]
					self.levels_changed |= True
					this_levels_changed = True
		# if this_levels_changed:
		# 	debug.print('Levels changed')
		# 	debug.print({'emitter':emitter})
		# 	debug.print({'nirs':nirs})
		# 	debug.print({'old emit':emit})
		# 	debug.print({'new emit':self.emits[emitter]})
		# 	debug.print({'old gain':gain})
		# 	debug.print({'new gain':{k:self.gains[k] for k,v in self.emitter_paths_map[emitter].items()}})
	def auto_level(self):
		debug.print('Running auto-level')
		self.levels_changed = False
		if all(self.latest_single_sample[:12]==0) or all(self.latest_single_sample[12:]==0) : #all zeros for either pod means bad data
			debug.print('bad pod data')
			return()
		for emitter in self.emitter_names:
			if emitter[0:1]=='S':
				self.auto_level_short(emitter)
			else:
				self.auto_level_long(emitter)
	def loop(self):
		self.initialize_headset()
		self.send_levels_to_bg_and_writer()
		self.wait_for_recording_start()
		while (time.perf_counter()-self.recording_start_time)<3:
			self.wait_for_next_sample()
		self.initialize_counter()
		while True:
			self.auto_level()
			if self.levels_changed:
				self.send_levels_to_bg_and_writer()
				debug.print('Waiting for counter to update since last levels update...')
				while not self.counter_updated_since_last_levels_update:
					self.wait_for_next_sample()
			else:
				self.wait_for_next_sample()



conductor = conductor_class(tx_dict,rx_dict)
conductor.loop()