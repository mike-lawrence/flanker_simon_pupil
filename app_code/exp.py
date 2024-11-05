########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class('experiment')
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])
if 'rx_dict' not in locals():
	from file_forker import q_class
	rx_dict = {'parent' : q_class(name='parent_to_self',tx='parent',rx='self') }
	tx_dict = {'parent' : q_class(name='self_to_parent',tx='self',rx='parent') }


########
#Important parameters
########

viewing_distance = 40.0 #units can be anything so long as they match those used in windowWidth below
stim_display_width = 54.0 #units can be anything so long as they match those used in viewingDistance above
stim_display_res = (1920,1080) #pixel resolution of the window
# stim_display_res = (2560,1440) #pixel resolution of the window
stim_display_position_x = 0

# key_list = {'z':'left','/':'right'}
# response_list = ['z','/']
key_list = {'left':'left','right':'right'}
response_list = ['left','right']
trigger_left_axis = 2
trigger_right_axis = 5
trigger_criterion_value = -(2**16/4) # criterion at 25%


target_location_list = ['left','right','up','down']
target_list = ['black','white']
flankers_list = ['congruent','incongruent','neutral','neutral']

fixation_duration = 1.000
response_timeout = 1.000
feedback_duration = 1.000

reps_per_block = 1
number_of_blocks = 10 #specify the number of blocks

instruction_size_in_degrees = 1 #specify the size of the instruction text
feedback_size_in_degrees = 1 #specify the size of the feedback text (if used)

fixation_size_in_degrees = .5 #specify the width of the fixation stimulus

target_size_in_degrees = 1 #specify the width of the target
flanker_separation_in_degrees = .25
offset_size_in_degrees = 3 #specify the vertical offset of the target from fixation

text_width = .9 #specify the proportion of the screen to use when drawing instructions


do_eyelink = 'eyelink' in rx_dict


def list_map_int(i):
	return(list(map(int,i)))

stim_display_res = list_map_int(stim_display_res)



########
# Import libraries
########
import sdl2 #for input and display
import sdl2.ext #for input and display
import numpy as np #for image and display manipulation
from PIL import Image #for image manipulation
import aggdraw #for drawing
import math #for rounding
import sys #for quitting
import random #for shuffling and random sampling
import time #for timing
import os #for checking existing files
import os
import ctypes
import cv2

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
# Initialize the timer
########
sdl2.SDL_Init(sdl2.SDL_INIT_TIMER)

########
# Initialize the gamepad 
########
sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK)
gamepad = sdl2.SDL_JoystickOpen(0)


########
# Initialize the window
########

sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
window = sdl2.ext.Window(
	"experiment"
	, size = stim_display_res
	, position = [1920,0]
	# , position = (windowPositionX,0)
	, flags = 
		sdl2.SDL_WINDOW_SHOWN
		| sdl2.SDL_WINDOW_BORDERLESS
		| sdl2.SDL_RENDERER_PRESENTVSYNC

)
window_surf = sdl2.SDL_GetWindowSurface(window.window)
window_array = sdl2.ext.pixels3d(window_surf.contents)
sdl2.mouse.SDL_ShowCursor(0)

mirror_window = sdl2.ext.Window(
	"experiment mirror"
	, size = list_map_int([stim_display_res[0]/2,stim_display_res[1]/2])
	, position = [0,0]
	, flags = sdl2.SDL_WINDOW_SHOWN
)
mirror_window_surf = sdl2.SDL_GetWindowSurface(mirror_window.window)
mirror_window_array = sdl2.ext.pixels3d(mirror_window_surf.contents)



def raise_and_focus():
	sdl2.SDL_RaiseWindow(window.window)
	sdl2.SDL_SetWindowInputFocus(window.window)
	sdl2.SDL_PumpEvents()

raise_and_focus()
for i in range(5): sdl2.SDL_PumpEvents() #to show the windows


########
#Perform some calculations to convert stimulus measurements in degrees to pixels
########
window_width_in_degrees = math.degrees(math.atan((stim_display_width/2.0)/viewing_distance)*2)
PPD = stim_display_res[0]/window_width_in_degrees #compute the pixels per degree (PPD)

