import time
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

pirpin=15
GPIO.setup(pirpin, GPIO.IN)

def Motion(pirpin):
    print('Motion detected')

GPIO.add_event_detect(pirpin,GPIO.RISING,callback=Motion)

while 1:
    time.sleep(100)
