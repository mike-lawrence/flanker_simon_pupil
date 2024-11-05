import usb
import sys
import time

dev = usb.core.find(idVendor=0x045e, idProduct=0x028e) 
# dev = usb.core.find(idVendor=0x057e, idProduct=0x2009) 

if dev.is_kernel_driver_active(0):
	dev.detach_kernel_driver(0)

dev.set_configuration()
usb.util.claim_interface(dev, 0)

read_endpoint = dev[0][(1, 0)][0]  # Endpoint 0x81 (IN)
write_endpoint = dev[0][(1, 0)][1]  # Endpoint 0x01 (OUT)

dev.write(write_endpoint,"\x01\x03\x00",0)



# Continuous loop to read packets
try:
	while True:
		try:
			data = dev.read(read_endpoint.bEndpointAddress, read_endpoint.wMaxPacketSize, timeout=0)
			print(f"Data: {data}")
		except usb.core.USBError as e:
			if e.errno == 110:  # Timeout error code
				print("Timeout, no data yet.")
			else:
				print(f"USB Error: {e}")
		time.sleep(0.1)  # Add a small sleep to avoid high CPU usage
finally:
	usb.util.release_interface(dev, 0)
	dev.attach_kernel_driver(0)
	sys.exit()
