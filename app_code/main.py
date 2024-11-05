#when using file_forker, it's necessary to put all the code inside a 'if __name__ == '__main__':' check
if __name__ == '__main__':

	import sys
	if sys.platform=='darwin':
		import appnope
		appnope.nope()

	from file_forker import debug_class, family_class #for easy multiprocessing
	debug = debug_class('main')

	########
	#set up family
	########

	fam = family_class()
	fam.child(file='exp.py')
	fam.child(file='cpu.py')
	# fam.child(file='eyelink.py')
	fam.child(file='pytracker_cam.py')
	fam.child(file='pytracker.py')
	# fam.child(file='pytracker_cal.py')
	# fam.child(file='ble_bg.py')
	# fam.child(file='ble.py')
	# fam.child(file='qc.py')
	# fam.child(file='viz.py')
	fam.child(file='writer.py') #writer must be last so it is the last to receive the stop command (might not be true anymore actually)

	# all the senders to writer
	fam.q_connect(
		rx_name_list=['writer']
		, tx_name_list = [
			'cpu'
			# , 'pytracker'
			# , 'eyelink'
			, 'exp'
		]
	)

	# connect eyelink to exp and vice versa
	# fam.q_connect(tx_name_list=['eyelink'],rx_name_list=['exp'])
	# fam.q_connect(rx_name_list=['eyelink'],tx_name_list=['exp'])

	# connect pytracker_cam to pytracker
	fam.q_connect(tx_name_list=['pytracker_cam'],rx_name_list=['pytracker'])

	# connect exp and children whose niceness exp will control
	# fam.q_connect(tx_name_list=['exp'],rx_name_list=['pytracker_cam'])

	# connect pytracker_cam to pytracker_cal and vice versa
	# fam.q_connect(tx_name_list=['pytracker_cam'],rx_name_list=['pytracker_cal'])
	# fam.q_connect(tx_name_list=['pytracker_cal'],rx_name_list=['pytracker_cam'])

	fam.start_and_monitor() #loops until all children self-terminate
	sys.exit()