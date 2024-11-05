
cam_index = 0
# cam_res = [4096,2160]
# cam_fps = 30
# cam_res = [1920,1080]
# cam_fps = 60
cam_res = [1280,720]
cam_fps = 90

preview_downsize = 2
preview_loc = [0,0]
face_detection_scale = 10
eye_detection_scale = 5
timestamp_method = 0
viewing_distance = 100
stim_display_width = 100
stim_display_res = [1920,1080]
stim_display_position = [0,0]
manual_calibration_order = True
calibration_dot_size_in_degrees = .5

import file_forker
import numpy as np
import cv2
import scipy.ndimage.filters
import sys
import sdl2
import sdl2.ext
import sdl2.sdlmixer
import time
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


#define a class for a clickable text UI
class clickable_text:
	def __init__(self,x,y,text,right_justified=False,value_text=''):
		self.x = x
		self.y = y
		self.text = text
		self.right_justified = right_justified
		self.value_text = value_text
		self.is_active = False
		self.clicked = False
		self.update_surf()
	def update_surf(self):
		self.surf = sdl2.sdlttf.TTF_RenderText_Blended_Wrapped(
			font
			, (self.text+self.value_text).encode()
			, sdl2.pixels.SDL_Color(r=0, g=255*self.is_active, b=255, a=255)
			, preview_window.size[0]
		).contents
	def check_if_active(self,event):
		if self.right_justified:
			x_left = self.x - self.surf.w
			x_right = self.x
		else:
			x_left = self.x
			x_right = self.x + self.surf.w
		if (event.button.x>x_left) & (event.button.x<x_right) & (event.button.y>self.y) & (event.button.y<(self.y+font_size)):
			self.is_active = True
		else:
			self.is_active = False
		self.update_surf()
	def draw(self,target_window_surf):
		if self.right_justified:
			sdl2.SDL_BlitSurface(self.surf, None, target_window_surf, sdl2.SDL_Rect(self.x-self.surf.w,self.y,self.surf.w,self.surf.h))
		else:
			sdl2.SDL_BlitSurface(self.surf, None, target_window_surf, sdl2.SDL_Rect(self.x,self.y,self.surf.w,self.surf.h))

#define a class for settings
class setting_text(clickable_text):
	def __init__(self,value,x,y,text,right_justified=False):
		self.value = value
		self.value_text = str(value)
		clickable_text.__init__(self,x,y,text,right_justified,self.value_text)
	def add_value(self,to_add):
		self.value_text = self.value_text+to_add
		self.update_surf()
	def del_value(self):
		if self.value_text != '':
			self.value_text = self.value_text[0:(len(self.value_text)-1)]
			self.update_surf()
	def finalize_value(self):
		try:
			self.value = int(self.value_text)
		except:
			print('Non-numeric value entered!')

