viewing_distance = 100
stim_display_width = 100
stim_display_res = (2560,1440)
stim_display_position = (-2560,0)
mirror_display_position = (0,0)
calibration_dot_size_in_degrees = 1
mirror_down_size = 2
manual_calibration_order = True

import numpy #for image and display manipulation
import scipy.misc #for image and display manipulation
import math #for trig and other math stuff
import sys #for quitting
import sdl2
import sdl2.ext
import random
import time
from PIL import Image
import numpy as np


def resize_image(image_array, size):
	image = Image.fromarray(image_array.transpose(1,0,2))
	resized_image = image.resize(size, Image.NEAREST)
	resized_image_array = np.array(resized_image).transpose(1,0,2)
	return resized_image_array


#define a function that gets the time (unit=seconds,zero=?)
def get_time():
	return time.perf_counter()

def list_map_int(i):
	return(list(map(int,i)))

#initialize video
sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
# sdl2.SDL_SetHint("SDL_HINT_VIDEO_MINIMIZE_ON_FOCUS_LOSS","0")
mirror_window = sdl2.ext.Window(
	"Mirror"
	, size = list_map_int(
		(
			stim_display_res[0]/mirror_down_size
			, stim_display_res[1]/mirror_down_size
		)
	)
	, position = mirror_display_position
	, flags = sdl2.SDL_WINDOW_SHOWN
)
mirror_display_surf = sdl2.SDL_GetWindowSurface(mirror_window.window)
mirror_display_array = sdl2.ext.pixels3d(mirror_display_surf.contents)
# stim_display = sdl2.ext.Window("Calibration",size=stim_display_res,position=stim_display_position,flags=sdl2.SDL_WINDOW_SHOWN|sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP|sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC)
window = sdl2.ext.Window(
	"Calibration"
	, size = list_map_int(stim_display_res)
	, position = stim_display_position
	# , flags = sdl2.SDL_WINDOW_SHOWN|sdl2.SDL_WINDOW_BORDERLESS|sdl2.SDL_RENDERER_ACCELERATED | sdl2.SDL_RENDERER_PRESENTVSYNC
	, flags = 
		sdl2.SDL_WINDOW_SHOWN
		| sdl2.SDL_WINDOW_BORDERLESS
		| sdl2.SDL_RENDERER_PRESENTVSYNC
)
window_surf = sdl2.SDL_GetWindowSurface(window.window)
window_array = sdl2.ext.pixels3d(window_surf.contents)
sdl2.SDL_PumpEvents() #to show the windows
sdl2.SDL_PumpEvents() #to show the windows
sdl2.SDL_PumpEvents() #to show the windows
sdl2.SDL_PumpEvents() #to show the windows
sdl2.SDL_PumpEvents() #to show the windows
sdl2.SDL_PumpEvents() #to show the windows
########
#Perform some calculations to convert stimulus measurements in degrees to pixels
########
stim_display_width_in_degrees = math.degrees(math.atan((stim_display_width/2.0)/viewing_distance)*2)
ppd = stim_display_res[0]/stim_display_width_in_degrees #compute the pixels per degree (PPD)
calibration_dot_size = int(calibration_dot_size_in_degrees*ppd)
#initialize font
sdl2.sdlttf.TTF_Init()
font = sdl2.sdlttf.TTF_OpenFont(str.encode('./stimuli/fonts/DejaVuSans.ttf'), int(ppd)*2)
########
# Define some useful colors for SDL2
########
white = sdl2.pixels.SDL_Color(r=255, g=255, b=255, a=255)
black = sdl2.pixels.SDL_Color(r=0, g=0, b=0, a=255)
grey = sdl2.pixels.SDL_Color(r=127, g=127, b=127, a=255)
light_grey = sdl2.pixels.SDL_Color(r=200, g=200, b=200, a=255)
def draw_dot(loc):
	cy,cx = loc
	cx =  stim_display_res[1]/2 + cx
	cy =  stim_display_res[0]/2 + cy
	radius = calibration_dot_size/2
	y, x = numpy.ogrid[-radius: radius, -radius: radius]
	index = numpy.logical_and( (x**2 + y**2) <= (radius**2) , (x**2 + y**2) >= ((radius/4)**2) )
	window_array[ (cy-radius):(cy+radius) , (cx-radius):(cx+radius) , ][index] = [255,255,255,255]

