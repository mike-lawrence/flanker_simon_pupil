########
# Import libraries
########
import sdl2 #for input and display
import sdl2.ext #for input and display
import sdl2.sdlmixer #for input and display
import numpy as np #for image and display manipulation
from PIL import Image #for image manipulation
from PIL import ImageDraw #for image manipulation
import aggdraw #for drawing
import math #for rounding
import sys #for quitting
import time #for timing
import os #for checking existing files
import pylink
import array
byteify = lambda x, enc: x.encode(enc)


########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class('eyelink')
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
if 'rx_dict' not in locals():
	from file_forker import q_class
	rx_dict = {
		'parent' : q_class(tx='parent',rx='self') 
		, 'exp' : q_class(tx='exp',rx='self') 
	}
	tx_dict = {
		'parent' : q_class(tx='self',rx='parent') 
		, 'exp' : q_class(tx='self',rx='writer') 
		, 'writer' : q_class(tx='self',rx='writer') 
	}


########
#Important parameters
########

viewing_distance = 40.0 #units can be anything so long as they match those used in windowWidth below
stim_display_width = 40.0 #units can be anything so long as they match those used in viewingDistance above
stim_display_res = (1920,1080) #pixel resolution of the window
stim_display_position_x = 0

calibration_dot_size_in_degrees = .5 #specify the width of the fixation stimulus

calibration_dot_size = 10
gaze_target_criterion = 10

eyelink_ip = '100.1.1.1'
edf_file_name = 'tmp.edf'
saccade_sound_file = './stimuli/sounds/stop.wav'
blink_sound_file = './stimuli/sounds/stop.wav'
drift_sound_file = './stimuli/sounds/beep.wav'

def list_map_int(i):
	return(list(map(int,i)))

stim_display_res = list_map_int(stim_display_res)


########
#Perform some calculations to convert stimulus measurements in degrees to pixels
########
window_width_in_degrees = math.degrees(math.atan((stim_display_width/2.0)/viewing_distance)*2)
PPD = stim_display_res[0]/window_width_in_degrees #compute the pixels per degree (PPD)

calibration_dot_size = int(calibration_dot_size_in_degrees*PPD)

calibration_pixel_coords = [0,0,stim_display_res[0],stim_display_res[1]]
calibration_phys_coords = [
	-stim_display_res[0]/2.0
	,stim_display_res[1]/2.0
	,stim_display_res[0]/2.0
	,-stim_display_res[1]/2.0
]


########
# Initialize sounds
########

sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO)
sdl2.sdlmixer.Mix_OpenAudio(44100, sdl2.sdlmixer.MIX_DEFAULT_FORMAT, 2, 1024)
class Sound:
	def __init__(self, fileName):
		self.sample = sdl2.sdlmixer.Mix_LoadWAV(sdl2.ext.compat.byteify(fileName, "utf-8"))
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
		else:
			return False

saccade_sound = Sound(saccade_sound_file)
blink_sound = Sound(blink_sound_file)
drift_sound = Sound(drift_sound_file)


########
# Initialize the timer and random seed
########
sdl2.SDL_Init(sdl2.SDL_INIT_TIMER)

########
# Initialize the window
########

sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
window = sdl2.ext.Window(
	"eyelink"
	, size = stim_display_res
	, position = [0,0]
	# , position = (windowPositionX,0)
	, flags = 
		sdl2.SDL_WINDOW_SHOWN
		| sdl2.SDL_WINDOW_BORDERLESS
		| sdl2.SDL_RENDERER_PRESENTVSYNC
)
window_surf = sdl2.SDL_GetWindowSurface(window.window)
window_array = sdl2.ext.pixels3d(window_surf.contents)
sdl2.mouse.SDL_ShowCursor(0)

def raise_and_focus():
	sdl2.SDL_RaiseWindow(window.window)
	sdl2.SDL_SetWindowInputFocus(window.window)
	sdl2.SDL_PumpEvents()

# raise_and_focus()
for i in range(5): 
	raise_and_focus()
	sdl2.SDL_PumpEvents() #to show the windows