instruction_size = int(instruction_size_in_degrees*PPD)
feedback_size = int(feedback_size_in_degrees*PPD)

fixation_size = int(fixation_size_in_degrees*PPD)
target_size = int(target_size_in_degrees*PPD)
flanker_separation = int(flanker_separation_in_degrees*PPD)
offset_size = int(offset_size_in_degrees*PPD)

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
#Initialize the fonts
########

sdl2.sdlttf.TTF_Init()
instruction_font = sdl2.sdlttf.TTF_OpenFont(str.encode('./stimuli/fonts/DejaVuSans.ttf'), instruction_size)
feedback_font = sdl2.sdlttf.TTF_OpenFont(str.encode('./stimuli/fonts/DejaVuSans.ttf'), feedback_size)


########
# Pre-render some visual stimuli
########

def draw_to_image(_Draw):
	return Image.frombytes(_Draw.mode,_Draw.size,_Draw.tobytes())

def image_to_array(_Image):
	return np.rot90(np.fliplr(np.asarray(_Image)))

def render_pinwheel(col1,col2,size):
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

fixation_pinwheel = image_to_array(draw_to_image(render_pinwheel(col1=(255,255,255,255),col2=(0,0,0,255),size=fixation_size)))
neutral_pinwheel = draw_to_image(render_pinwheel(col1=(255,255,255,255),col2=(0,0,0,255),size=target_size))
white_pinwheel = draw_to_image(render_pinwheel(col1=(255,255,255,255),col2=(127,127,127,255),size=target_size))
black_pinwheel = draw_to_image(render_pinwheel(col1=(127,127,127,255),col2=(0,0,0,255),size=target_size))

def render_target_and_flankers(target_pinwheel,flankers_pinwheel):
	img = Image.new(target_pinwheel.mode, (target_size*3+flanker_separation*2,target_size*3+flanker_separation*2), (127,127,127,255))
	img.paste(target_pinwheel,(target_size+flanker_separation,target_size+flanker_separation))
	img.paste(flankers_pinwheel,(0,target_size+flanker_separation))
	img.paste(flankers_pinwheel,(target_size*2+flanker_separation*2,target_size+flanker_separation))
	img.paste(flankers_pinwheel,(target_size+flanker_separation,0))
	img.paste(flankers_pinwheel,(target_size+flanker_separation,target_size*2+flanker_separation*2))
	return(image_to_array(img))

target_flankers_list = {}
for target in ['black','white']:
	for flankers in ['congruent','incongruent','neutral']:
		if flankers=='neutral':
			flankers_suffix = 'neutral'
		elif flankers=='congruent':
			flankers_suffix = target
		elif target=='black':
			flankers_suffix = 'white'
		elif target=='white':
			flankers_suffix = 'black'
		target_flankers_list[target+'_'+flankers] = render_target_and_flankers(eval(target+'_pinwheel'),eval(flankers_suffix+'_pinwheel'))



########
# Drawing and helper functions
########

#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

# define a function to check if a given duration has passed since a reference time
def elapsed_since_ref_greater_than_crit(last,crit):
	return((get_time()-last)>crit)

#define a function that will kill everything safely
def exit_safely():
	tx_dict['parent'].put(kind='stop')
	sdl2.ext.quit()
	sys.exit()

# class to handle a single trigger
class single_trigger_class:
	def __init__(self,name):
		self.name = name
		self.last_value = -2**16
		self.last_response_time = None
		self.response_made = False
		self.response_finished = False
	def process_input(self,value,last_pump_time):
		# print(f'{self.name} trigger value: {value}')
		#send data to writer
		tx_dict['writer'].put(
			kind = "data"
			, payload = {
				"dset_name" : 'triggers'
				, "value" : np.array(
					[[
						last_pump_time
						, trigger_col_info['trigger']['mapping'][self.name] 
						, value
					]]
					, dtype = np.float64
				)
			}
		)
		#check if input reflects a "response"
		if self.response_made & (not self.response_finished):
			if (value<self.last_value) & (value<trigger_criterion_value):
				self.response_finished = True
				# debug.print(f'{self.name} trigger released')
		else:
			if not self.response_made:
				if (value>self.last_value) & (value>trigger_criterion_value):
					self.response_made = True
					self.last_response_time = last_pump_time
					# debug.print(f'{self.name} trigger pressed')
		self.last_value = value
	def reset_response(self):
		self.response_made = False
		self.response_finished = False