calibration_locations = dict()
calibration_locations['CENTER'] = numpy.array([0,0])
calibration_locations['N'] = numpy.array([0,int(0-stim_display_res[1]/2.0+calibration_dot_size)])
calibration_locations['S'] = numpy.array([0,int(0+stim_display_res[1]/2.0-calibration_dot_size)])
calibration_locations['E'] = numpy.array([int(0-stim_display_res[0]/2.0+calibration_dot_size),0])
calibration_locations['W'] = numpy.array([int(0+stim_display_res[0]/2.0-calibration_dot_size),0])
calibration_locations['NE'] = numpy.array([int(0+stim_display_res[0]/2.0-calibration_dot_size),int(0-stim_display_res[1]/2.0+calibration_dot_size)])
calibration_locations['SE'] = numpy.array([int(0+stim_display_res[0]/2.0-calibration_dot_size),int(0+stim_display_res[1]/2.0-calibration_dot_size)])
calibration_locations['NW'] = numpy.array([int(0-stim_display_res[0]/2.0+calibration_dot_size),int(0-stim_display_res[1]/2.0+calibration_dot_size)])
calibration_locations['SW'] = numpy.array([int(0-stim_display_res[0]/2.0+calibration_dot_size),int(0+stim_display_res[1]/2.0-calibration_dot_size)])
calibration_key = {'q':'NW','w':'N','e':'NE','a':'E','s':'CENTER','d':'W','z':'SW','x':'S','c':'SE'}

#define a function that will kill everything safely
def exit_safely():
	tx_dict['pytracker_cam'].put(kind='stop_queing')
	sdl2.ext.quit()
	sys.exit()

#define a function that waits for a given duration to pass
def simple_wait(duration):
	start = get_time()
	while get_time() < (start + duration):
		sdl2.SDL_PumpEvents()

#define a function to draw a numpy array on a surface centered on given coordinates
def blit_array(src,dst,x_offset=0,y_offset=0):
	x1 = dst.shape[0]/2+x_offset-src.shape[0]/2
	y1 = dst.shape[1]/2+y_offset-src.shape[1]/2
	x2 = x1+src.shape[0]
	y2 = y1+src.shape[1]
	dst[x1:x2,y1:y2,:] = src

def blit_surf(src_surf,dst,dst_surf,x_offset=0,y_offset=0):
	x = dst.size[0]/2+x_offset-src_surf.w/2
	y = dst.size[1]/2+y_offset-src_surf.h/2
	sdl2.SDL_BlitSurface(src_surf, None, dst_surf, sdl2.SDL_Rect(x,y,src_surf.w,src_surf.h))
	sdl2.SDL_UpdateWindowSurface(dst.window) #should this really be here? (will it cause immediate update?)

def check_for_stop():
	while not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind == 'stop':
			exit_safely()

#define a function that waits for a response
def wait_for_response():
	done = False
	while not done:
		check_for_stop()
		sdl2.SDL_PumpEvents()
		for event in sdl2.ext.get_events():
			if event.type==sdl2.SDL_KEYDOWN:
				response = sdl2.SDL_GetKeyName(event.key.keysym.sym).lower()
				if response=='escape':
					exit_safely()
				else:
					done = True
	return response

def refresh_windows():
	window.refresh()
	image = window_array[:,:,0:3]
	image = resize_image(image, mirror_display_array.shape[0:2])
	mirror_display_array[:,:,0:3] = image
	mirror_window.refresh()
	return None

def clear_screen(color):
	sdl2.ext.fill(window_surf.contents,color)

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


#define a function that prints a message on the stim_display while looking for user input to continue. The function returns the total time it waited
def show_message(my_text,lock_wait=False):
	message_viewing_time_start = get_time()
	clear_screen(black)
	refresh_windows()
	clear_screen(black)
	draw_text(my_text, font, light_grey)
	simple_wait(0.500)
	refresh_windows()
	clear_screen(black)
	if lock_wait:
		response = None
		while response not in ['return','y','n']:
			response = wait_for_response()
	else:
		response = wait_for_response()
	refresh_windows()
	clear_screen(black)
	simple_wait(0.500)
	message_viewing_time = get_time() - message_viewing_time_start
	return [response,message_viewing_time]

