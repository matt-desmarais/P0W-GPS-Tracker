from os import system
import serial
import subprocess
from time import sleep
import random
import sys
import time
import json
from collections import OrderedDict
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


# Import Adafruit IO MQTT client.
from Adafruit_IO import MQTTClient

ADAFRUIT_IO_KEY      = ''
ADAFRUIT_IO_USERNAME = '' 

client = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)
# Raspberry Pi pin configuration:
RST = None     # on the PiOLED this pin isnt used
# Note the following are only used with SPI:
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0

# 128x32 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)

# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))

# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
# First define some constants to allow easy resizing of shapes.
padding = -2
top = padding
bottom = height-padding
# Move left to right keeping track of the current x position for drawing shapes.
x = 0

# Load default font.
font = ImageFont.load_default()

# Define callback functions which will be called when certain events happen.
def connected(client):
    # Connected function will be called when the client is connected to Adafruit IO.
    # This is a good place to subscribe to feed changes.  The client parameter
    # passed to this function is the Adafruit IO MQTT client so you can make
    # calls against it easily.
    cmd = "hostname -I | cut -d\' \' -f1"
    IP = subprocess.check_output(cmd, shell = True )
    cmd = "curl ifconfig.me"
    WAN = subprocess.check_output(cmd, shell = True )
    draw.text((x, top),       "Connection established",  font=font, fill=255)
    draw.text((x, top+8),     "Local IP: " + str(IP), font=font, fill=255)
    draw.text((x, top+16),    "WAN IP:" + str(WAN),  font=font, fill=255)
    draw.text((x, top+25),    "Ready to Upload",  font=font, fill=255)
    disp.image(image)
    disp.display()


def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print('Disconnected from Adafruit IO!')
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    #sys.exit(1)

# Setup the callback functions defined above.
client.on_connect    = connected
client.on_disconnect = disconnected

# Start PPPD
def openPPPD():	
	draw.rectangle((0,0,width,height), outline=0, fill=0)
	image2 = Image.open('connectingtonetwork.ppm').convert('1')
	disp.image(image2)
	disp.display()
	# Check if PPPD is already running by looking at syslog output
	output1 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
	if "secondary DNS address" not in output1 and "locked" not in output1:
		while True:
			subprocess.call("sudo poff fona", shell=True)
			# Start the "fona" process
			subprocess.call("sudo pon fona", shell=True)
			sleep(3)
			output2 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -4", shell=True)
			print output2
			print "starting fona"
			if "Connect script failed" not in output2:
				print "BREAK!!!!"+output2
				break
	# Make sure the connection is working
	while True:
		output3 = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -3", shell=True)
		print output3
		if "secondary DNS address" in output3:
			return True
# Stop PPPD
def closePPPD():
	print "turning off cell connection"
	# Stop the "fona" process
	subprocess.call("sudo poff fona", shell=True)
	# Make sure connection was actually terminated
	while True:
		output = subprocess.check_output("cat /var/log/syslog | grep pppd | tail -1", shell=True)
		if "Exit" in output:
			return True

# Check for a GPS fix
def checkForFix():
	draw.rectangle((0,0,width,height), outline=0, fill=0)
        image2 = Image.open('gpsfix.ppm').convert('1')
        disp.image(image2)
	disp.display()
	print "checking for fix"
	# Start the serial connection
	ser=serial.Serial('/dev/serial0', 115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)
	# Turn on the GPS
	ser.write("AT+CGNSPWR=1\r")
	ser.write("AT+CGNSPWR?\r")
	while True:
		response = ser.readline()
		if " 1" in response:
			break
	# Ask for the navigation info parsed from NMEA sentences
	ser.write("AT+CGNSINF\r")
	while True:
			response = ser.readline()
			# Check if a fix was found
			if "+CGNSINF: 1,1," in response:
				print "fix found"
				print response
				return True
			# If a fix wasn't found, wait and try again
			if "+CGNSINF: 1,0," in response:
				sleep(5)
				ser.write("AT+CGNSINF\r")
				print "still looking for fix"
			else:
				ser.write("AT+CGNSINF\r")

# Read the GPS data for Latitude and Longitude
def getCoord():
	draw.rectangle((0,0,width,height), outline=0, fill=0)
        image2 = Image.open('gpscoord.ppm').convert('1')
        disp.image(image2)
        disp.display()
	# Start the serial connection
	ser=serial.Serial('/dev/serial0', 115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)
	ser.write("AT+CGNSINF\r")
	while True:
		response = ser.readline()
		if "+CGNSINF: 1," in response:
			# Split the reading by commas and return the parts referencing lat and long
			array = response.split(",")
			lat = array[3]
			print lat
			lon = array[4]
			print lon
			alt = array[5]
			print alt
			return (lat,lon,alt)


# Start the program by opening the cellular connection
if openPPPD():
	draw.rectangle((0,0,width,height), outline=0, fill=0)
        image2 = Image.open('catgps.ppm').convert('1')
        disp.image(image2)
        disp.display()	
	sleep(10)	
	while True:
		# Close the cellular connection
		if closePPPD():
			print "closing connection"
			sleep(1)
		# Check for GPS Fix
		if checkForFix():
			# Get lat and long
			if getCoord():

				latitude, longitude, altitude = getCoord()
				coord = str(latitude) + "," + str(longitude) + "," + str(altitude)
				print coord
				with open("path.txt", "a") as file:
				    file.write(coord)
				# Buffer the coordinates to be streamed
				d = OrderedDict()
				d['value'] = 23
				d['lat'] = latitude
				d['lon'] = longitude
				d['ele'] = altitude
				print "dump:",json.dumps(d)
				 # Draw a black filled box to clear the image.
				draw.rectangle((0,0,width,height), outline=0, fill=0)
				draw.text((x, top),       "Time: " + datetime.datetime.now().strftime('%H:%M:%S'),  font=font, fill=255)
				draw.text((x, top+8),     "Lat: " + str(latitude), font=font, fill=255)
				draw.text((x, top+16),    "Long: " + str(longitude),  font=font, fill=255)
				draw.text((x, top+25),    "Alt: " + str(altitude),  font=font, fill=255)
				# Display image.
				disp.image(image)
				disp.display()
				sleep(3)

		if openPPPD():
			client.connect()
			sleep(1)
			draw.rectangle((0,0,width,height), outline=0, fill=0)
			image2 = Image.open('Adafruit-IO-Logo.ppm').convert('1')
			disp.image(image2)
			disp.display()

			client.publish('gpsdata',json.dumps(d))