#class to handle both triggers together
class both_triggers_class:
	def __init__(self):
		self.left_trigger_dict_name = str(trigger_left_axis)
		self.right_trigger_dict_name = str(trigger_right_axis)
		self.triggers = {
			self.left_trigger_dict_name : single_trigger_class('left')
			, self.right_trigger_dict_name : single_trigger_class('right')
		}
	def process_input(self):
		sdl2.SDL_PumpEvents()
		last_pump_time = get_time()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_KEYDOWN:
				response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower().decode()
				if response=='escape':
					exit_safely()
			elif event.type == sdl2.SDL_JOYAXISMOTION:
				if str(event.jaxis.axis) in self.triggers.keys():
					# debug.print(f'Axis {event.jaxis.axis} value: {event.jaxis.value}')
					self.triggers[str(event.jaxis.axis)].process_input(event.jaxis.value,last_pump_time)
	def reset_responses(self):
		for trigger in self.triggers.values():
			trigger.reset_response()
	def clear_residual_input(self):
		self.process_input()
		self.reset_responses()
	def check_for_dual_response(self):
		if self.triggers[self.right_trigger_dict_name].response_finished & self.triggers[self.right_trigger_dict_name].response_finished:
			#check that the last response time is within 0.5s of eachother
			if abs(self.triggers[self.right_trigger_dict_name].last_response_time - self.triggers[self.left_trigger_dict_name].last_response_time)<0.5:
				result = True
			else:
				result = False
				debug.print('Dual response not simultaneous')
			self.reset_responses()
		else:
			result = False
		return(result)
	def check_for_response(self):
		self.process_input()
		responses = []
		for trigger in self.triggers.values():
			if trigger.response_made:
				responses.append({
					'name' : trigger.name
					, 'time' : trigger.last_response_time
			})
		self.reset_responses()
		return responses

both_triggers_obj = both_triggers_class()

#define a function to wait relative to some reference time
def wait(duration,reference_time):
	while not elapsed_since_ref_greater_than_crit(reference_time, duration):
		# pass
		both_triggers_obj.process_input()

#define a function that waits for a given duration to pass
def simple_wait(duration):
	wait(duration,get_time())

def clear_screen(color):
	sdl2.ext.fill(window_surf.contents,color)

#define a function to draw a numpy array on  surface centered on given coordinates
def blit_array(src,x_offset=0,y_offset=0):
	x1 = int(window_array.shape[0]/2+x_offset-src.shape[0]/2)
	y1 = int(window_array.shape[1]/2+y_offset-src.shape[1]/2)
	x2 = x1+src.shape[0]
	y2 = y1+src.shape[1]
	window_array[x1:x2,y1:y2,:] = src


def blit_surf(src_surf,x_offset=0,y_offset=0):
	x = window.size[0]/2+x_offset-src_surf.w/2
	y = window.size[1]/2+y_offset-src_surf.h/2
	sdl2.SDL_BlitSurface(src_surf, None, window_surf, sdl2.SDL_Rect(x,y,src_surf.w,src_surf.h))
	#sdl2.SDL_UpdateWindowSurface(window.window) #should this really be here? (will it cause immediate update?)
	# sdl2.SDL_FreeSurface(srcSurf)

def draw_target(target_location,target,flankers):
	target_flankers = target_flankers_list[target+'_'+flankers]
	if target_location=='left':
		blit_array(target_flankers,x_offset=-offset_size)
	elif target_location=='right':
		blit_array(target_flankers,x_offset=offset_size)
	elif target_location=='up':
		blit_array(target_flankers,y_offset=-offset_size)
	elif target_location=='down':
		blit_array(target_flankers,y_offset=offset_size)


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
			#check for gamepad buttons
			elif event.type==sdl2.SDL_JOYBUTTONDOWN:
					response = 'button'
					done = True
	return response