#define a class for dots
class dot_obj:
	def __init__(self,name,is_fid,fid,x_pixel,y_pixel,radius_pixel,blink_criterion,blur_size,filter_size):
		self.name = name
		self.is_fid = is_fid
		self.x = x_pixel
		self.y = y_pixel
		self.radius = radius_pixel
		self.first = True
		self.last = [self.x,self.y,self.radius]
		self.lost = False
		self.blink_happened = False
		self.radii = []
		self.sds = []
		self.lost_count = 0
		self.blink_criterion = blink_criterion
		self.blur_size = blur_size
		self.filter_size = filter_size
		self.set_pixels()
		if not self.is_fid:
			self.make_relative_to_fid(fid)
	def set_pixels(self):
		self.x_pixel = int(self.x)
		self.y_pixel = int(self.y)
		self.radius_pixel = int(self.radius)
		return None
	def make_relative_to_fid(self,fid):
		self.x2 = (self.x-fid.x)/fid.radius
		self.y2 = (self.y-fid.y)/fid.radius
		self.radius2 = self.radius/fid.radius
		return None
	def get_dark_ellipse(self,img):
		try:
			smoothed_img = cv2.GaussianBlur(img,(self.blur_size,self.blur_size),0)
			# smoothed_img = img
		except Exception as e:
			print(f'cv2.GaussianBlur failed:\n{e}')
			return None
		try:
			# data_min = scipy.ndimage.filters.minimum_filter(smoothed_img, self.filter_size)
			data_min = smoothed_img
		except Exception as e:
			print(f'scipy.ndimage.filters.minimum_filter failed:\n{e}')
			return None
		# print(f'data_min:\n{data_min}')
		if data_min is not None:
			try:
				min_locs = np.where(data_min < (np.min(data_min) + np.std(data_min)))
			except Exception as e:
				print(f'np.where failed:\n{e}')
				return None
			# print(f'min_locs:\n{min_locs}')
			if len(min_locs[0]) >= 5:
				try:
					ellipse = cv2.fitEllipse(np.reshape(np.column_stack((min_locs[1],min_locs[0])),(len(min_locs[0]),1,2)))
				except Exception as e:
					print(f'cv2.fitEllipse failed:\n{e}')
					return None
				return ellipse
	def crop_image(self,img,crop_size):
		x_lo = self.x_pixel - crop_size
		if x_lo < 0:
			x_lo = 0
		x_hi = self.x_pixel + crop_size
		if x_hi > img.shape[1]:
			x_hi = img.shape[1]
		y_lo = self.y_pixel - crop_size
		if y_lo < 0:
			y_lo = 0
		y_hi = self.y_pixel + crop_size
		if y_hi > img.shape[0]:
			y_hi = img.shape[0]
		return [img[y_lo:y_hi,x_lo:x_hi],x_lo,x_hi,y_lo,y_hi]
	def search(self,img):
		# print(f'ellipse search input size:\n{img.shape}')
		# print(f'first:\n{self.first}')
		# print(f'fid:\n{self.is_fid}')
		# print(f'lost:\n{self.lost}')
		# print(f'radius_pixel:\n{self.radius_pixel}')
		if self.first and self.is_fid:
			search_size = 1
		elif self.lost:
			search_size = 5
		else:
			search_size = 3
		if self.first:
			self.first = False
		# print(f'search_size:\n{search_size}')
		img,x_lo,x_hi,y_lo,y_hi = self.crop_image(img=img,crop_size=search_size*self.radius_pixel)
		# print(f'ellips e search cropped size:\n{img.shape}')
		self.ellipse = self.get_dark_ellipse(img=img)
		if self.ellipse != None:
			self.ellipse = ((self.ellipse[0][0] + x_lo,self.ellipse[0][1] + y_lo),self.ellipse[1],self.ellipse[2])
			self.lost = False
			self.x = self.ellipse[0][0]
			self.y = self.ellipse[0][1]
			self.major = self.ellipse[1][0]
			self.minor = self.ellipse[1][1]
			self.angle = self.ellipse[2]
			self.radius = (self.ellipse[1][0] + self.ellipse[1][1]) / 4
			self.set_pixels()
		else:
			self.lost = True
	def check_search(self):
		self.median_radius = np.median(self.radii)
		self.crit_radius = 10 * ((np.median((self.radii-self.median_radius)**2))**.5)
		if len(self.radii) < 30:
			self.radii.append(self.radius2)
			self.lost = False
		else:
			if (self.radius2 < (1/6)) or (self.radius2 > 2):
				self.lost = True
			else:
				self.lost = False
				self.radii.append(self.radius2)
			if len(self.radii) >= 300:
				self.radii.pop()
	def check_sd(self,img,fid):
		self.obs_sd = np.std(self.crop_image(img=img,crop_size=5*fid.radius_pixel)[0])
		self.median_sd = np.median(self.sds)
		self.crit_sd = self.median_sd * self.blink_criterion
		if len(self.sds) < 30:
			self.sds.append(self.obs_sd)
			self.blink_happened = False
		else:
			if self.obs_sd < self.crit_sd:
				self.blink_happened = True
			else:
				self.sds.append(self.obs_sd)
				self.blink_happened = False
			if len(self.sds) >= 300:
				self.sds.pop()
	def update(self,img,fid,blink_criterion,blur_size,filter_size):
		self.blink_criterion = blink_criterion
		self.blur_size = blur_size
		self.filter_size = filter_size
		self.last = [self.x,self.y,self.radius]
		if self.is_fid:
			self.search(img=img)
		else:
			self.check_sd(img=img,fid=fid)
			if self.blink_happened:
				self.x,self.y,self.radius = self.last
				self.set_pixels()
				self.make_relative_to_fid(fid)
			else:
				self.search(img=img)
				if self.lost:
					self.x,self.y,self.radius = self.last
					self.set_pixels()
					self.make_relative_to_fid(fid)
				else:
					self.make_relative_to_fid(fid=fid)
					self.check_search()
					if self.lost:
						self.x,self.y,self.radius = self.last
						self.set_pixels()
						self.make_relative_to_fid(fid)
		if self.lost and not self.blink_happened:
			self.lost_count += 1
		else:
			self.lost_count = 0