########
#Define some useful colors
########
white = sdl2.pixels.SDL_Color(r=255, g=255, b=255, a=255)
black = sdl2.pixels.SDL_Color(r=0, g=0, b=0, a=255)
grey = sdl2.pixels.SDL_Color(r=127, g=127, b=127, a=255)
light_grey = sdl2.pixels.SDL_Color(r=192, g=192, b=192, a=255)
red = sdl2.pixels.SDL_Color(r=255, g=0, b=0, a=255)
green = sdl2.pixels.SDL_Color(r=0, g=255, b=0, a=255)


########
# Pre-render some visual stimuli
########

def draw_to_image(_Draw):
	return Image.frombytes(_Draw.mode,_Draw.size,_Draw.tobytes())

def image_to_array(_Image):
	return np.rot90(np.fliplr(np.asarray(_Image)))

def draw_pinwheel(col1,col2,size):
	pinwheel = aggdraw.Draw('RGBA',[size,size],(127,127,127,255))
	this_degree = 0
	for i in range(12):
		this_degree = i*30
		if i%2==1:
			brush = aggdraw.Brush(col1)
		else:
			brush = aggdraw.Brush(col2)
		for j in range(30):
			this_degree = this_degree+1
			pinwheel.polygon(
		     (
		       int(round(size/2.0))
		       , int(round(size/2.0))
		       , int(round(size/2.0 + math.sin(this_degree*math.pi/180)*size/2.0))
		       , int(round(size/2.0 + math.cos(this_degree*math.pi/180)*size/2.0))
		       , int(round(size/2.0 + math.sin((this_degree+1)*math.pi/180)*size/2.0))
		       , int(round(size/2.0 + math.cos((this_degree+1)*math.pi/180)*size/2.0))
		     )
		     , brush
		    )
	return(pinwheel)

fixation_pinwheel = image_to_array(draw_to_image(draw_pinwheel(col1=(255,255,255,255),col2=(0,0,0,255),size=calibration_dot_size)))


########
# Drawing and helper functions
########

#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

# define a function to check if a given duration has passed since a reference time
def elapsed_since_ref_greater_than_crit(last,crit):
	return((get_time()-last)>crit)

#define a function to wait relative to some reference time
def wait(duration,reference_time):
	while not elapsed_since_ref_greater_than_crit(reference_time, duration):
		pass

#define a function that waits for a given duration to pass
def simple_wait(duration):
	wait(duration,get_time())


def clear_screen(color=grey):
	sdl2.ext.fill(window_surf.contents,color)

#define a function to draw a numpy array on  surface centered on given coordinates
def blit_array(src,x_offset=0,y_offset=0,x=None,y=None):
	if x is None:
		x1 = int(window_array.shape[0]/2+x_offset-src.shape[0]/2)
		y1 = int(window_array.shape[1]/2+y_offset-src.shape[1]/2)
	else:
		x1 = int(x-src.shape[0]/2)
		y1 = int(y-src.shape[1]/2)
	x2 = x1+src.shape[0]
	y2 = y1+src.shape[1]
	window_array[x1:x2,y1:y2,:] = src


def blit_surf(src_surf,x_offset=0,y_offset=0):
	x = window.size[0]/2+x_offset-src_surf.w/2
	y = window.size[1]/2+y_offset-src_surf.h/2
	sdl2.SDL_BlitSurface(src_surf, None, window_surf, sdl2.SDL_Rect(x,y,src_surf.w,src_surf.h))
	#sdl2.SDL_UpdateWindowSurface(window.window) #should this really be here? (will it cause immediate update?)
	# sdl2.SDL_FreeSurface(srcSurf)

def draw_stim(x=None,y=None,x_offset=None,y_offset=None):
	clear_screen(grey)
	blit_array(fixation_pinwheel,x=x,y=y,x_offset=x_offset,y_offset=y_offset)
	refresh_windows()

#define a function that waits for a response
def wait_for_response():
	done = False
	while not done:
		sdl2.SDL_PumpEvents()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_KEYDOWN:
				response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower().decode()
				if response=='escape':
					exit_safely()
				else:
					done = True
	return response




def refresh_windows():
	#sdl2.SDL_UpdateWindowSurface(window.window)
	window.refresh()
	return None

def check_input():
	responses = []
	sdl2.SDL_PumpEvents()
	pump_time = get_time()
	for event in sdl2.ext.get_events():
		if event.type==sdl2.SDL_KEYDOWN:
			response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower().decode()
			if response=='escape':
				exit_safely()
			else:
				responses.append([pump_time,response])
	return responses


