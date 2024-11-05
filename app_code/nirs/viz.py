########
# Initialize debugger & check for expected variables
########
# from file_forker import debug_class
# debug = debug_class('viz')
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])

import sys
import matplotlib
from matplotlib import cm
from matplotlib.colors import ListedColormap
import numpy as np
import time
import zarr

done = False
while not done:
	time.sleep(0.1) #to reduce cpu load
	#handle messages received
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind=='stop':
			debug.print('Stopping')
			sys.exit()
	#check for file from writer
	if not rx_dict['writer'].empty():
		message = rx_dict['writer'].get()
		if message.kind=='store_path':
			store_path = message.payload
		elif message.kind=='data':
			if message.payload['dset_name']=='nirs':
				done = True

# debug.print('received file: '+ store_path)
store = zarr.open('../data/_' + store_path,mode='r')

while ('nirs' not in store.keys()) or ('nirs_time' not in store.keys()):
	time.sleep(.1)

nirs = store['nirs']
while 'col_names' not in nirs.attrs.keys():
	time.sleep(.1)

col_names = nirs.attrs.get('col_names')
nirs_time = store['nirs_time']

top = cm.get_cmap('Oranges_r', 128+64)
bottom = cm.get_cmap('Blues', 128-64)
newcolors = np.vstack((top(np.linspace(0, 1, 128+64)),
                       bottom(np.linspace(0, 1, 128-64))))
colormap = ListedColormap(newcolors, name='OrangeBlue')

#colormap = cm.get_cmap('viridis',256)

def prettify(x):
	x = format(x, '.0e')
	x = x.replace('e-0', 'e-')
	x = x.replace('e+0', 'e+')
	return(x)

matplotlib.rcParams.update({'font.size': 11})
# matplotlib.use('Qt5Agg')
# matplotlib.use('GTK3Agg')
matplotlib.rcParams['toolbar'] = 'None'

import matplotlib.pyplot as plt
plt.ion()
def mypause(interval):
	backend = plt.rcParams['backend']
	if backend in matplotlib.rcsetup.interactive_bk:
		figManager = matplotlib._pylab_helpers.Gcf.get_active()
		if figManager is not None:
			canvas = figManager.canvas
			if canvas.figure.stale:
				canvas.draw()
			canvas.start_event_loop(interval)
			return


vizChildStartTime = time.perf_counter()

global showAllSamples
global timeToShow
global detrend

showAllSamples = False#True
timeToShow = 90
latency_frames_criterion = 1
detrend = False
def on_close(event):
	tx_dict['parent'].put(kind='stop')

def on_key(event):
	global showAllSamples
	global timeToShow
	global detrend
	if event.key in [' ','Space']: #toggle show_latest on / off
		showAllSamples = not showAllSamples
		timeToShow = lastTimeShown
	elif event.key=='d':
		detrend = not detrend
	elif event.key in ['left','Left']:
		if not showAllSamples:
			timeToShow = 2*timeToShow
	elif event.key in ['right','Right']:
		if not showAllSamples:
			timeToShow = timeToShow/2.0
			if timeToShow<1:
				timeToShow = 1
	else:
		debug.print(event.key)

plt.rcParams['ytick.labelsize'] = 'small'
plt.style.use(['dark_background','fast'])

fig, ax = plt.subplots(num='Channel Timeseries')#frameon=False)
fig.canvas.mpl_connect('key_press_event',on_key)
fig.canvas.mpl_connect('close_event',on_close)
# fig.canvas.manager.window.setGeometry(0, 0,1440,900) #can tweak this to fit your screen better