#def draw_text(text,font,color,wrapped=False):
#	if wrapped:
#		surface = sdl2.sdlttf.TTF_RenderText_Blended_Wrapped(font,text,color,int(window.size[0]*.9)).contents
#	else:
#		surface = sdl2.sdlttf.TTF_RenderText_Blended(font,text,color).contents
#	sdl2.SDL_BlitSurface(surface, None, windowSurf, sdl2.SDL_Rect(window.size[0]/2-surface.w/2,window.size[1]/2-surface.h/2,surface.w,surface.h))
#	sdl2.SDL_UpdateWindowSurface(window.window)
#	sdl2.SDL_FreeSurface(surface)
#	return None

#define a function that formats text for the screen
def draw_text(my_text, my_font, text_color, caption = False, text_width = 0.9):
	line_height = sdl2.sdlttf.TTF_RenderText_Blended(my_font,'T'.encode(),text_color).contents.h
	text_width_max = int(window.size[0]*text_width)
	paragraphs = my_text.splitlines()
	render_list = []
	text_height = 0
	for this_paragraph in paragraphs:
		words = this_paragraph.split(' ')
		if len(words)==1:
			render_list.append(words[0])
			if (this_paragraph!=paragraphs[len(paragraphs)-1]):
				render_list.append(' ')
				text_height = text_height + line_height
		else:
			this_word_index = 0
			while this_word_index < (len(words)-1):
				line_start = this_word_index
				line_width = 0
				while (this_word_index < (len(words)-1)) and (line_width <= text_width_max):
					this_word_index = this_word_index + 1
					line_width = sdl2.sdlttf.TTF_RenderText_Blended(my_font,' '.join(words[line_start:(this_word_index+1)]).encode(),text_color).contents.w
				if this_word_index < (len(words)-1):
					#last word went over, paragraph continues
					render_list.append(' '.join(words[line_start:(this_word_index-1)]))
					text_height = text_height + line_height
					this_word_index = this_word_index-1
				else:
					if line_width <= text_width_max:
						#short final line
						render_list.append(' '.join(words[line_start:(this_word_index+1)]))
						text_height = text_height + line_height
					else:
						#full line then 1 word final line
						render_list.append(' '.join(words[line_start:this_word_index]))
						text_height = text_height + line_height
						render_list.append(words[this_word_index])
						text_height = text_height + line_height
					#at end of paragraph, check whether a inter-paragraph space should be added
					if (this_paragraph!=paragraphs[len(paragraphs)-1]):
						render_list.append(' ')
						text_height = text_height + line_height
	num_lines = len(render_list)*1.0
	for this_line in range(len(render_list)):
		this_render = sdl2.sdlttf.TTF_RenderText_Blended(my_font,render_list[this_line].encode(),text_color).contents
		x = int(window.size[0]/2.0 - this_render.w/2.0)
		if caption:
			y = int(window.size[1] - this_render.h - text_height + (1.0*this_line)/num_lines*text_height)
		else:
			y = int(window.size[1]/2.0 - this_render.h/2.0 + 1.0*this_line/num_lines*text_height)
		sdl2.SDL_BlitSurface(this_render, None, window_surf, sdl2.SDL_Rect(x,y,this_render.w,this_render.h))
		# sdl2.SDL_UpdateWindowSurface(window.window) #should this really be here? (will it cause immediate update?)


def refresh_windows():
	#sdl2.SDL_UpdateWindowSurface(window.window)
	window.refresh()
	# tmp = window_array[:,:,0:3]
	# tmp = np.rot90(cv2.resize(np.rot90(tmp),mirror_window.size,interpolation=cv2.INTER_NEAREST))
	# mirror_window_array[:,:,0:3] = tmp
	mirror_window_array[:,:,0:3] = np.rot90(
		cv2.resize(np.rot90(window_array[:,:,0:3]),mirror_window.size,interpolation=cv2.INTER_NEAREST)
		, k = 3
	)
	# sdl2.SDL_UpdateWindowSurface(mirror_window.window)
	mirror_window.refresh()
	return None


