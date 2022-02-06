#!/usr/bin/env python2
import socket
import struct
import random

mysock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
mysock.bind(('0.0.0.0', 2000))

RESPONSE = {
0x01 : '\x0E\x31', # Koelwatertemperatuur, 1lsb = 0.1 degC, 0 = -273.3
0x02 : '\x0E\x31', # Olie temperatuur???? lengte is gegokt!
0x03 : '\x0B\x76', # Inlaatluchttemperatuur, format = koelwatertemp
0x07 : '\x0E\x10', # MAP, 1lsb = 0.01kpa, 0=0
0x08 : '\x01\xE0', # TPS, 1lsb = 0.01deg., 0=0
0x09 : '\x00\x00', # RPM
0x0A : '\x00\x80\x00\x20\x07\xb1\x27\x10\x00\x00\x00\x00\x00\x00', # O2 sensor first 2 bytes: feedback, 0.01%, next 2 bytes: voltage, 1 lsb = 1 mv.
0x0E : 'aaddjjmmpp000022',
0x0F : '\x08',     # Gaspedaal status (bit0, 0=stationair), contactslot (bit 1, 1=aan), airco(bit 3, 1=aan)
0x10 : '\x40\x00\x40\x00', # Accuspanning (byte 0 en 1) 00 01 = 1mV. Byte 2 en 3 nogmaals accu spanning in 1mv. 2e is iets hoger...
0x11 : '\x00\x00\x00\x00\x00', # o.a. krukas en nokas sync (1 = error), byte 0: bit0 = nokkenas, bit1=krukas
0x12 : '\x00\x20', # Stappenmotorstand, 1lsb = 0.5step
0x13 : '\x00', # Unknown, lambda status?
0x15 : '', # Unknown, stepper position?
0x19 : '\x00\x00\x00\x00\x00', # DTC?
0x20 : '\x00\x87\x27\x01',
0x21 : '\x00\x00', # RPM Error, lengte gegokt
0x32 : 'adjmp002' + 'adhme0024117' + '    ',
0x33 : 'TPUM0101' + 'adjmp002',
0x3A : '\x01\x01\x00\x00', # Offset ignition (byte 0 and 1, signed 0.1 deg) and rpm (byte 2 and 3), lengte gegokt!
}

challenge = 0

def process_obd(message):
	#print "Got EOBD message: ", repr(message)
	global challenge

	checksum = 0
	for i in message[0:-1]:
		checksum += ord(i)
	assert (checksum % 256) == ord(message[-1])
	assert ord(message[0]) == len(message) - 2
	contents = message[1:-1]
	cmd = ord(contents[0])

	# Default: Ack by making bit 6 high
	reply = chr(cmd + 0x40)
	if cmd == 0x27:
		if contents[1] == chr(1):
			reply += chr(1) + struct.pack('<H', challenge)
		elif contents[1] == chr(2):
			response = struct.unpack('<H', contents[2:4])[0]
			print "Challenge: 0x%x, response: 0x%x"%(challenge, response)
			myfile = open('challenge-response-auto.log', 'a')
			myfile.write("c = 0x%04x, r = 0x%04x\n"%(challenge, response))
			myfile.close()
			reply += chr(2)
			challenge += 1
	elif cmd == 0x21:
		info = contents[1]
		print "Fetched data 0x%x"%ord(info)
		reply += info
		reply += RESPONSE[ord(info)]
	else:
		print "Unknown CMD: 0x%X"%cmd
		print "Arguments:",repr(contents)
	reply = chr(len(reply)) + reply
	checksum = 0
	for i in reply:
		checksum += ord(i)
	reply += chr(checksum % 256)
	
	#print "Sending EOBD reply: ", repr(reply)

	return reply
	