########
# Initialize audio and define a class that handles playing sounds in PySDL2
########
sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
sdl2.sdlmixer.Mix_OpenAudio(44100, sdl2.sdlmixer.MIX_DEFAULT_FORMAT, 2, 1024)
class Sound:
	def __init__(self, file_name):
		self.sample = sdl2.sdlmixer.Mix_LoadWAV(sdl2.ext.compat.byteify(file_name, "utf-8"))
		self.started = False
	def play(self):
		self.channel = sdl2.sdlmixer.Mix_PlayChannel(-1, self.sample, 0)
		self.started = True
	def still_playing(self):
		if self.started:
			if sdl2.sdlmixer.Mix_Playing(self.channel):
				return True
			else:
				self.started = False
				return False

########
# define some useful functions
########

#define a function to exit safely
def exit_safely():
	tx_dict['parent'].put(kind='stop')
	sdl2.ext.quit()
	sys.exit()

#define a function to rescale
def rescale_biggest_haar(detected,scale,add_to_x=0,add_to_y=0):
	x,y,w,h = detected[np.argmax([np.sqrt(w*w+h*h) for x,y,w,h in detected])]
	return [x*scale+add_to_x,y*scale+add_to_y,w*scale,h*scale]


########
# Initialize variables
########

#initialize sounds
blink_sound = Sound('./stimuli/sounds/beep.wav')
saccade_sound = Sound('./stimuli/sounds/stop.wav')

#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

def list_map_int(i):
	return(list(map(int,i)))

#initialize font
font_size = int(cam_res[1] / preview_downsize / 10)
sdl2.sdlttf.TTF_Init()
font = sdl2.sdlttf.TTF_OpenFont(str.encode('./stimuli/fonts/DejaVuSans.ttf'), font_size)

#initialize preview video
sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
preview_window = sdl2.ext.Window(
	"Preview"
	, size = list_map_int(
		(
			cam_res[0]/preview_downsize
			, cam_res[1]/preview_downsize
		)
	)
	, position = preview_loc
	, flags = sdl2.SDL_WINDOW_SHOWN
)
preview_window_surf = sdl2.SDL_GetWindowSurface(preview_window.window)
preview_window_array = sdl2.ext.pixels3d(preview_window_surf.contents)
sdl2.ext.fill(preview_window_surf.contents, sdl2.pixels.SDL_Color(r=255, g=255, b=255, a=255))
preview_window.refresh()
last_refresh_time = get_time()

#initialize the settings window
settings_window = sdl2.ext.Window(
	"Settings"
	, size = list_map_int(
		(
			cam_res[0]/preview_downsize
			, cam_res[1]/preview_downsize
		)
	)
	, position = list_map_int(
		(
			preview_loc[0] + cam_res[0] / preview_downsize + 1
			, preview_loc[1]
		)
	)
)
settings_window_surf = sdl2.SDL_GetWindowSurface(settings_window.window)
settings_window_array = sdl2.ext.pixels3d(settings_window_surf.contents)
sdl2.ext.fill(settings_window_surf.contents, sdl2.pixels.SDL_Color(r=0, g=0, b=0, a=255))
settings_window.hide()
settings_window.refresh()


