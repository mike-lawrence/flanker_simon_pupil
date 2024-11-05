########
# Initialize debugger & check for expected variables
########
from file_forker import debug_class
debug = debug_class('qc')
debug.print('I am running')
debug.check_vars(['rx_dict', 'tx_dict'])

#library imports
import sys
if sys.platform=='darwin':
	import appnope
	appnope.nope()
import sdl2 #for input and display
import sdl2.ext #for input and display
from PIL import Image #for image manipulation
import aggdraw #for drawing
import numpy as np
import time
import copy
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


stimDisplayRes = (1000,250) #pixel resolution of the stimDisplay

sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
stimDisplay = sdl2.ext.Window("Signal Quality (any blinking paths are bad!)", size=stimDisplayRes,position=(100,100),flags=sdl2.SDL_WINDOW_SHOWN)
stimDisplaySurf = sdl2.SDL_GetWindowSurface(stimDisplay.window)
stimDisplayArray = sdl2.ext.pixels3d(stimDisplaySurf.contents)
for i in range(5):
	sdl2.SDL_PumpEvents() #to show the windows

########
#Define some useful colors
########
white = sdl2.pixels.SDL_Color(r=255, g=255, b=255, a=255)
black = sdl2.pixels.SDL_Color(r=0, g=0, b=0, a=255)
red = sdl2.pixels.SDL_Color(r=255, g=0, b=0, a=255)
green = sdl2.pixels.SDL_Color(r=0, g=255, b=0, a=255)


sdl2.sdlttf.TTF_Init()


font = sdl2.sdlttf.TTF_OpenFont(str.encode('./stimuli/fonts/DejaVuSans.ttf'), 50)

def draw_letters():
	text = str.encode('F')
	surface = sdl2.sdlttf.TTF_RenderText_Blended(font,text,white).contents
	sdl2.SDL_BlitSurface(surface, None, stimDisplaySurf, sdl2.SDL_Rect(
		  int(stimDisplay.size[0]/2 - surface.w/2)
		, 0#int(surface.h/8)
		,surface.w
		,surface.h
	))
	text = str.encode('L')
	surface = sdl2.sdlttf.TTF_RenderText_Blended(font,text,white).contents
	sdl2.SDL_BlitSurface(surface, None, stimDisplaySurf, sdl2.SDL_Rect(
		  int(stimDisplay.size[0]/4 - surface.w/2)
		, int(stimDisplay.size[1]/2 - surface.h/2)
		,surface.w
		,surface.h
	))
	text = str.encode('R')
	surface = sdl2.sdlttf.TTF_RenderText_Blended(font,text,white).contents
	sdl2.SDL_BlitSurface(surface, None, stimDisplaySurf, sdl2.SDL_Rect(
		  int(stimDisplay.size[0]/4*3 - surface.w/2)
		, int(stimDisplay.size[1]/2 - surface.h/2)
		,surface.w
		,surface.h
	))
	sdl2.SDL_UpdateWindowSurface(stimDisplay.window)
	sdl2.SDL_FreeSurface(surface)


# sdl2.SDL_BlitSurface(surface, None, stimDisplaySurf, sdl2.SDL_Rect(
# 	  int(stimDisplay.size[0]/2 - loc[0] - surface.w/2)
# 	, int(stimDisplay.size[1]/2 - loc[1] - surface.h/2)
# 	,surface.w
# 	,surface.h
# ))
path_start_end_list = {

	'F3_D3': {
		'start': [5,5]
		, 'end': [3,3]
	}

	, 'F3_D1': {
		'start': [5,5]
		, 'end': [7,3]
	}

	, 'R3_D3': {
		'start': [3,3]
		, 'end': [5,1]
	}

	, 'R3_D1': {
		'start': [5,1]
		, 'end': [7,3]
	}


	, 'F4_D2': {
		'start': [12,3]
		, 'end': [14,5]
	}

	, 'F4_D4': {
		'start': [14,5]
		, 'end': [16,3]
	}


	, 'R4_D2': {
		'start': [12,3]
		, 'end': [14,1]
	}

	, 'R4_D4': {
		'start': [14,1]
		, 'end': [16,3]
	}

	, 'S1_D1': {
		'start': [7,3]
		, 'end': [8,3]
	}
	, 'S2_D2': {
		'start': [11,3]
		, 'end': [12,3]
	}
	, 'S3_D3': {
		'start': [2,3]
		, 'end': [3,3]
	}
	, 'S4_D4': {
		'start': [16,3]
		, 'end': [17,3]
	}
}

pen_width = int(np.min(stimDisplay.size)*.05)
red_pen = aggdraw.Pen(color='red',width=pen_width,opacity=255)
blue_pen = aggdraw.Pen(color='blue',width=pen_width,opacity=255)
red_brush = aggdraw.Brush(color='red',opacity=255)
blue_brush = aggdraw.Brush(color='blue',opacity=255)
white_brush = aggdraw.Brush(color='white',opacity=255)