while True:
	data, addr = mysock.recvfrom( 1024 ) # buffer size is 1024 bytes
	checksum = 0
	for i in data[0:-1]:
		checksum += ord(i)
	assert (checksum % 256) == ord(data[-1])
	assert len(data) == ord(data[3])
	
	data = data[0:-1]
	
	print "Got packet: '%s'"%repr(data)
	
	# Unknown init cmd's
	if data[0] == chr(0):
		response = '\x80\x00\x00\x1b\x00\x02\x00\x10\xc9\x03\x00\xd0\x07' + '0004d70022ca' + chr(0)
	elif data[0] == chr(4):# == '\x04\x0c\x00\x06\x00':
		response = '\x84\x16\x00\x06\x00'
	elif data[0] == chr(5):
		response = '\x85\x00\x00\x06\x00'
	elif data[0] == chr(0x33):
		if data[5] == chr(1):
			#response = '\xb3\0\0\x09\0\xc0\x4b\x03' # Blue cable detect package
			response = '\xb3\x00\x00\x09\x00\xf8\x4a\x03' # Also blue cable...
			#response = '\xb3\0\0\x09\0\x60\xa1\x08' # SPI cable detected
		else:
			response = '\xb3\x00\x00\x09\x00\x90\x60\x05' # Current clamp detected
	# Unknown, but called repeatedly to retry ecu init only when cable is detected
	elif data[0] == chr(0x10):
		response = '\x90\x00\x00\x06\x00'
	# Something like request break? Also called repeatedly only when cable is detected.
	elif data[0] == chr(0x11): # MEMS 2J: 11:0c:00:0a:00  01:69:01:00
							   # MEMS 1.9:11:09:00:09:00  01:20:08 			
							   # Rover 200 L-series bosch: 11:0d:00:12:00   04:50:07:63:10:00:68:14:00:69:00:00 
							   # Rover 200 Copy'd on L-line?
		response = '\x91\x00\x00\x06\x00'
	elif data == '\x12\x0c\x00\x0b\x00\x81\x13\xf7\x81\x0c' or \
		data == '\x12\x00\x00\x0b\x00\x81\x13\xf7\x81\x0c': # Allow second char to be 0
		# Request send data with init?? For now just fixed response..
		response = '\x92\x00\x00\x0b\x00\x03\xc1\xd5\x8f\x28'
	elif data[0] == chr(0x20):
		reply = process_obd(data[5:])
		response = '\xa0\x00\x00' + chr(len(data) + 6) + '\x00' + reply
	elif data == '\x13\x0c\x00\x0c\x00\xb8\x0b\x02\x3e\x01\x41' or \
		data == '\x13\x00\x00\x0c\x00\xb8\x0b\x02\x3e\x01\x41': # Allow second char to be 0
		# Set keep-alive, just ack for now.
		response = '\x93\x00\x00\x08\x00\xff\xff\x99'
	elif data[0] == chr(0x32):
		response = '\xb2\x00\x00\x09\x00\x10\x27\x00' # actual voltage data, 00 ff ff ff = 0v...
		# 01 02 03 04 = 26.29v
		# 01 02 03 03 = 19.73v
		# 01 02 02 03 = 19.71v
		# 01 01 02 03 = 19.71v
		# 02 01 02 03 = 19.71v
		# 02 01 00 01 = 6.55v
		# (Laate 3 byts l.e. = reading, 1lsb = 0.1mv or 0.1ohm or 0.01A or 0.02kpa
		# 0x4364 = 100.0 kpa 
		# 0x4000 = 88.03 kpa
		# 0x2710 = 0 kpa (Absolute...)
		# 7252 lsb == 100kpa
	elif data[0] == chr(0x13):
		response = '\x93\x00\x00\x08\x00\xd0\x07'
	elif data[0] == chr(0x1):
		myfile = open('testbook_fw.bin', 'a')
		myfile.write(data[5:-3])
		print "Wrote %d bytes"%len(data[5:-1])
		myfile.close()
		response = '\x81\0\0\x06\0'
	else:
		print "Unknown UDP command:", repr(data)
		response = chr(ord(data[0]) + 0x80) + '\0\0\x06\0'
	checksum = 0
	for i in response:
		checksum += ord(i)
	response += chr(checksum % 256)
	
	mysock.sendto(response, addr)