#define a function that prints a message on the window while looking for user input to continue. The function returns the total time it waited
def show_message(my_text,whitelist=None):
	# print(my_text)
	# print(lock_wait)
	message_viewing_time_start = get_time()
	clear_screen(black)
	refresh_windows()
	clear_screen(black)
	draw_text(my_text, instruction_font, light_grey)
	simple_wait(0.500)
	refresh_windows()
	clear_screen(black)
	if whitelist is not None:
		response = None
		while response not in whitelist:
			response = wait_for_response()
	else:
		response = wait_for_response()
	window.refresh()
	clear_screen(black)
	simple_wait(0.500)
	message_viewing_time = get_time() - message_viewing_time_start
	return response,message_viewing_time


#define a function that requests user input
def get_input(get_what,whitelist=None):
	get_what = get_what+'\n'
	text_input = ''
	clear_screen(black)
	refresh_windows()
	simple_wait(0.500)
	my_text = get_what+text_input
	clear_screen(black)
	draw_text(my_text, instruction_font, light_grey)
	refresh_windows()
	clear_screen(black)
	done = False
	while not done:
		sdl2.SDL_PumpEvents()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_KEYDOWN:
				response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower().decode()
				if response=='escape':
					exit_safely()
				elif response == 'backspace':
					if text_input!='':
						text_input = text_input[0:(len(text_input)-1)]
						my_text = get_what+text_input
						clear_screen(black)
						draw_text(my_text, instruction_font, light_grey)
						refresh_windows()
				elif response == 'return':
					# debug.print(f'whitelist: {whitelist}')
					# debug.print(f'text_input: {text_input}')
					if whitelist is not None:
						if text_input in whitelist:
							done = True
					else:
						done = True
				else:
					text_input = text_input + response
					my_text = get_what+text_input
					clear_screen(black)
					draw_text(my_text, instruction_font, light_grey)
					refresh_windows()
	clear_screen(black)
	refresh_windows()
	return text_input



#define a function that generates a randomized list of trial-by-trial stimulus information representing a factorial combination of the independent variables.
def get_trials():
	trials=[]
	for rep in range(reps_per_block):
		for target_location in target_location_list:
			for target in target_list:
				for flankers in flankers_list:
					if target=='white':
						target_hand = key_list[white_response]
					elif target=='black':
						target_hand = key_list[black_response]
					
					if target_location in ['up','down']:
						simon = 'neutral'
					elif target_hand==target_location:
						simon = 'congruent'
					else:
						simon = 'incongruent'
					trials.append([target_location,target,flankers,simon,target_hand])
	random.shuffle(trials)
	return trials


def do_feedback(feedback_text,feedback_color):
	clear_screen(grey)
	draw_text(feedback_text,feedback_font,feedback_color)
	refresh_windows()
	feedback_start_time = get_time()
	while not elapsed_since_ref_greater_than_crit(feedback_start_time,feedback_duration):
		pass
		# responses = check_input()
		# if len(responses)>0:
		# 	feedback_response = 1
		# 	feedback_start_time = get_time()
		# 	if feedback_text=='Miss!':
		# 		feedback_text = 'Too slow!'
		# 	else:
		# 		feedback_text = 'Respond only once!'
		# 	feedback_color = red
		# 	# print('feedback response')
		# 	clear_screen(grey)
		# 	draw_text(feedback_text,feedback_font,feedback_color)
		# 	refresh_windows()