def check_for_stop():
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()




########
# Eyelink functions
########

def exit_safely():
	if 'eyelink' in locals(): # `eyelink` object initialized below
		if eyelink.isRecording()==0:
			eyelink.stopRecording()
		eyelink.setOfflineMode()
		eyelink.closeDataFile()
		eyelink.receiveDataFile(edf_file_name,'/tmp/eyelink_data.edf')
		eyelink.close()
		# direct the writer to move the edf file to the same dir as other data
		tx_dict['writer'].put(kind='file',payload='/tmp/eyelink_data.edf')
		# export the events and samples
		for ev in ['events','samples']:
			try:
				# use edf2asc to extract the flagged data
				os.system(f'edf2asc -y -{ev[0]} /tmp/eyelink_data.edf /tmp/eyelink_{ev}.asc')
				# compress the data
				os.system(f"7z a -tzip /tmp/eyelink_{ev}.asc.zip /tmp/eyelink_{ev}.asc")
				# remove the uncompressed file
				os.remove(f'/tmp/eyelink_{ev}.asc')
				# direct the writer to move the zip file to the same dir as other data
				tx_dict['writer'].put(kind='file',payload=f'/tmp/eyelink_{ev}.asc.zip')
			except Exception as e:
				debug.print(f'Error exporting {ev}: {e}')
	tx_dict['parent'].put(kind='stop')
	sdl2.ext.quit()
	sys.exit()


done = False
while not done:
	try:
		eyelink = pylink.EyeLink(eyelink_ip)
		done = True
	except:
		check_for_stop()

eyelink.openDataFile(edf_file_name)

eyelink.sendCommand('select_parser_configuration 0')# 0--> standard (cognitive); 1--> sensitive (psychophysical)
eyelink.sendCommand('sample_rate 250')
eyelink.setLinkEventFilter("SACCADE,BLINK")
eyelink.sendCommand("saccade_velocity_threshold = 30") # docs recommend 30 for cognitive
eyelink.sendCommand("saccade_acceleration_threshold = 9500") # docs recommend 9500 for cognitive

#screen_pixel_coords
# sets the gaze-position coordinate system, which is used for all calibration target locations and drawing commands
# usually set to correspond to the pixel mapping of the subject display
# Issue the "calibration_type" command after changing this to recompute fixation target positions
# you should also write a DISPLAY_COORDS messaage to the start of the EDF file to record the display resolution
#eyelink.sendCommand("screen_pixel_coords =  %d %d %d %d" % ' '.join(map(str,calibrationPixelCoords)) )
eyelink.sendCommand("screen_pixel_coords =  "+  ' '.join(map(str,calibration_pixel_coords)) )
#eyelink.sendCommand("screen_phys_coords =  %d %d %d %d" % calibrationPhysCoords) # signed distance from center to: left, top, right, bottom
eyelink.sendCommand("screen_phys_coords =  "+ ' '.join(map(str,calibration_phys_coords)) ) # signed distance from center to: left, top, right, bottom
eyelink.sendCommand("screen_distance =  " + str(viewing_distance) ) #distance from subject to display in mm
#eyelink.sendMessage("DISPLAY_COORDS  0 0 %d %d" %(stimDisplayRes[0],stimDisplayRes[1]))