plt.show()
while True:
	time.sleep(0.001) #to reduce cpu load
	#handle messages received
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind=='stop':
			debug.print('Stopping')
			sys.exit()
	# debug.print('updating viz')
	nirs = store['nirs'].astype('float64')#[1:]
	actual_nirs_time = store['nirs_time']
	# nirs_time = actual_nirs_time[1] + np.arange(actual_nirs_time.shape[0])/5 #[1:]
	nirs_time = actual_nirs_time
	min_samples = np.min([nirs.shape[0],nirs_time.shape[0]])
	nirs = nirs[0:min_samples,]
	nirs_time = nirs_time[0:min_samples]
	# if nirs.shape[0]>nirs_time.shape[0]:
	# 	nirs = nirs[0:nirs_time]
	# print([nirs.shape,nirs_time.shape])
	if nirs.shape[0]>=2:
		latest_time = nirs_time[-1]
		now = time.perf_counter()
		latency = now - latest_time
		lag = 9999999#latency_frames_criterion/60.0
		if latency>lag: #if we're getting behind on samples
			# debug.print('delaying viz update to process data')
			latency_frames_criterion += 1
			# pass
		else:
			# debug.print('really updating viz')
			latency_frames_criterion = 1
			ax.clear()
			ax.get_xaxis().set_visible(False)
			latest_time = nirs_time[-1]
			earliest_time = nirs_time[0]
			lastTimeShown = latest_time - earliest_time
			y_axis_shift = 0
			y_tick_locs = []
			y_tick_labels = []
			hz_list = []
			render_start_time = time.perf_counter()
			dt = np.median(np.diff(nirs_time))
			if dt<=0:
				hz = np.Inf
			else:
				hz = 1/dt
			time_select = np.arange(nirs.shape[0])
			# print(nirs)
			# print(nirs_time)
			# print(time_select)
			if not showAllSamples:
				time_test = (latest_time - nirs_time) < timeToShow
				# print(time_test)
				time_select = time_select[time_test]
				# print(time_select)
			total_cols = nirs.shape[1]
			x = nirs_time[time_select]
			mean_x = np.mean(x)
			x_minus_mean_x =  x - mean_x
			for i in range(total_cols):
				y = nirs[time_select,i]
				label = col_names[i]
				#fix occasional negative spikes
				bad = np.asarray((y<=0)|(y>5e3)).nonzero()[0]
				for this_bad in bad:
					if this_bad>0:
						prior_val = y[this_bad-1]
					else:
						prior_val = np.nan
					if this_bad < (y.shape[0]-2):
						next_val = y[this_bad+1]
					else:
						next_val = np.nan
					#next line occasionally fails with error "IndexError: too many indices for array"
					y[this_bad] = np.nanmean(np.array([prior_val,next_val]))
				#get the mean (for printing DC level)
				dc = np.mean(y)
				if detrend:
					#detrend (from: https://towardsdatascience.com/simple-linear-regression-from-scratch-in-numpy-871335e14b7a)
					y -= dc
					numerator = np.sum( x_minus_mean_x * y )
					denominator = np.sum( x_minus_mean_x**2 )
					b1 = numerator/denominator
					b0 = -b1*mean_x
					y -= b0 + b1*x #obtains residuals
					y += dc #for proper colors
				ysd = np.std(y)
				last_y = y[-1]
				yrange_min = np.min(y)
				yrange_max = np.max(y)
				y = y-yrange_min
				range_diff = yrange_max-yrange_min
				if(range_diff>0):
					y = y/range_diff
				else:
					y = y + .5
				y = y + y_axis_shift
				if last_y<=0:
					last_y=1
				ax.plot(x-earliest_time,y,label=label,color=colormap(np.log10(last_y)/4))
				ax.get_xaxis().set_visible(True)
				y_tick_locs.append(y_axis_shift+.5)
				y_tick_labels.append(label+' '+\
					prettify(last_y)+\
					' ('+\
					prettify(ysd)+\
					')')
				y_axis_shift += 1
			#add y-axis tick labels
			if len(y_tick_locs)>0:
				plt.yticks(y_tick_locs,y_tick_labels)
				plt.ylim((-.5,y_tick_locs[-1]+1))
			try:
				plt.xlabel('Time since start (seconds); Hz: '+\
					str(round(hz,2))+\
					', Lag: '+str(int(round(latency*1000)))+'ms'+\
					', render time: '+str(int(round(render_duration*1000)))+'ms'+\
					'\n'
					)
				# if lag>1:
				# 	plt.xlabel('Time since start (seconds)\nHz: '+str(int(round(np.median(np.array(hz_list)))))+'\n[Lag: '+str(round(lag,2))+'s]')
				# else:
				# 	plt.xlabel('Time since start (seconds)\nHz: '+str(int(round(np.median(np.array(hz_list))))))
			except:
				pass
				# debug.print('Can\'t do x-axis label')
			plt.margins(x=0)
			plt.subplots_adjust(left=0.2, right=.99, top=0.99, bottom=0.05)
			mypause(.00001) #don't know why this is necessary
			now = time.perf_counter()
			render_duration = now - render_start_time
			last_plot_time = now