def write_trial_data(
	block
	, trial_num
	, trial_start_time
	, target_location
	, target
	, flankers
	, simon
	, target_hand
	, rt
	, response
	, error
	, anticipation
	, target_on_time0
	, target_on_time1
	, target_on_time2
	, target_on_time3
	# , recalibration_performed
	#,feedback_response):
):
	tx_dict['writer'].put(
		kind = "data"
		, payload = {
			"dset_name" : 'exp'
			, "value" : np.array(
				[[
					block
					, trial_num
					, trial_start_time
					, col_info['target_location']['mapping'][target_location] 
					, col_info['target']['mapping'][target] 
					, col_info['flankers']['mapping'][flankers] 
					, col_info['simon']['mapping'][simon] 
					, col_info['target_hand']['mapping'][target_hand] 
					, rt 
					, col_info['response']['mapping'][response]  #TODO: this breaks if a wrong key is pressed
					, int(error)
					, int(anticipation)
					# , int(feedback_response)
					, target_on_time0
					, target_on_time1
					, target_on_time2
					, target_on_time3
					# , int(recalibration_performed)
				]]
				, dtype = np.float64
			)
		}
	)

def double_clear():
	for i in range(2):
		clear_screen(grey)
		refresh_windows()

def double_draw_fixation():
	for i in range(2):
		clear_screen(grey)
		blit_array(fixation_pinwheel)
		refresh_windows()

def check_for_stop():
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()


def wait_for_dual_triggers():
	while True:
		both_triggers_obj.process_input()
		if both_triggers_obj.check_for_dual_response():
			break



