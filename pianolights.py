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
GPIO.setwarnings(False)

#########################################
# LOCAL
# CONFIG
#########################################

PinCandleLeft = 13 # Pin for left candle LED
PinCandleRight = 4 # Pin for right candle LED
PinStarLights = 10 # Pin for starlights
PinMotionDetect = 15 # Pin for PIR motion detect sensor

TimeOutLights = 5 # After x seconds lights turn off again

GPIO.setup(PinCandleLeft, GPIO.OUT)
GPIO.setup(PinCandleRight, GPIO.OUT)
GPIO.setup(PinStarLights, GPIO.OUT)
GPIO.setup(PinMotionDetect, GPIO.IN)

motiondetected = datetime.datetime.now() # Initialise for first use
GPIO.remove_event_detect(PinMotionDetect)

#########################################
# FUNCTIONS
#########################################

def Motion(PinMotionDetect):
    global motiondetected
    motiondetected = datetime.datetime.now()
    print('Detected motion')

def LightControl():
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

#########################################
# START MAIN PROGRAM
#########################################

GPIO.output(PinStarLights,GPIO.LOW)    
GPIO.output(PinCandleLeft,GPIO.LOW)
GPIO.output(PinCandleRight,GPIO.LOW)

MidiThread = threading.Thread(target=LightControl)
MidiThread.daemon = True
MidiThread.start()

GPIO.add_event_detect(PinMotionDetect, GPIO.BOTH, callback=Motion) # Whenever the pin rises the interrupt is called

while 1: # do not close the program, but keep on looking for the interrupt
    time.sleep(100)
