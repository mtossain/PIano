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

candleleftpin = 8                       # Pin for left candle LED
candlerightpin = 7                      # Pin for left candle LED
starpin = 6                             # Pin for starlights
pirpin = 10                             # Pin for PIR motion detect sensor

GPIO.setup(candleleftpin, GPIO.OUT)
GPIO.setup(candlerightpin, GPIO.OUT)
GPIO.setup(starpin, GPIO.OUT)
GPIO.setup(pirpin, GPIO.IN)

GPIO.output(starpin,GPIO.LOW)    
GPIO.output(candleleftpin,GPIO.LOW)
GPIO.output(candlerightpin,GPIO.LOW)

motiondetected = datetime.datetime(1,1,1)

#########################################
# FUNCTIONS
#########################################

def MOTION(PIR_PIN):
    motiondetected = datetime.datetime.now()

def CandleCtrl():
	
	while True:
		
		timesincemotion = datetime.datetime.now() - motiondetected

		if timesincemotion.total_seconds() < 5*60: # after x seconds switch off candles
			GPIO.output(candleleftpin,GPIO.HIGH) # Put the left LED on
			GPIO.output(candlerightpin,GPIO.HIGH) # Put the right LED on
			GPIO.output(starpin,GPIO.HIGH)

		else:
			GPIO.output(candleleftpin,GPIO.LOW) # Put the left LED off
			GPIO.output(candlerightpin,GPIO.LOW) # Put the right LED off
			GPIO.output(starpin,GPIO.LOW)
		
		time.sleep(1)


MidiThread = threading.Thread(target=CandleCtrl)
MidiThread.daemon = True
MidiThread.start()

# Whenever the pin rises the interrupt is called
GPIO.add_event_detect(pirpin, GPIO.RISING, callback=MOTION)
# do not close the program, but keep on looking for the interrupt
while 1:
    time.sleep(100)
