#
# PianoLights, when somebody sits behind piano the lights will go on.
#
# M.Tossaint
# Feb 2016
#

#########################################
# IMPORT
# MODULES
#########################################

import time
import os
import threading
import datetime
from datetime import timedelta
from datetime import date
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

#########################################
# LOCAL
# CONFIG
#########################################

PinCandleLeft = 8           # Pin for left candle LED
PinCandleRight = 7          # Pin for left candle LED
PinStarLights = 6           # Pin for starlights
PinMotionDetect = 15        # Pin for PIR motion detect sensor

TimeOutLights = 5           # After x seconds lights turn off again

GPIO.setup(PinCandleLeft, GPIO.OUT)
GPIO.setup(PinCandleRight, GPIO.OUT)
GPIO.setup(PinStarLights, GPIO.OUT)
GPIO.setup(PinMotionDetect, GPIO.IN)

GPIO.output(PinStarLights,GPIO.LOW)    
GPIO.output(PinCandleLeft,GPIO.LOW)
GPIO.output(PinCandleRight,GPIO.LOW)

motiondetected = datetime.datetime(1,1,1) # Initialise for first use

#########################################
# FUNCTIONS
#########################################

def Motion():
    motiondetected = datetime.datetime.now()

def CandleCtrl():
	while True:
		timesincemotion = datetime.datetime.now() - motiondetected
                if timesincemotion.total_seconds() < TimeOutLights:
			GPIO.output(PinCandleLeft,GPIO.HIGH)
			GPIO.output(PinCandleRight,GPIO.HIGH)
			GPIO.output(PinStarLights,GPIO.HIGH)
	        else:
		        GPIO.output(PinCandleLeft,GPIO.LOW) 
		        GPIO.output(PinCandleRight,GPIO.LOW) 
		        GPIO.output(PinStarLights,GPIO.LOW)
		time.sleep(1)

MidiThread = threading.Thread(target=CandleCtrl)
MidiThread.daemon = True
MidiThread.start()

GPIO.add_event_detect(PinMotionDetect, GPIO.RISING, callback=Motion()) # Whenever the pin rises the interrupt is called
while 1: # do not close the program, but keep on looking for the interrupt
    time.sleep(100)