def draw_path(start_end,path,nm):
	fr = path[0:1]

	start = copy.deepcopy(start_end['start'])
	end = copy.deepcopy(start_end['end'])

	# end[0] *= 100
	# end[1] *= 100
	if start[0]<end[0]:
		xmult = 1
	else:
		xmult = -1

	if start[1]<end[1]:
		ymult = 1
	else:
		ymult = -1

	if fr=='R':
		yshift = -1
	else:
		yshift = 1

	start[0] -= 1.5
	if start[0]>9:
		start[0] -= 2

	if fr=='S':
		if path[-1:] in ['1','4']:
			start[0] -= .25
		else:
			start[0] += .25
	# start[1] += .5

	col_width = 1/14.0*stimDisplay.size[0]
	row_height = 1/6.0*stimDisplay.size[1]

	start[0] *= col_width
	start[1] *= row_height

	start[1] += yshift*pen_width
	if nm=='hi':
		pen = red_pen
		brush = red_brush
		start[1] -= pen_width/2
		xp = .4
		circ_mult = 1
	else:
		pen = blue_pen
		brush = blue_brush
		start[1] += pen_width/2
		xp = .4
		circ_mult = -1

	if(start_end['start'][1]==start_end['end'][1]):
		tool = brush
		start[1] -= pen_width
		start[1] += pen_width*circ_mult/2
		#hi circle: M0,0 a .5 .5 0 0 1 1 0 z
		#lo circle: M0,0 a .5 .5 0 0 0 1 0 z
		#M 0,.5 C 0,.25 .25,0 .5,0 C .75,0 1,.25 1,.5 z
		#M 0,0  c  0,-.25    .25,-.5    .5,-.5     c .25,0    .5,.25   .5,.5
		pathstring = [
			'M'
			+ str(start[0])
			+ ','
			+ str(start[1])

			+ ' c 0,'
			+ str(-circ_mult*col_width/4)

			+ ' '
			+ str(col_width/4)
			+ ','
			+ str(-circ_mult*col_width/2)

			+ ' '
			+ str(col_width/2)
			+ ','
			+ str(-circ_mult*col_width/2)

			+ ' c '
			+ str(col_width/4)
			+ ',0'

			+ ' '
			+ str(col_width/2)
			+ ','
			+ str(circ_mult*col_width/4)

			+ ' '
			+ str(col_width/2)
			+ ','
			+ str(circ_mult*col_width/2)

			+ 'z'
		]
	else:
		tool = pen
		pathstring = [
			'M'
			+ str(start[0])
			+ ','
			+ str(start[1])

			+ ' q'
			+ str(xmult*col_width*xp)
			+ ',0 '

			+ str(xmult*col_width)
			+ ','
			+ str(ymult*row_height)

			+ ' q'
			+ str(xmult*col_width*(1-xp))
			+ ','
			+ str(ymult*row_height)
			+ ' '

			+ str(xmult*col_width)
			+ ','
			+ str(ymult*row_height)
		]
	# M0,0 Q400,0 1000,1000 Q1600,2000 2000,2000
	# pathstring = 'm0,0 c300,300,700,600,300,900'
	#print(pathstring)
	symbol = aggdraw.Symbol(pathstring[0])
	draw.symbol([0,0], symbol, tool)
	return(None)

def imageToArray(_Image):
	return np.rot90(np.fliplr(np.asarray(_Image)))


def draw_ellipse(row,col):
	col_width = 1/14.0*stimDisplay.size[0]
	row_height = 1/6.0*stimDisplay.size[1]
	x = row*col_width
	y = col*row_height
	size = col_width*.5
	draw.ellipse([
			  x-size/2
			, y-size/2
			, x+size/2
			, y+size/2
		]
		,white_brush
	)
	return(None)


loop_count = 0
last_rows = 0
while True:
	sdl2.SDL_PumpEvents()
	events = sdl2.ext.get_events()
	for event in events:
		if event.type == sdl2.SDL_QUIT:
			tx_dict['parent'].put(kind='stop')
	loop_count += 1
	if loop_count>=10:
		loop_count = 0
	time.sleep(0.01) #to reduce cpu load
	#handle messages received
	if not rx_dict['parent'].empty():
		message = rx_dict['parent'].get()
		if message.kind=='stop':
			debug.print('Stopping')
			sys.exit()
	#check for new data 
	nirs = store['nirs']
	# if nirs.shape[0]>last_rows:
	# 	last_rows = nirs.shape[0]
	# 	print({'shape':nirs.shape,'data':nirs[-1,:]})
	if nirs.shape[0]>1:
		im = Image.new('RGBA',stimDisplay.size)
		draw = aggdraw.Draw(im)
		draw.setantialias(True)
		# for path in path_dict.keys():
		for index,value in enumerate(col_names):
			if len(value)==8:
				path = value
				value = nirs[-1,index]
				nm = path[-2:].lower()
				path = path[0:-3]
				do_draw = True
				if (loop_count>=5) and (((value<1e2)and(value>-8e3) ) or (value>5e3)):
					do_draw = False
				if do_draw:
					draw_path(start_end=path_start_end_list[path],path=path,nm=nm)
		draw_ellipse(3.5,5.25)
		draw_ellipse(3.5,.75)
		draw_ellipse(10.5,5.25)
		draw_ellipse(10.5,.75)
		draw.flush()
		stimDisplayArray[:,:,:] = imageToArray(im)
		draw_letters()
		stimDisplay.refresh()
		time.sleep(1.0/60)