#define a function to show stimuli and collect calibration data
def get_calibration_data():
	if not manual_calibration_order:
		dot_location_list = ['q','w','e','a','s','d','z','x','c']
		random.shuffle(dot_location_list)
	done = False
	calibration_data = []
	start_times = []
	stop_times = []
	stop_times = []
	tx_dict['pytracker_cam'].put(kind='start_queing')
	while not done:
		if manual_calibration_order:
			dot_location = wait_for_response()
		else:
			if len(dot_location_list)==0:
				break
			else:
				dot_location = dot_location_list.pop()
		if dot_location=='0':
			phase1_done = True
		elif not dot_location in calibration_key:
			pass
		else:
			display_coords = calibration_locations[calibration_key[dot_location]]
			start_times.append(display_coords/ppd)
			clear_screen(black)
			draw_dot(display_coords)
			refresh_windows()
			junk = wait_for_response()
			stop_times.append(get_time())
			simple_wait(1)
			stop_times.append(get_time())
		while not rx_dict['pytracker_cam'].empty():
			calibration_data.append(rx_dict['pytracker_cam'].get())
	clear_screen(black)
	refresh_windows()
	tx_dict['pytracker_cam'].put(kind='stop_queing',payload=get_time())
	simple_wait(1)
	done = False
	while not done:
		if not rx_dict['pytracker_cam'].empty():
			done_queing = rx_dict['pytracker_cam'].get()
			if done_queing=='done_queing':
				done = True
			else:
				calibration_data.append(done_queing)
	calibration_data_list = []
	for i in range(len(stop_times)):
		temp = [ [list(start_times[i])[0],list(start_times[i])[1],1.0,e[1],e[2],e[1]*e[2],e[3],e[4],e[3]*e[4]] for e in calibration_data if ( (e[0]>stop_times[i]) and (e[0]<stop_times[i]) )  ]
		temp = [item for sublist in temp for item in sublist]
		calibration_data_list.append(temp)

	calibration_data_list = numpy.array([item for sublist in calibration_data_list for item in sublist])
	calibration_data_list = calibration_data_list.reshape([len(calibration_data_list)/9,9])
	return calibration_data_list

#define a function to compute prediction error
def get_errors(calibration_data_list,x_coef_left,x_coef_right,y_coef_left,y_coef_right,left_cols,right_cols):
	x_preds_left = x_coef_left[0] + x_coef_left[1]*calibration_data_list[:,left_cols[1]] + x_coef_left[2]*calibration_data_list[:,left_cols[2]] + x_coef_left[3]*calibration_data_list[:,left_cols[3]]
	x_error = y_coef_left[0] + y_coef_left[1]*calibration_data_list[:,left_cols[1]] + y_coef_left[2]*calibration_data_list[:,left_cols[2]] + y_coef_left[3]*calibration_data_list[:,left_cols[3]]
	x_error = x_coef_right[0] + x_coef_right[1]*calibration_data_list[:,right_cols[1]] + x_coef_right[2]*calibration_data_list[:,right_cols[2]] + x_coef_right[3]*calibration_data_list[:,right_cols[3]]
	x_error = y_coef_right[0] + y_coef_right[1]*calibration_data_list[:,right_cols[1]] + y_coef_right[2]*calibration_data_list[:,right_cols[2]] + y_coef_right[3]*calibration_data_list[:,right_cols[3]]
	y_error = (x_preds_left+x_error)/2
	y_preds = (x_error+x_error)/2
	x_error_mean = numpy.mean((y_error-calibration_data_list[:,0])**2)**.5
	y_error_mean = numpy.mean((y_preds-calibration_data_list[:,1])**2)**.5
	tot_error = numpy.mean((((y_error-calibration_data_list[:,0])**2)+(y_preds-calibration_data_list[:,1])**2)**.5)
	return [x_error_mean,y_error_mean,tot_error]


#start calibration
done = False
while not done:
	check_for_stop()
	show_message('When you are ready to begin calibration, press any key.')
	calibration_data_list = get_calibration_data()
	left_cols = [2,3,4,5]
	right_cols = [2,6,7,8]
	x_coef_left = numpy.linalg.lstsq(calibration_data_list[:,left_cols], calibration_data_list[:,0])[0]
	x_coef_right = numpy.linalg.lstsq(calibration_data_list[:,right_cols], calibration_data_list[:,0])[0]
	y_coef_left = numpy.linalg.lstsq(calibration_data_list[:,left_cols], calibration_data_list[:,1])[0]
	y_coef_right = numpy.linalg.lstsq(calibration_data_list[:,right_cols], calibration_data_list[:,1])[0]
	x_error_mean,y_error_mean,tot_error = get_errors(calibration_data_list,x_coef_left,x_coef_right,y_coef_left,y_coef_right,left_cols,right_cols)
	show_message('Calibration results:\nx = '+str(x_error_mean)+'\ny = '+str(y_error_mean)+'\nz = '+str(tot_error)+'\nPress any key to validate calibration.')
	validation_data_list = get_calibration_data()
	x_error_mean,y_error_mean,tot_error = get_errors(validation_data_list,x_coef_left,x_coef_right,y_coef_left,y_coef_right,left_cols,right_cols)
	done2 = False
	while not done2:
		response = show_message('Validation results:\nx = '+str(x_error_mean)+'\ny = '+str(y_error_mean)+'\nz = '+str(tot_error)+'\nExperimenter: Press "a" to accept calibration, or "r" to repeat calibration.')
		if response[0]=='a':
			tx_dict['pytracker_cam'].put(kind='calibration_coefs',payload=[x_coef_left,x_coef_right,y_coef_left,y_coef_right])
			done = True
			done2 = True
		elif response[0]=='r':
			done2 = True
exit_safely()