class EyeLinkCoreGraphicsPySDL2(pylink.EyeLinkCustomDisplay):
	def __init__(self):
		self.__target_beep__ = Sound('./stimuli/sounds/type.wav')
		self.__target_beep__done__ = Sound('qbeep.wav')
		self.__target_beep__error__ = Sound('error.wav')
		if sys.byteorder == 'little':
			self.byteorder = 1
		else:
			self.byteorder = 0
		self.imagebuffer = array.array('I')
		self.pal = None
		self.__img__ = None
		# self.last_erase_cal_target_time = get_time()
		# self.last_exit_cal_display_time = get_time()
	def record_abort_hide(self):
		pass
	def play_beep(self,beepid):
		#pass
		if beepid == pylink.DC_TARG_BEEP or beepid == pylink.CAL_TARG_BEEP:
			self.__target_beep__.play()
		elif beepid == pylink.CAL_ERR_BEEP or beepid == pylink.DC_ERR_BEEP:
			self.__target_beep__error__.play()
		else:#	CAL_GOOD_BEEP or DC_GOOD_BEEP
			self.__target_beep__done__.play()
	def clear_cal_display(self):
		clear_screen()
		refresh_windows()
	def setup_cal_display(self):
		clear_screen()
		draw_stim(x_offset=0,y_offset=0)
		refresh_windows()
	def exit_cal_display(self): 
		# if elapsed_since_ref_greater_than_crit(self.last_exit_cal_display_time,.5):
		# 	clear_screen()
		# 	refresh_windows()
		# 	self.last_exit_cal_display_time = get_time()
		clear_screen()
		refresh_windows()
	def erase_cal_target(self):
		clear_screen()
		refresh_windows()
	def draw_cal_target(self, x, y):
		clear_screen()
		draw_stim(x=x,y=y)
		refresh_windows()
	def setup_image_display(self, width, height):
		self.img_size = (width,height)
		return(0)
	def exit_image_display(self):
		clear_screen()
		refresh_windows()
	def image_title(self,text):
		pass
	def set_image_palette(self, r,g,b):
		self.imagebuffer = array.array('I')
		sz = len(r)
		i = 0
		self.pal = []
		while i < sz:
			rf = int(b[i])
			gf = int(g[i])
			bf = int(r[i])
			if self.byteorder:
				self.pal.append((rf<<16) | (gf<<8) | (bf))
			else:
				self.pal.append((bf<<24) |  (gf<<16) | (rf<<8)) #for mac
			i = i+1
	def draw_image_line(self, width, line, totlines,buff):
		i = 0
		while i < width:
			if buff[i]>=len(self.pal):
				buff[i] = len(self.pal)-1
			self.imagebuffer.append(self.pal[buff[i]&0x000000FF])
			i = i+1
		if line == totlines:
			img = Image.frombytes('RGBX', (width,totlines), self.imagebuffer.tobytes())
			img = img.convert('RGBA')
			self.__img__ = img.copy()
			self.__draw__ = ImageDraw.Draw(self.__img__)
			# self.draw_cross_hair() #inherited method, calls draw_line and draw_losenge
			blit_array(
				np.array(self.__img__.resize([self.__img__.size[0]*4,self.__img__.size[1]*4],Image.BICUBIC))
			)
			self.__img__ = None
			self.__draw__ = None
			self.imagebuffer = array.array('I')
	def get_color_from_index(self,colorindex):
		if colorindex   ==  pylink.CR_HAIR_COLOR:          return (255,255,255,255)
		elif colorindex ==  pylink.PUPIL_HAIR_COLOR:       return (255,255,255,255)
		elif colorindex ==  pylink.PUPIL_BOX_COLOR:        return (0,255,0,255)
		elif colorindex ==  pylink.SEARCH_LIMIT_BOX_COLOR: return (255,0,0,255)
		elif colorindex ==  pylink.MOUSE_CURSOR_COLOR:     return (255,0,0,255)
		else: return (0,0,0,0)
	def draw_line(self,x1,y1,x2,y2,colorindex):
		if x1<0: x1 = 0
		if x2<0: x2 = 0
		if y1<0: y1 = 0
		if y2<0: y2 = 0
		if x1>self.img_size[0]: x1 = self.img_size[0]
		if x2>self.img_size[0]: x2 = self.img_size[0]
		if y1>self.img_size[1]: y1 = self.img_size[1]
		if y2>self.img_size[1]: y2 = self.img_size[1]
		imr = self.__img__.size
		x1 = int((float(x1)/float(self.img_size[0]))*imr[0])
		x2 = int((float(x2)/float(self.img_size[0]))*imr[0])
		y1 = int((float(y1)/float(self.img_size[1]))*imr[1])
		y2 = int((float(y2)/float(self.img_size[1]))*imr[1])
		color = self.get_color_from_index(colorindex)
		self.__draw__.line( [(x1,y1),(x2,y2)] , fill=color)
		#Ghis' code doesn't have  the below return
		return 0
	def draw_lozenge(self,x,y,width,height,colorindex):
		color = self.get_color_from_index(colorindex)
		imr = self.__img__.size
		x=int((float(x)/float(self.img_size[0]))*imr[0])
		width=int((float(width)/float(self.img_size[0]))*imr[0])
		y=int((float(y)/float(self.img_size[1]))*imr[1])
		height=int((float(height)/float(self.img_size[1]))*imr[1])
		if width>height:
			rad = height/2
			self.__draw__.line([(x+rad,y),(x+width-rad,y)],fill=color)
			self.__draw__.line([(x+rad,y+height),(x+width-rad,y+height)],fill=color)
			clip = (x,y,x+height,y+height)
			self.__draw__.arc(clip,90,270,fill=color)
			clip = ((x+width-height),y,x+width,y+height)
			self.__draw__.arc(clip,270,90,fill=color)
		else:
			rad = width/2
			self.__draw__.line([(x,y+rad),(x,y+height-rad)],fill=color)
			self.__draw__.line([(x+width,y+rad),(x+width,y+height-rad)],fill=color)
			clip = (x,y,x+width,y+width)
			self.__draw__.arc(clip,180,360,fill=color)
			clip = (x,y+height-width,x+width,y+height)
			self.__draw__.arc(clip,360,180,fill=color)
		#Ghis' code doesn't have  the below return
		return 0
	def get_mouse_state(self):
		# pos = pygame.mouse.get_pos()
		# state = pygame.mouse.get_pressed()
		# return (pos,state[0])
		pass
	def get_input_key(self):
		ky=[]
		sdl2.SDL_PumpEvents()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_JOYBUTTONDOWN:
				ky.append(pylink.KeyInput(32,0)) #button translated to space keypress (for drift correct)
			if event.type==sdl2.SDL_KEYDOWN:
				keysym = event.key.keysym
				keycode = keysym.sym
				if keycode == sdl2.SDLK_F1:           keycode = pylink.F1_KEY
				elif keycode == sdl2.SDLK_F2:         keycode = pylink.F2_KEY
				elif keycode == sdl2.SDLK_F3:         keycode = pylink.F3_KEY
				elif keycode == sdl2.SDLK_F4:         keycode = pylink.F4_KEY
				elif keycode == sdl2.SDLK_F5:         keycode = pylink.F5_KEY
				elif keycode == sdl2.SDLK_F6:         keycode = pylink.F6_KEY
				elif keycode == sdl2.SDLK_F7:         keycode = pylink.F7_KEY
				elif keycode == sdl2.SDLK_F8:         keycode = pylink.F8_KEY
				elif keycode == sdl2.SDLK_F9:         keycode = pylink.F9_KEY
				elif keycode == sdl2.SDLK_F10:        keycode = pylink.F10_KEY
				elif keycode == sdl2.SDLK_PAGEUP:     keycode = pylink.PAGE_UP
				elif keycode == sdl2.SDLK_PAGEDOWN:   keycode = pylink.PAGE_DOWN
				elif keycode == sdl2.SDLK_UP:         keycode = pylink.CURS_UP
				elif keycode == sdl2.SDLK_DOWN:       keycode = pylink.CURS_DOWN
				elif keycode == sdl2.SDLK_LEFT:       keycode = pylink.CURS_LEFT
				elif keycode == sdl2.SDLK_RIGHT:      keycode = pylink.CURS_RIGHT
				elif keycode == sdl2.SDLK_BACKSPACE:  keycode = ord('\b')
				elif keycode == sdl2.SDLK_RETURN:     keycode = pylink.ENTER_KEY
				elif keycode == sdl2.SDLK_ESCAPE:     keycode = pylink.ESC_KEY
				elif keycode == sdl2.SDLK_TAB:        keycode = ord('\t')
				elif keycode == pylink.JUNK_KEY:      keycode = 0
				ky.append(pylink.KeyInput(keycode,keysym.mod))
		return ky

