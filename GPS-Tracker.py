import logging
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
import datetime
import RPi.GPIO as GPIO            # import RPi.GPIO module  
from time import sleep             # lets us have a delay  
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)             # choose BCM or BOARD  
GPIO.setup(18, GPIO.OUT)

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import re
from squid import *

rgb = Squid(16, 20, 21)

# Import Adafruit IO MQTT client.
from Adafruit_IO import MQTTClient

ADAFRUIT_IO_KEY      = 'YOURKEYHERE'
ADAFRUIT_IO_USERNAME = 'YOURUSERNAME' 

client = MQTTClient(ADAFRUIT_IO_USERNAME, ADAFRUIT_IO_KEY)

filename = str(datetime.datetime.now())

logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('trackerlog.txt')
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

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

disp.begin()

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
font2 = ImageFont.truetype('/home/pi/P0W-GPS-Tracker/VCR_OSD_MONO.ttf', 16)


startTime = datetime.datetime.now()
connected = False
timesFailed = 0
latency = 0
signal = None
lat = 0
lon = 0
alt = 0
maxTries = 3
d = OrderedDict()
filename = str(datetime.datetime.now())
failedConnections = 0
failedPings = 0
sucessfulUploads = 0
#battery = None

def getSerialInfo():
	global signal, lat, lon, alt
	logging.info("getting info from serial")
	# Start the serialconnection
	ser=serial.Serial('/dev/ttyS0', 115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)
	try:
		rgb.set_color(CYAN)
		# Get signal strength
		while signal == None:
			ser.write("AT+CSQ\r")
			response = ser.readline()
			if "" is response:
				logging.info("waiting for serial device")
				draw.rectangle((0,0,width,height), outline=0, fill=0)
				image2 = Image.open('/home/pi/P0W-GPS-Tracker/serial.ppm').convert('1')
				disp.image(image2)
                                disp.display()
			#logging.info(response)
			gibberish =  '''!}!}!} }2}"}&}'''
			if gibberish in response:
				GPIO.output(18, 0)         # set GPIO18 to 0/GP$
				sleep(.1)
				rgb.set_color(WHITE)
				GPIO.output(18, 1)         # set GPIO18 to 1/GP$
				sleep(10)
				logging.info(response)
			if "+CSQ:" in response and "AT+CSQ" not in response:
				#logging.info(response)
				array = re.split('\s|,', response)
				signal = array[1] 
				if int(array[1]) < 5:
					logging.info("Bad Signal! -> "+signal)
					break 
				if int(array[1]) >= 5 and int(array[1]) < 10:
					logging.info("Decent Signal -> "+signal)
					break
				if int(array[1]) >= 10:
					logging.info("Great Signal! -> "+signal)
					break
		try:
        	        ser.reset_input_buffer()
        	except:
	                logging.info("IO ERROR resetting buffer")

		ser.write("AT+CGNSPWR=1\r")
		draw.rectangle((0,0,width,height), outline=0, fill=0)
		image2 = Image.open('/home/pi/P0W-GPS-Tracker/gpsfix.ppm').convert('1')
		disp.image(image2)
		disp.display()
		logging.info("getting GPS fix")
		while lat == 0 and lon == 0:
			ser.write("AT+CGNSINF\r")
			response = ser.readline()
			#logging.info(response)
			# Check if a fix was found
			if "+CGNSINF: 1,1," in response and ",,,," not in response:
				with open(filename+"-nmea.txt", "a") as file:
					file.write(response)
				logging.info("fix found")
				logging.info(response)
				array = response.split(",")
				#logging.info(array)
				lat = array[3]
				logging.info("latitude: "+lat)
				lon = array[4]
				logging.info("longitude: "+lon)
				alt = array[5]
				logging.info("altitude: "+alt)
				draw.rectangle((0,0,width,height), outline=0, fill=0)
				draw.text((x, top),       "Time: " + datetime.datetime.now().strftime('%H:%M:%S'),  font=font, fill=255)
				draw.text((x, top+8),     "Lat: " + str(lat), font=font, fill=255)
				draw.text((x, top+16),    "Long: " + str(lon),  font=font, fill=255)
				draw.text((x, top+25),    "Alt: " + str(alt),  font=font, fill=255)
				disp.image(image)
				disp.display()
				coord = str(lat) + "," + str(lon) + "," + str(alt)
				with open(filename+"-path.txt", "a") as file:
	                                file.write(coord)
				break
			#rgb.set_color(CYAN)
	except serial.serialutil.SerialException:
                logging.info("serial exception")
                getSerialInfo()
	try:
		ser.reset_input_buffer()
	except:
		logging.info("IO ERROR resetting buffer")
	ser.close()