#create some settings 
settings_dict = {}
settings_dict['blink'] = setting_text(value=75, x=font_size, y=font_size, text='Blink (0-100) = ')
settings_dict['blur'] = setting_text(value=3, x=font_size, y=font_size*2, text='Blur (0-; odd only) = ')
settings_dict['filter'] = setting_text(value=3, x=font_size, y=font_size*3, text='Filter (0-; odd only) = ')
settings_dict['saccade0'] = setting_text(value=50, x=font_size, y=font_size*4, text='Saccade (0-) = ')
settings_dict['saccade'] = setting_text(value=1, x=font_size, y=font_size*5, text='Calibrated Saccade (0-) = ')

#create some text UIs
clickable_text_dict = {}
clickable_text_dict['init'] = clickable_text(x=0, y=0, text='Init')
clickable_text_dict['calibrate'] = clickable_text(x=0, y=preview_window.size[1]-font_size, text='Calibrate')
clickable_text_dict['settings'] = clickable_text(x=preview_window.size[0], y=0, text='Settings', right_justified=True)
clickable_text_dict['lag'] = clickable_text(x=preview_window.size[0], y=preview_window.size[1]-font_size*2, text='Lag: ', right_justified=True)
clickable_text_dict['fps'] = clickable_text(x=preview_window.size[0], y=preview_window.size[1]-font_size, text='FPS: ', right_justified=True)

#initialize variables
preview_in_focus = True
settings_in_focus = False
last_time = 0
dot_list = []
last_locs = [None,None]
display_lag_list = []
frame_to_frame_time_list = []
do_haar = False
do_haar_face = False
clicking_for_dots = False
calibrating = False
done_calibration = False
do_sounds = True
queue_data_to_parent = False

#set dummy calibration coefficients (yields untransformed pixel locs)
calibration_coefs = [[0,1,0,0],[0,1,0,0],[0,0,1,0],[0,0,1,0]]

col_info = {
	'time1' : {}
	, 'time2' : {}
	, 'blue' : {}
	, 'green' : {}
	, 'red' : {}
	, 'x_loc' : {}
	, 'y_loc' : {}
	, 'radius1' : {}
	, 'radius2' : {}
	, 'saccade' : {}
	, 'blink' : {}
	, 'lost1' : {}
	, 'lost2' : {}
	, 'blink1' : {}
	, 'blink2' : {}
}

# add column number:
for i,k in enumerate(col_info.keys()):
	col_info[k]['col_num'] = i+1

tx_dict['writer'].put(kind="attr",payload={"dset_name":"eye","value":{'col_names':[k for k in col_info.keys()],'col_info':col_info}})

def check_for_stop():
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()