def is_eyelink_recording():
	# eyelink.isRecording() returns 0 if it *is* indeed recording!
	return(eyelink.isRecording()==0) 

def stop_recording():
	if is_eyelink_recording(): 
		eyelink.stopRecording()

def start_recording():
	eyelink.startRecording(1,1,1,1) #this retuns immediately takes 10-30ms to actually kick in on the tracker
	while not is_eyelink_recording():
		pass

def do_calibration():
	stop_recording()
	raise_and_focus()
	eyelink.doTrackerSetup()
	start_recording()
	tx_dict['exp'].put(kind='calibration_done')




# initialize the data stores
tx_dict['writer'].put(
	kind = 'attr'
	, payload = {
		'dset_name' : 'eyelink_offset'
		, 'value' : { 'col_names' : ['offset','offset_usec'] }
	}
)


custom_display = EyeLinkCoreGraphicsPySDL2()
pylink.openGraphicsEx(custom_display)
do_calibration()

#set sounds (has to occur after `pylink.openGraphicsEx()`)
pylink.setDriftCorrectSounds('on','on','on')
pylink.setCalibrationSounds('on','on','on')


new_gaze_target = False
gaze_target = [calibration_pixel_coords[2]/2.0,calibration_pixel_coords[3]/2.0]
report_saccades = False
report_blinks = False
last_offset_poll_time = get_time()
while True:
	# handle messages from main.py
	check_for_stop()
	# handle messages from experiment
	if not rx_dict['exp'].empty():
		message = rx_dict['exp'].get()
		if message.kind=='edf_path':
			edf_save_path = message.payload
		elif message.kind=='report_saccades':
			report_saccades = message.payload
		elif message.kind=='report_blinks':
			report_blinks = message.payload
		elif message.kind=='send_message':
			eyelink.sendMessage(message.payload)
		elif message.kind=='do_drift_correct':
			stop_recording()
			drift_correct_success = True
			try:
				location = message.payload
				error = eyelink.doDriftCorrect(location[0],location[1],0,1)
				if error == 27: 
					drift_correct_success = False
			except:
				pass
			if not drift_correct_success:
				# tx_dict['exp'].put(kind='recalibrating')
				do_calibration()
			else:
				drift_sound.play()
				tx_dict['exp'].put(kind='drift_correct_done')
		elif message.kind=='start_recording':
			start_recording()
			tx_dict['exp'].put(kind='recording_started')
		elif message.kind=='new_gaze_target':
			new_gaze_target = True
			gaze_target = np.array(message.payload[1])
			gaze_target_criterion = np.array(message.payload[2])
		elif message.kind=='accept_trigger':
			eyelink.accept_trigger()
		elif message.kind=='do_calibration':
			do_calibration()
	if elapsed_since_ref_greater_than_crit(last_offset_poll_time,1):
		tx_dict['writer'].put(
			kind = 'data'
			, payload = {
				'dset_name' : 'eyelink_offset'
				, 'value' : np.array([[eyelink.trackerTimeOffset(),eyelink.trackerTimeUsecOffset()]],dtype = np.float64)
			}
		)
	if is_eyelink_recording(): 
		eye_data = eyelink.getNextData()
		if eye_data==pylink.ENDSACC:
			if (not saccade_sound.still_playing()) and (not blink_sound.still_playing()):
				saccade_sound.play()
			if report_saccades:
				tx_dict['exp'].put(kind='saccade')
			# eye_sample = eyelink.getFloatData()
			# gaze_start_time = eye_sample.getStartTime()
			# gaze_start = eye_sample.getStartGaze()
			# gaze_end = eye_sample.getEndGaze()
			# if (gaze_start[0]!=-32768.0) & (gaze_end[0]!=-32768.0):
			# 	gaze_dist_from_gaze_target = np.linalg.norm(np.array(gaze_end)-gaze_target)
			# 	if gaze_dist_from_gaze_target<1000:
			# 		if new_gaze_target:
			# 			if gaze_dist_from_gaze_target<(gaze_target_criterion):
			# 				tx_dict['exp'].put(kind='gaze_target_met',payload = [gaze_target,gaze_start_time])
			# 				new_gaze_target = False
			# 		elif gaze_dist_from_gaze_target>(gaze_target_criterion):
			# 			if report_saccades:
			# 				tx_dict['exp'].put(kind='gaze_target_lost',payload = gaze_target)
			# 			if (not saccade_sound.still_playing()) and (not blink_sound.still_playing()):
			# 				saccade_sound.play()
			# 		else:
			# 			if report_saccades:
			# 				tx_dict['exp'].put(kind='smaller_saccade',payload = gaze_dist_from_gaze_target)
		# elif eye_data==pylink.STARTBLINK:
		# 	last_start_blink_time = get_time()
		elif eye_data==pylink.ENDBLINK:
			# if elapsed_since_ref_greater_than_crit(last_start_blink_time,.1):
			if (not saccade_sound.still_playing()) and (not blink_sound.still_playing()):
				blink_sound.play()
			if report_blinks:
				tx_dict['exp'].put(kind='blink')