# Start PPPD
def openPPPD():
	global failedConnections, timesFailed, lat, lon, alt, signal, connected, maxTries
	while timesFailed < maxTries:
		while True:
			rgb.set_color(BLUE)
			subprocess.call("sudo poff fona", shell=True)
			# Start the "fona" process
			subprocess.call("sudo pon fona", shell=True)
			sleep(2)
			output2 = subprocess.check_output("cat /var/log/syslog | grep -a pppd | tail -4", shell=True)
			#logging.info("output2"+output2+"output2")
			logging.info("started pppd fona")
			#	logging.info("GIBBERISH\nGIBBERISH\nGIBBERISH") 
			if "Connect script failed" not in output2:
				#logging.info(output2)
				logging.info("Connect script running")
				draw.rectangle((0,0,width,height), outline=0, fill=0)
				image2 = Image.open('/home/pi/P0W-GPS-Tracker/connectingtonetwork.ppm').convert('1')
				disp.image(image2)
				disp.display()
				break
		# Make sure the connection is working
		while True:
			output3 = subprocess.check_output("cat /var/log/syslog | grep -a pppd | tail -1", shell=True)
			#logging.info("OUTPUT3\n"+output3+"\nOUTPUT3")
			if "DNS address" in output3:
				logging.info("connection established")
				rgb.set_color(GREEN)
				subprocess.call("sudo route add default ppp0", shell=True)
				logging.info("defualt route set")
				connected = True
				timesFailed = maxTries
				break
			if "Connect script failed" in output3 or "terminated" in output3 or "Modem hangup" in output3:
				logging.info("FAILED RESTARTING")
				rgb.set_color(RED)
				timesFailed = timesFailed + 1
				failedConnections = failedConnections + 1
				logging.info("failed "+str(timesFailed)+" times")
				draw.rectangle((0,0,width,height), outline=0, fill=0)
				draw.text((x, top+8),"Failed "+str(timesFailed)+"/"+str(maxTries), font=font2, fill=255)
				disp.image(image)
				disp.display()
				break
			
def upload():
	global sucessfulUploads, failedPings, signal, lat, lon, alt, latency, timesFailed

	proc = subprocess.Popen(["fping", "io.adafruit.com", "-c", "1", "-q"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	junk, out = proc.communicate()
	#logging.info("out: "+out)
	if '%loss = 1/0/100%' in out or "" is out:
		logging.info("Packet loss")
		rgb.set_color(RED)
		time.sleep(1)
		failedPings = failedPings + 1
	elif "io.adafruit.com : xmt/rcv/%loss = 1/1/0%" in out:
		try:
			draw.rectangle((0,0,width,height), outline=0, fill=0)
			image2 = Image.open('/home/pi/P0W-GPS-Tracker/Adafruit-IO-Logo.ppm').convert('1')
			disp.image(image2)
			disp.display()
			array = re.split("/+", out)
	        	#print array
			latency = array[7]
			logging.info('Latency: '+latency+'ms')
			d['value'] = signal
			d['lat'] = lat
			d['lon'] = lon
			d['ele'] = alt
			client.connect()
			client.publish('gpsdata',json.dumps(d))
			rgb.set_color(PURPLE)
			logging.info("Published to IO")
			sleep(2)
			sucessfulUploads = sucessfulUploads + 1
			draw.rectangle((0,0,width,height), outline=0, fill=0)
			disp.image(image)
			disp.display()
		except Exception as e:
                        logging.info("Connection error: "+str(e))

def resetVars():
	global signal, connected, lat, lon, alt, timesFailed, battery
	connected = False
        signal = None
        lat = 0
        lon = 0
        alt = 0
        timesFailed = 0
	battery = None
	rgb.set_color(OFF)

try:
	GPIO.output(18, 0)         # set GPIO24 to 0/GPIO.LOW/False  
	sleep(.1)
	GPIO.output(18, 1)         # set GPIO24 to 0/GPIO.LOW/False  
	draw.rectangle((0,0,width,height), outline=0, fill=0)
	image2 = Image.open('/home/pi/P0W-GPS-Tracker/catgps.ppm').convert('1')
	disp.image(image2)
	disp.display()	
	sleep(5)
	draw.rectangle((0,0,width,height), outline=0, fill=0)
	disp.image(image)
        disp.display()	

	while True:
		subprocess.call("sudo poff fona", shell=True)
		getSerialInfo()
		openPPPD()
		if connected:
			upload()
		resetVars()

finally:
	logging.info("Finally")
	totalTime = datetime.datetime.now()-startTime
	logging.info(totalTime)
	logging.info("Total events: "+str(failedConnections+failedPings+sucessfulUploads))
	logging.info("failedConnections: "+str(failedConnections))
	logging.info("failedPings: "+str(failedPings))
	logging.info("sucessfulUploads: "+str(sucessfulUploads))
	logging.info("time/upload: "+str(totalTime/sucessfulUploads))
