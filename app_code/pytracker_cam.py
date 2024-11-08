

cam_index = 0
# cam_res = [4096,2160]
# cam_fps = 30
# cam_res = [1920,1080]
# cam_fps = 60
cam_res = [1280,720]
cam_fps = 90

import file_forker
import numpy as np
import cv2
import sys
import time
import os
import ctypes
import threading

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
set_realtime_priority(pid, priority=50)
os.nice(-10)


########
# Initialize camera
########

#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()


class VideoCapture:
	def __init__(self, cam_index=0, cam_fps=30, cam_res=(1280, 720)):
		self.cap = cv2.VideoCapture(cam_index, cv2.CAP_V4L)
		self.cap.set(cv2.CAP_PROP_FPS, cam_fps)
		self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_res[0])
		self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_res[1])
		self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
		self.t1 = get_time()
		self.ret, self.frame = self.cap.read()
		self.t2 = get_time()
		self.image_num = 1
		self.stop_event = threading.Event()  # Use an Event to signal stopping
	def start(self):
		self.thread = threading.Thread(target=self.update, daemon=True)
		self.thread.start()
		return self
	def update(self):
		try:
			while not self.stop_event.is_set():  # Check if stop event is set
				self.t1 = get_time()
				self.ret, self.frame = self.cap.read()
				self.t2 = get_time()
				self.image_num += 1
				filename = os.path.join('../frames', f"frame_{self.image_num}.npy")
				np.save(filename, self.frame)
				time.sleep(0.0001)  # Optional: small sleep to reduce CPU usage
		finally:
			self.cap.release()  # Ensure release when loop exits
	def read(self):
		return [self.ret, self.frame, self.image_num, self.t1, self.t2]
	def stop(self):
		self.stop_event.set()  # Signal the thread to stop
		self.thread.join()  # Wait for the thread to finish

cap = VideoCapture(cam_fps=cam_fps,cam_res = cam_res).start()

#define a function to exit safely
def exit_safely():
	tx_dict['parent'].put(kind='stop')
	debug.print('releasing')
	cap.stop()
	debug.print('exiting')
	sys.exit()
	debug.print('exited')


def check_for_stop():
	# debug.print('checking for stop')
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			debug.print('stopping')
			exit_safely()

def check_for_renice():
	#check if there are any messages from the parent process
	while not rx_dict['exp'].empty():
		message = rx_dict['exp'].get()
		if message.kind == 'max_nice':
			os.nice(-10)
		elif message.kind == 'reg_nice':
			os.nice(10)

#start the loop
while True:

	#check for messages from the main process
	check_for_stop()	

	#check if there are any messages from the parent process
	# check_for_renice()

	#poll the camera
	_,image,image_num,t1,t2 = cap.read() #request the image
	image_time = t1 + (t2-t1) / 2.0 #timestamp the image as halfway between times before and after request
	tx_dict['pytracker'].put(
		kind = 'data'
		, payload = {
			't1' : t1
			, 't2' : t2
			, 'image_time' : image_time
			# , 'image' : image[:,:,2] #grab red channel (image is BGR)
			, 'image' : np.mean(image, axis=2).astype(np.uint8)
			, 'image_num' : image_num
			, 'bgr' : np.mean(image,axis=(0,1))
		}
	)
	# debug.print('looping')