#define a function that runs a block of trials
def run_block(block):

	# print('block '+str(block)+' started')

	# tx_dict['eyelink'].put('do_calibration')
	# calibration_done = False
	# while not calibration_done:
	# 	check_for_stop()
	# 	while not rx_dict['eyelink'].empty():
	# 		message = rx_dict['eyelink'].get()
	# 		if message.kind=='calibration_done':
	# 			calibration_done = True

	trial_list = get_trials()

	#run the trials
	trial_num = 0
	while len(trial_list)>0:

		# check for stop messages from the parent
		check_for_stop()

		#bump the trial number
		trial_num = trial_num + 1

		#get the trial info
		target_location,target,flankers,simon,target_hand = trial_list.pop()

		#clear any input still queued
		both_triggers_obj.clear_residual_input()

		#present the fixation
		double_draw_fixation()

		recalibration_performed = False
		wait_for_dual_triggers()
		# # drift-correct
		# if do_eyelink:
		# 	# we need two loops to handle the case where the drift correct fails and re-calibration is needed
		# 	# if the drift correct fails, the eyelink child will automatically start a re-calibration. When that's done
		# 	# we need to return focus, redraw fixationn, and wait for input to restart the drift correction process
		# 	drift_correct_outer_done = False
		# 	while not drift_correct_outer_done:
		# 		wait_for_dual_triggers()
		# 		tx_dict['eyelink'].put('do_drift_correct')
		# 		drift_correct_inner_done = False
		# 		while not drift_correct_inner_done:
		# 			while not rx_dict['eyelink'].empty():
		# 				message = rx_dict['eyelink'].get()
		# 				if message.kind=='drift_correct_done':
		# 					drift_correct_inner_done = True
		# 					drift_correct_outer_done = True
		# 				elif message.kind=='calibration_done':
		# 					drift_correct_inner_done = True
		# 					recalibration_performed = True
		# 					raise_and_focus()
		# 					double_draw_fixation()

		double_clear()
		# os.nice(-10)
		double_draw_fixation()
		trial_start_time = get_time()
		# os.nice(10)

		# print('trial start '+str(trial_num))

		#initialize some variables to be written later with default values
		rt = -999
		response = 'NA'
		error = -999
		anticipation = 0
		# feedback_response = 0
		feedback_color = red

		target_on_time0 = trial_start_time + fixation_duration

		#prepare the target
		clear_screen(grey)
		blit_array(fixation_pinwheel)
		draw_target(target_location,target,flankers)

		#wait until it's time to show the target
		wait(fixation_duration,trial_start_time)
		# os.nice(-10)

		#show the target
		refresh_windows()
		target_on_time1 = get_time()

		# show again immediately (hopefully a better target_on_error estimate)
		clear_screen(grey)
		blit_array(fixation_pinwheel)
		draw_target(target_location,target,flankers)
		target_on_time2 = get_time()
		refresh_windows()
		target_on_time3 = get_time()
		# os.nice(10)
		# tx_dict['input_watcher'].put('max_nice')
		# tx_dict['pytracker_cam'].put('max_nice')

		stop_trial = False
		#check for any pre-target blinks or saccades
		# if do_eyelink:
		# 	while not rx_dict['eyelink'].empty():
		# 		message = rx_dict['eyelink'].get()
		# 		if message.kind in ['blink','saccade']:
		# 			stop_trial = True
		# 			if message.kind=='blink':
		# 				feedback_text = "Blink\ndetected"
		# 			elif message.kind=='saccade':
		# 				feedback_text = "Move\ndetected"
		#check for any pre-target input
		responses = both_triggers_obj.check_for_response()
		if len(responses)>0:
			stop_trial = True
			feedback_text = 'Too\nsoon'
		# stop the trial if there was a blink, saccade, or premature response
		if stop_trial:
			# tx_dict['input_watcher'].put('reg_nice')
			# tx_dict['pytracker_cam'].put('reg_nice')
			anticipation = 1
			# print('anticipation')
			#uncomment next two lines to *enable* recycling the trials
			trial_list.append([target_location,target,flankers,simon,target_hand])
			random.shuffle(trial_list)
			do_feedback(feedback_text,feedback_color)
			write_trial_data(
				block
				, trial_num
				, trial_start_time
				, target_location
				, target
				, flankers
				, simon
				, target_hand
				, rt
				, response
				, error
				, anticipation
				, target_on_time0
				, target_on_time1
				, target_on_time2
				, target_on_time3
				# , recalibration_performed
			)

			continue # skip to the next trial
		#wait for response
		while True:
			if elapsed_since_ref_greater_than_crit(target_on_time0,response_timeout):
				feedback_text = 'Miss'
				# print('miss')
				break # exit the waiting-for-response loop
			# if do_eyelink:
			# 	while not rx_dict['eyelink'].empty():
			# 		message = rx_dict['eyelink'].get()
			# 		if message.kind in ['blink','saccade']:
			# 			if message.kind=='blink':
			# 				feedback_text = "Blink\ndetected"
			# 			elif message.kind=='saccade':
			# 				feedback_text = "Move\ndetected"
			# 			break # exit the waiting-for-response loop
			responses = both_triggers_obj.check_for_response()
			if len(responses)>0:
				rt = responses[0]['time'] - target_on_time0
				response = responses[0]['name']
				feedback_text = str(int(round(rt*1000)))
				if response==black_response:
					response = 'black'
					feedback_color = black
				elif response==white_response:
					response = 'white'
					feedback_color = white
				if response == target:
					error = 0
				else:
					error = 1
				break # exit the waiting-for-response loop
		# tx_dict['input_watcher'].put('reg_nice')
		# tx_dict['pytracker_cam'].put('reg_nice')

		# present feedback & write data
		do_feedback(feedback_text,feedback_color)		
		write_trial_data(
			block
			, trial_num
			, trial_start_time
			, target_location
			, target
			, flankers
			, simon
			, target_hand
			, rt
			, response
			, error
			, anticipation
			, target_on_time0
			, target_on_time1
			, target_on_time2
			, target_on_time3
			#,feedback_response
		)
	#done the block
	# print('block '+str(block)+' done')


########
# Initialize the data files
########

#get subject info
id = get_input('ID (\'test\' to demo): ')
tx_dict['writer'].put(kind='store_path_prefix',payload=id)
# if do_eyelink:
# 	tx_dict['writer'].put(kind='edf_path',payload='../data/_' +id)

# #counter-balance stimulus-response mapping
mapping = int(get_input('Response-Color mapping (0 or 1):',whitelist=['0','1']))

white_response = response_list[mapping]
black_response = response_list[1-mapping]

show_message("Response-Color mapping:\n"+white_response+" = white\n"+black_response+" = black.\nPress any key or button or to continue.")

inputs = {
	'id':id
	, 'mapping':mapping
}