#start the loop
while True:

	#check for messages from the main process
	check_for_stop()

	#poll the queue from pytracker_cam
	while rx_dict['pytracker_cam'].empty():
		check_for_stop()
	
	message = rx_dict['pytracker_cam'].get()
	t1 = message.payload['t1']
	t2 = message.payload['t2']
	image = message.payload['image']
	image_time = message.payload['image_time']
	image_num = message.payload['image_num']
	bgr = message.payload['bgr']

	#process input
	sdl2.SDL_PumpEvents()
	for event in sdl2.ext.get_events():
		if event.type == sdl2.SDL_WINDOWEVENT:
			target_window = sdl2.SDL_GetWindowFromID(event.window.windowID)
			title = sdl2.SDL_GetWindowTitle(target_window)
			if event.window.event == sdl2.SDL_WINDOWEVENT_LEAVE:
				if title == 'Preview':
					preview_in_focus = False
					settings_in_focus = True
			if (event.window.event == sdl2.SDL_WINDOWEVENT_FOCUS_GAINED) or (event.window.event == sdl2.SDL_WINDOWEVENT_ENTER):
				if title == 'Preview':
					preview_in_focus = True
					settings_in_focus = False
				elif title == 'Settings':
					preview_in_focus = False
					settings_in_focus = True
			elif event.window.event == sdl2.SDL_WINDOWEVENT_CLOSE:
				if title == 'Preview':
					exit_safely()
				elif title == 'Settings':
					preview_in_focus = True
					settings_in_focus = False
					settings_window.hide()
					preview_window.show()
		elif settings_in_focus:
			if event.type == sdl2.SDL_MOUSEMOTION:
				already_clicked = False
				for setting in settings_dict:
					if (settings_dict[setting].is_active) and (settings_dict[setting].clicked):
						already_clicked = True
				if not already_clicked:
					for setting in settings_dict:
						settings_dict[setting].check_if_active(event)
			elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
				already_clicked = False
				for setting in settings_dict:
					if (settings_dict[setting].is_active) and (settings_dict[setting].clicked):
						already_clicked = True
				if not already_clicked:
					for setting in settings_dict:
						if settings_dict[setting].is_active:
							settings_dict[setting].clicked = True
			elif event.type == sdl2.SDL_KEYDOWN:
				key = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower()
				if key == 'backspace':
					for setting in settings_dict:
						if (settings_dict[setting].is_active) and (settings_dict[setting].clicked):
							settings_dict[setting].del_value()
				elif key == 'return':
					for setting in settings_dict:
						if (settings_dict[setting].is_active) and (settings_dict[setting].clicked):
							settings_dict[setting].finalize_value()
							settings_dict[setting].clicked = False
				else:
					for setting in settings_dict:
						if (settings_dict[setting].is_active) and (settings_dict[setting].clicked):
							settings_dict[setting].add_value(key)
		elif preview_in_focus:
			if event.type == sdl2.SDL_KEYDOWN:
				key = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower()
				if key == 'escape': #exit
					clicking_for_dots = False
					clicking_for_fid = False
					defining_fid_finder_box = False
					dot_list = []
			if event.type == sdl2.SDL_MOUSEMOTION:
					if clicking_for_dots:
						clickable_text_dict['init'].is_active = True
						if defining_fid_finder_box:
							fid_finder_box_size = abs(fid_finder_box_x - (preview_window.size[0]-event.button.x))
					else:
						for clickable_text in clickable_text_dict:
							if not (clickable_text in ['lag','fps']):
								clickable_text_dict[clickable_text].check_if_active(event)
			if event.type == sdl2.SDL_MOUSEBUTTONDOWN:
				if clicking_for_dots:
					if clicking_for_fid:
						if not defining_fid_finder_box:
							defining_fid_finder_box = True
							fid_finder_box_x = preview_window.size[0] - event.button.x
							fid_finder_box_y = event.button.y
							fid_finder_box_size = 0
						else:
							defining_fid_finder_box = False
							clicking_for_fid = False
							fid_finder_box_size = abs(fid_finder_box_x - (preview_window.size[0] - event.button.x))
							dot_list.append(dot_obj(name='fid', is_fid=True, fid=None, x_pixel=fid_finder_box_x * preview_downsize, y_pixel=fid_finder_box_y * preview_downsize, radius_pixel=fid_finder_box_size * preview_downsize, blink_criterion=settings_dict['blink'].value/100.0, blur_size=settings_dict['blur'].value, filter_size=settings_dict['filter'].value))
					else:
						click_x = (preview_window.size[0] - event.button.x)
						click_y = event.button.y
						if len(dot_list) == 1:
							dot_list.append(dot_obj(name='left', is_fid=False, fid=dot_list[0], x_pixel=click_x * preview_downsize, y_pixel=click_y * preview_downsize, radius_pixel=dot_list[0].radius_pixel, blink_criterion=settings_dict['blink'].value/100.0, blur_size=settings_dict['blur'].value, filter_size=settings_dict['filter'].value))
						else:
							dot_list.append(dot_obj(name='right', is_fid=False, fid=dot_list[0], x_pixel=click_x * preview_downsize, y_pixel=click_y * preview_downsize, radius_pixel=dot_list[1].radius_pixel, blink_criterion=settings_dict['blink'].value/100.0, blur_size=settings_dict['blur'].value, filter_size=settings_dict['filter'].value))
							clicking_for_dots = False
							man_text_surf = sdl2.sdlttf.TTF_RenderText_Blended_Wrapped(font,'Init'.encode(),sdl2.pixels.SDL_Color(r=0, g=0, b=255, a=255),preview_window.size[0]).contents
				else:
					if clickable_text_dict['settings'].is_active:
						if (sdl2.SDL_GetWindowFlags(settings_window.window) & sdl2.SDL_WINDOW_SHOWN):
							settings_window.hide()
						else:
							settings_window.show()
					elif clickable_text_dict['auto'].is_active:
						waiting_for_haar = False
						do_haar = True
						dot_list = [] 
					elif clickable_text_dict['init'].is_active:
						clicking_for_dots = True
						clicking_for_fid = True
						defining_fid_finder_box = False
						dot_list = []
					# elif clickable_text_dict['calibrate'].is_active:
					# 	done_calibration = False
					# 	calibration_child.start()
					# 	calibrating = True
					# 	check_calibration_stop_time = False
					# 	queue_data_to_calibration_child = False


	#update the dots given the latest image
	for i in range(len(dot_list)): 
		dot_list[i].update(img=image, fid=dot_list[0], blink_criterion=settings_dict['blink'].value / 100.0, blur_size=settings_dict['blur'].value, filter_size=settings_dict['filter'].value)

	#some post-processing
	blink_happened = False
	saccade_happened = False
	if len(dot_list) == 3:
		if dot_list[0].lost:
			dot_list = []
			print('fid lost')
		elif (dot_list[1].lost_count > 30) or (dot_list[2].lost_count > 30):
			print("lost lots")
			if (not dot_list[1].blink_happened) and (not dot_list[2].blink_happened):
				dot_list = []
		elif dot_list[1].blink_happened and dot_list[2].blink_happened:
			blink_happened = True
		else:
			#compute gaze location to check for saccades
			x_coef_left,x_coef_right,y_coef_left,y_coef_right = calibration_coefs
			if dot_list[1].lost: #left missing, use right
				x_loc = x_coef_right[0] + x_coef_right[1] * dot_list[2].x2 + x_coef_right[2] * dot_list[2].y2 + x_coef_right[3] * dot_list[2].y2 * dot_list[2].x2
				y_loc = y_coef_right[0] + y_coef_right[1] * dot_list[2].x2 + y_coef_right[2] * dot_list[2].y2 + y_coef_right[3] * dot_list[2].y2 * dot_list[2].x2
			elif dot_list[2].lost: #right missing, use left
				x_loc = x_coef_left[0] + x_coef_left[1] * dot_list[1].x2 + x_coef_left[2] * dot_list[1].y2 + x_coef_left[3] * dot_list[2].y2 * dot_list[1].x2
				y_loc = y_coef_left[0] + y_coef_left[1] * dot_list[1].x2 + y_coef_left[2] * dot_list[1].y2 + y_coef_left[3] * dot_list[2].y2 * dot_list[1].x2
			elif dot_list[1].lost and dot_list[2].lost: #both missing, use last
				x_loc = last_locs[0]
				y_loc = last_locs[1]
			else: #both present, use average
				x_loc_left = x_coef_left[0] + x_coef_left[1] * dot_list[1].x2 + x_coef_left[2] * dot_list[1].y2 + x_coef_left[3] * dot_list[1].y2 * dot_list[1].x2
				y_loc_left = y_coef_left[0] + y_coef_left[1] * dot_list[1].x2 + y_coef_left[2] * dot_list[1].y2 + y_coef_left[3] * dot_list[1].y2 * dot_list[1].x2
				x_loc_right = x_coef_right[0] + x_coef_right[1] * dot_list[2].x2 + x_coef_right[2] * dot_list[2].y2 + x_coef_right[3] * dot_list[2].y2 * dot_list[2].x2
				y_loc_right = y_coef_right[0] + y_coef_right[1] * dot_list[2].x2 + y_coef_right[2] * dot_list[2].y2 + y_coef_right[3] * dot_list[2].y2 * dot_list[2].x2
				x_loc = (x_loc_left + x_loc_right) / 2.0
				y_loc = (y_loc_left + y_loc_right) / 2.0
			if None not in last_locs:
				loc_diff = (((x_loc - last_locs[0]) ** 2) + ((y_loc - last_locs[1]) ** 2)) ** .5
				if done_calibration:
					saccade_criterion = settings_dict['saccade'].value
				else:
					saccade_criterion = settings_dict['saccade0'].value / 100.0
				if loc_diff > saccade_criterion:
					saccade_happened = True
			last_locs = [x_loc,y_loc]
			tx_dict['writer'].put(
				kind = "data"
				, payload = {
					"dset_name" : 'eye'
					, "value" : np.array(
						[[
							t1
							, t2
							, bgr[0]
							, bgr[1]
							, bgr[2]
							, x_loc
							, y_loc
							, dot_list[1].radius2
							, dot_list[2].radius2
							, saccade_happened
							, blink_happened
							, dot_list[1].lost
							, dot_list[2].lost
							, dot_list[1].blink_happened
							, dot_list[2].blink_happened
						]]
						, dtype = np.float64
					)
				}
			)

	#play sounds as necessary
	if do_sounds:
		if (not saccade_sound.still_playing()) and (not blink_sound.still_playing()):
			if blink_happened:
				blink_sound.play()
			elif saccade_happened:
				saccade_sound.play()

	#do drawing
	if preview_downsize != 1:
		image = cv2.resize(image,dsize=preview_window.size,interpolation=cv2.INTER_NEAREST)
	image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
	if clicking_for_dots:
		if clicking_for_fid:
			if defining_fid_finder_box:
				cv2.circle(image,(fid_finder_box_x,fid_finder_box_y),fid_finder_box_size,color=(255,0,0,255),thickness=1)
	for dot in dot_list:
		if dot.ellipse is not None:
			ellipse = ((dot.ellipse[0][0] / preview_downsize, dot.ellipse[0][1] / preview_downsize), (dot.ellipse[1][0] / preview_downsize, dot.ellipse[1][1] / preview_downsize), dot.ellipse[2])
			if dot.blink_happened or dot.lost:
				dot_color = (0,0,255,255)
			else:
				dot_color = (0,255,0,255)
			cv2.ellipse(image,ellipse,color=dot_color,thickness=1)
	image = np.rot90(image)
	preview_window_array[:,:,0:3] = image
	frame_to_frame_time_list.append(image_time - last_time)
	last_time = image_time
	display_lag_list.append(get_time() - image_time)
	if len(display_lag_list) > 30:
		display_lag_list.pop(0)
		frame_to_frame_time_list.pop(0)
	clickable_text_dict['lag'].value_text = str(int(np.median(display_lag_list) * 1000))
	clickable_text_dict['lag'].update_surf()
	clickable_text_dict['fps'].value_text = str(int(1.0/np.median(frame_to_frame_time_list)))
	clickable_text_dict['fps'].update_surf()
	for clickable_text in clickable_text_dict:
		clickable_text_dict[clickable_text].draw(preview_window_surf)
	preview_window.refresh()
	this_refresh_time = get_time()
	last_refresh_time = this_refresh_time
	if (sdl2.SDL_GetWindowFlags(settings_window.window) & sdl2.SDL_WINDOW_SHOWN):
		sdl2.ext.fill(settings_window_surf.contents, sdl2.pixels.SDL_Color(r=0, g=0, b=0, a=255))
		for setting in settings_dict:
			settings_dict[setting].draw(settings_window_surf)
		settings_window.refresh()

	#calibration stuff
	# if calibrating:
	# 	if not tx_dict['pytracker_cal'].empty():
	# 		message = tx_dict['pytracker_cal'].get()
	# 		if message == 'start_queing':
	# 			queue_data_to_calibration_child = True
	# 		elif message.kind == 'stop_queing':
	# 			calibration_stop_time = message.payload
	# 			check_calibration_stop_time = True
	# 		elif message.kind == 'calibration_coefs':
	# 			calibration_coefs = message.payload
	# 			calibrating = False
	# 			done_calibration = True
	# 			calibration_child.stop()
	# 			del calibration_child
	# 			last_locs = []
	# 			tx_dict['parent'].put(kind='calibration_complete',payload=message)
	# 			queue_data_to_parent = True
	# 		else: 
	# 			print(message)
	# 	if check_calibration_stop_time:
	# 		if image_time > calibration_stop_time:
	# 			queue_data_to_calibration_child = False
	# 			rx_dict['pytracker_cal'].put('done_queing')
	# 			check_calibration_stop_time = False
	# 	if queue_data_to_calibration_child:
	# 		if len(dot_list) > 0:
	# 			rx_dict['pytracker_cal'].put(kind='data',payload = [image_time,dot_list[1].x2,dot_list[1].y2,dot_list[2].x2,dot_list[2].y2])