col_info = {
	'block' : {}
	, 'trial_num' : {}
	, 'trial_start_time' : {}
	, 'target_location' : {
		'mapping': {
			'left': 1
			, 'right' : 2
			, 'up' : 3
			, 'down'  :4
		}
	}
	, 'target' : {
		'mapping': {
			'black': 1
			, 'white' : 2
		}
	}
	, 'flankers' : {
		'mapping': {
			'congruent': 1
			, 'incongruent' : 2
			, 'neutral' : 3
		}
	}
	, 'simon' : {
		'mapping': {
			'congruent': 1
			, 'incongruent' : 2
			, 'neutral' : 3
		}
	}
	, 'target_hand' : {
		'mapping': {
			'left': 1
			, 'right' : 2
		}
	}
	, 'rt' : {}
	, 'response' : {
		'mapping': {
			'black': 1
			, 'white' : 2
			, 'NA' : -999
		}
	}
	, 'error' : {}
	, 'anticipation' : {}
	# , 'feedback_response' : {}
	, 'target_on_time0' : {}
	, 'target_on_time1' : {}
	, 'target_on_time2' : {}
	, 'target_on_time3' : {}
	# , 'recal' : {}
}

# add column number:
for i,k in enumerate(col_info.keys()):
	col_info[k]['col_num'] = i+1

tx_dict['writer'].put(kind="attr",payload={"dset_name":"exp","value":{'col_names':[k for k in col_info.keys()],'col_info':col_info,'inputs':inputs}})


trigger_col_info = {
	'time' : {}
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


def manual_demo():
	screen_num = 1
	done = False
	do_update = True
	while not done:
		sdl2.SDL_PumpEvents()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_KEYDOWN:
				response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower().decode()
				if response=='escape':
					exit_safely()
				elif response=='2':
					screen_num = screen_num + 1
					do_update = True
				elif response=='1':
					if screen_num>1:
						screen_num = screen_num - 1
						do_update = True
				elif response=='q':
					done = True
		if do_update:
			do_update = False
			clear_screen(grey)
			if screen_num==1:
				blit_array(fixation_pinwheel)
			elif screen_num==2:
				blit_array(fixation_pinwheel)
				draw_target('left','white','neutral')
			elif screen_num==3:
				blit_array(fixation_pinwheel)
				draw_target('left','black','neutral')
			elif screen_num==4:
				blit_array(fixation_pinwheel)
				draw_target('left','black','congruent')
			elif screen_num==5:
				blit_array(fixation_pinwheel)
				draw_target('left','black','incongruent')
			elif screen_num==6:
				draw_text('572', instruction_font, black)
			elif screen_num==7:
				draw_text('416', instruction_font, white)
			elif screen_num==8:
				blit_array(fixation_pinwheel)
			elif screen_num==9:
				blit_array(fixation_pinwheel)
				draw_target('left','white','neutral')
			elif screen_num==10:
				blit_array(fixation_pinwheel)
				draw_target('right','white','neutral')
			elif screen_num==11:
				blit_array(fixation_pinwheel)
				draw_target('up','white','neutral')
			elif screen_num==12:
				blit_array(fixation_pinwheel)
				draw_target('down','white','neutral')
			elif screen_num==13:
				blit_array(fixation_pinwheel)
			refresh_windows()




########
# Start the experiment
########

# manual_demo()

response = None
while response!='n':
	trash_response,message_viewing_time = show_message('When you are ready to begin practice, press any button.')
	run_block(0)
	response,message_viewing_time = show_message('Practice is complete.\nExperimenter: Repeat practice?',whitelist=['y','n'])

response,message_viewing_time = show_message('When you are ready to begin the experiment, press any button.')

for i in range(number_of_blocks):
	block = str(i+1)
	run_block(block)
	if i<(number_of_blocks):
		response,message_viewing_time = show_message('Take a break!\nYou\'re about '+str(block)+'/'+str(number_of_blocks)+' done.\nWhen you are ready to resume the experiment, press any button.')

# print('experiment done')
show_message('You\'re all done!\nThe experimenter will be with you momentarily.')
exit_safely()
