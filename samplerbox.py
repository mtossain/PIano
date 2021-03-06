#
#  SamplerBox
#
#  author:    Joseph Ernest (twitter: @JosephErnest, mail: contact@samplerbox.org)
#  url:       http://www.samplerbox.org/
#  license:   Creative Commons ShareAlike 3.0 (http://creativecommons.org/licenses/by-sa/3.0/)
#
#  samplerbox.py: Main file
#

#########################################
# IMPORT
# MODULES
#########################################

import wave
import time
import numpy
import os
import re
import pyaudio
import threading
from chunk import Chunk
import struct
import rtmidi_python as rtmidi
import samplerbox_audio
from dotstar import Adafruit_DotStar
import datetime
from datetime import timedelta
from datetime import date
import math
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

#########################################
# LOCAL
# CONFIG
#########################################

AUDIO_DEVICE_ID = 0                     # change this number to use another soundcard
SAMPLES_DIR = "/home/pi/Music"          # The root directory containing the sample-sets. Example: "/media/" to look for samples on a USB stick / SD card
USE_SERIALPORT_MIDI = False             # Set to True to enable MIDI IN via SerialPort (e.g. RaspberryPi's GPIO UART pins)
USE_I2C_7SEGMENTDISPLAY = False         # Set to True to use a 7-segment display via I2C
USE_BUTTONS = False                     # Set to True to use momentary buttons (connected to RaspberryPi's GPIO pins) to change preset
presetuppin = 14                        # GPIO Pin If hw button used for up preset
presetdownpin = 15                      # GPIO Pin If hw button used for down preset
MAX_POLYPHONY = 80                      # This can be set higher, but 80 is a safe value
VOLUME = -1.0                           # Volume for playing, use real notation with .0!
USE_DOTSTAR = False                     # To use dotstar strip
numpixels = 60                          # Number of LEDs in dotstar strip
datapin   = 23                          # Dotstar datapin on GPIO
clockpin  = 24                          # Dotstar clockpin on GPIO
defaultcolor = 0xFFFFFF                 # White
strokecolor = 0x00FF00                  # Green
brightness = 64                         # Brightness overall between 0 and 256
USE_VOLUMESLIDER = True                 # To use hardware volume slider USB keyboard
USE_CANDLE = True                       # To light candle when piano played, auto on and auto off
candleleftpin = 8                       # Pin for left candle LED
candlerightpin = 7                      # Pin for left candle LED
AudioFramesPerBuffer=64                 # For optical 64
starpin = 6                             # pin for starlights

if USE_DOTSTAR:
    strip = Adafruit_DotStar(numpixels, datapin, clockpin) # Open strip to be used in multiple threads
    strip.begin()           # Initialize pins for output
    strip.setBrightness(brightness) # Limit brightness to ~1/4 duty cycle
    lastnoteplayed = datetime.date(1,1,1) # Dummy date long gone

if USE_CANDLE:
    lastnoteplayed = datetime.datetime(1,1,1)

#########################################
# SLIGHT MODIFICATION OF PYTHON'S WAVE MODULE
# TO READ CUE MARKERS & LOOP MARKERS
#########################################

class waveread(wave.Wave_read):

    def initfp(self, file):
        self._convert = None
        self._soundpos = 0
        self._cue = []
        self._loops = []
        self._ieee = False
        self._file = Chunk(file, bigendian=0)
        if self._file.getname() != 'RIFF':
            raise Error, 'file does not start with RIFF id'
        if self._file.read(4) != 'WAVE':
            raise Error, 'not a WAVE file'
        self._fmt_chunk_read = 0
        self._data_chunk = None
        while 1:
            self._data_seek_needed = 1
            try:
                chunk = Chunk(self._file, bigendian=0)
            except EOFError:
                break
            chunkname = chunk.getname()
            if chunkname == 'fmt ':
                self._read_fmt_chunk(chunk)
                self._fmt_chunk_read = 1
            elif chunkname == 'data':
                if not self._fmt_chunk_read:
                    raise Error, 'data chunk before fmt chunk'
                self._data_chunk = chunk
                self._nframes = chunk.chunksize // self._framesize
                self._data_seek_needed = 0
            elif chunkname == 'cue ':
                numcue = struct.unpack('<i', chunk.read(4))[0]
                for i in range(numcue):
                    id, position, datachunkid, chunkstart, blockstart, sampleoffset = struct.unpack('<iiiiii', chunk.read(24))
                    self._cue.append(sampleoffset)
            elif chunkname == 'smpl':
                manuf, prod, sampleperiod, midiunitynote, midipitchfraction, smptefmt, smpteoffs, numsampleloops, samplerdata = struct.unpack(
                    '<iiiiiiiii', chunk.read(36))
                for i in range(numsampleloops):
                    cuepointid, type, start, end, fraction, playcount = struct.unpack('<iiiiii', chunk.read(24))
                    self._loops.append([start, end])
            chunk.skip()
        if not self._fmt_chunk_read or not self._data_chunk:
            raise Error, 'fmt chunk and/or data chunk missing'

    def getmarkers(self):
        return self._cue

    def getloops(self):
        return self._loops


#########################################
# MIXER CLASSES
#
#########################################

class PlayingSound:

    def __init__(self, sound, note):
        self.sound = sound
        self.pos = 0
        self.fadeoutpos = 0
        self.isfadeout = False
        self.note = note

    def fadeout(self, i):
        self.isfadeout = True

    def stop(self):
        try:
            playingsounds.remove(self)
        except:
            pass


class Sound:

    def __init__(self, filename, midinote, velocity):
        wf = waveread(filename)
        self.fname = filename
        self.midinote = midinote
        self.velocity = velocity
        if wf.getloops():
            self.loop = wf.getloops()[0][0]
            self.nframes = wf.getloops()[0][1] + 2
        else:
            self.loop = -1
            self.nframes = wf.getnframes()

        self.data = self.frames2array(wf.readframes(self.nframes), wf.getsampwidth(), wf.getnchannels())

        wf.close()

    def play(self, note):
        snd = PlayingSound(self, note)
        playingsounds.append(snd)
        return snd

    def frames2array(self, data, sampwidth, numchan):
        if sampwidth == 2:
            npdata = numpy.fromstring(data, dtype=numpy.int16)
        elif sampwidth == 3:
            npdata = samplerbox_audio.binary24_to_int16(data, len(data)/3)
        if numchan == 1:
            npdata = numpy.repeat(npdata, 2)
        return npdata

FADEOUTLENGTH = 30000
FADEOUT = numpy.linspace(1., 0., FADEOUTLENGTH)            # by default, float64
FADEOUT = numpy.power(FADEOUT, 6)
FADEOUT = numpy.append(FADEOUT, numpy.zeros(FADEOUTLENGTH, numpy.float32)).astype(numpy.float32)
SPEED = numpy.power(2, numpy.arange(0.0, 84.0)/12).astype(numpy.float32)

samples = {}
playingnotes = {}
sustainplayingnotes = []
sustain = False
playingsounds = []
globalvolume = 10 ** (VOLUME/20)  # -12dB default global volume
globaltranspose = 12
numpresets = 1 # By default there should be at least one...

#########################################
# AUDIO AND MIDI CALLBACKS
#
#########################################

def AudioCallback(in_data, frame_count, time_info, status):
    global playingsounds
    rmlist = []
    playingsounds = playingsounds[-MAX_POLYPHONY:]
    b = samplerbox_audio.mixaudiobuffers(playingsounds, rmlist, frame_count, FADEOUT, FADEOUTLENGTH, SPEED)
    for e in rmlist:
        try:
            playingsounds.remove(e)
        except:
            pass
    b *= globalvolume
    odata = (b.astype(numpy.int16)).tostring()
    return (odata, pyaudio.paContinue)


def MidiCallback(message, time_stamp):
    global playingnotes, sustain, sustainplayingnotes
    global preset
    global globalvolume
    global lastnoteplayed
    messagetype = message[0] >> 4
    messagechannel = (message[0] & 15) + 1
    note = message[1] if len(message) > 1 else None
    midinote = note
    velocity = message[2] if len(message) > 2 else None

    if messagetype == 9 and velocity == 0:
        messagetype = 8

    if messagetype == 9:    # Note on
        midinote += globaltranspose
        lastnoteplayed = datetime.datetime.now()
        if USE_DOTSTAR and (midinote>offset) and (midinote<127-offset):
            strip.setPixelColor(midinote-offset, strokecolor)
            strip.show() # Update strip
        try:
            playingnotes.setdefault(midinote, []).append(samples[midinote, velocity].play(midinote))
        except:
            pass

    elif messagetype == 8:  # Note off
        midinote += globaltranspose
        if USE_DOTSTAR and (midinote>offset) and (midinote<127-offset):
            strip.setPixelColor(midinote-offset, defaultcolor) 
            strip.show() # Update strip             
        if midinote in playingnotes:
            for n in playingnotes[midinote]:
                if sustain:
                    sustainplayingnotes.append(n)
                else:
                    n.fadeout(50)
            playingnotes[midinote] = []

    elif messagetype == 12:  # Program change
        print 'Program change ' + str(note)
        preset = note
        LoadSamples()

    elif (messagetype == 11) and (note == 64) and (velocity < 64):  # sustain pedal off
        for n in sustainplayingnotes:
            n.fadeout(50)
        sustainplayingnotes = []
        sustain = False

    elif (messagetype == 11) and (note == 64) and (velocity >= 64):  # sustain pedal on
        sustain = True

    elif (messagetype == 11) and (note == 7) and USE_VOLUMESLIDER:  # volume slider
        globalvolume = float((1.0-velocity/127.0)*+3.0) # ranges from 0 to 3.0 now

    elif (messagetype == 11) and (note == 99): # preset up button TBC from octave+
        print('Debug: button preset up pressed')
        preset += 1
        if preset > numpresets-1:
            preset = 0
        LoadSamples()

    elif (messagetype == 11) and (note == 100): # preset down button TBC from octave-
        print('Debug: button preset down pressed')
        preset -= 1
        if preset < 0:
            preset = numpresets-1
        LoadSamples()

#########################################
# LOAD SAMPLES
#
#########################################

LoadingThread = None
LoadingInterrupt = False


def LoadSamples():
    global LoadingThread
    global LoadingInterrupt

    if LoadingThread:
        LoadingInterrupt = True
        LoadingThread.join()
        LoadingThread = None

    LoadingInterrupt = False
    LoadingThread = threading.Thread(target=ActuallyLoad)
    LoadingThread.daemon = True
    LoadingThread.start()

NOTES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]


def ActuallyLoad():
    global preset
    global samples
    global playingsounds
    global globalvolume, globaltranspose
    global numpresets
    
    playingsounds = []
    samples = {}
    globalvolume = 10 ** (VOLUME/20)  # -12dB default global volume
    globaltranspose = 12

    numpresets=0 # Determine number of presets available
    for root, dirs, files in os.walk(SAMPLES_DIR):
        for name in dirs:
            print os.path.join(root, name)
            numpresets += 1
    print('Found '+str(numpresets)+' number of presets')
    
    basename = next((f for f in os.listdir(SAMPLES_DIR) if f.startswith("%d " % preset)), None)      # or next(glob.iglob("blah*"), None)
    if basename:
        dirname = os.path.join(SAMPLES_DIR, basename)
    if not basename:
        print 'Preset empty: %s' % preset
        display("E%03d" % preset)
        return
    print 'Preset loading: %s (%s)' % (preset, basename)
    display("L%03d" % preset)

    definitionfname = os.path.join(dirname, "definition.txt")
    if os.path.isfile(definitionfname):
        with open(definitionfname, 'r') as definitionfile:
            for i, pattern in enumerate(definitionfile):
                try:
                    if r'%%volume' in pattern:        # %%paramaters are global parameters
                        globalvolume *= 10 ** (float(pattern.split('=')[1].strip()) / 20)
                        continue
                    if r'%%transpose' in pattern:
                        globaltranspose = int(pattern.split('=')[1].strip())
                        continue
                    defaultparams = {'midinote': '0', 'velocity': '127', 'notename': ''}
                    if len(pattern.split(',')) > 1:
                        defaultparams.update(dict([item.split('=') for item in pattern.split(',', 1)[1].replace(' ', '').replace('%', '').split(',')]))
                    pattern = pattern.split(',')[0]
                    pattern = re.escape(pattern.strip())
                    pattern = pattern.replace(r"\%midinote", r"(?P<midinote>\d+)").replace(r"\%velocity", r"(?P<velocity>\d+)")\
                                     .replace(r"\%notename", r"(?P<notename>[A-Ga-g]#?[0-9])").replace(r"\*", r".*?").strip()    # .*? => non greedy
                    for fname in os.listdir(dirname):
                        if LoadingInterrupt:
                            return
                        m = re.match(pattern, fname)
                        if m:
                            info = m.groupdict()
                            midinote = int(info.get('midinote', defaultparams['midinote']))
                            velocity = int(info.get('velocity', defaultparams['velocity']))
                            notename = info.get('notename', defaultparams['notename'])
                            if notename:
                                midinote = NOTES.index(notename[:-1].lower()) + (int(notename[-1])+2) * 12
                            samples[midinote, velocity] = Sound(os.path.join(dirname, fname), midinote, velocity)
                except:
                    print "Error in definition file, skipping line %s." % (i+1)

    else:
        for midinote in range(0, 127):
            if LoadingInterrupt:
                return
            file = os.path.join(dirname, "%d.wav" % midinote)
            if os.path.isfile(file):
                samples[midinote, 127] = Sound(file, midinote, 127)

    initial_keys = set(samples.keys())
    for midinote in xrange(128):
        lastvelocity = None
        for velocity in xrange(128):
            if (midinote, velocity) not in initial_keys:
                samples[midinote, velocity] = lastvelocity
            else:
                if not lastvelocity:
                    for v in xrange(velocity):
                        samples[midinote, v] = samples[midinote, velocity]
                lastvelocity = samples[midinote, velocity]
        if not lastvelocity:
            for velocity in xrange(128):
                try:
                    samples[midinote, velocity] = samples[midinote-1, velocity]
                except:
                    pass
    if len(initial_keys) > 0:
        print 'Preset loaded: ' + str(preset)
        display("%04d" % preset)
    else:
        print 'Preset empty: ' + str(preset)
        display("E%03d" % preset)


#########################################
# OPEN AUDIO DEVICE
#
#########################################

p = pyaudio.PyAudio()
try:
    stream = p.open(format=pyaudio.paInt16, channels=2, rate=44100, frames_per_buffer=64, output=True,
                    input=False, output_device_index=AUDIO_DEVICE_ID, stream_callback=AudioCallback)
    print 'Opened audio: ' + p.get_device_info_by_index(AUDIO_DEVICE_ID)['name']
except:
    print "Invalid Audio Device ID: " + str(AUDIO_DEVICE_ID)
    print "Here is a list of audio devices:"
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        # Remove input device (not really useful on a Raspberry Pi)
        if dev['maxOutputChannels'] > 0:
            print str(i) + " -- " + dev['name']
    exit(1)


#########################################
# BUTTONS THREAD (RASPBERRY PI GPIO)
#
#########################################

if USE_BUTTONS:

    lastbuttontime = 0

    def Buttons():
        GPIO.setup(presetuppin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(presetdownpin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        global preset, lastbuttontime
        while True:
            now = time.time()
            if not GPIO.input(presetuppin) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                preset -= 1
                if preset < 0:
                    preset = numpresets-1
                LoadSamples()

            elif not GPIO.input(presetdownpin) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                preset += 1
                if preset > numpresets-1:
                    preset = numpresets
                LoadSamples()

            time.sleep(0.020)

    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()


#########################################
# 7-SEGMENT DISPLAY
#
#########################################

if USE_I2C_7SEGMENTDISPLAY:
    import smbus

    bus = smbus.SMBus(1)     # using I2C

    def display(s):
        for k in '\x76\x79\x00' + s:     # position cursor at 0
            try:
                bus.write_byte(0x71, ord(k))
            except:
                try:
                    bus.write_byte(0x71, ord(k))
                except:
                    pass
            time.sleep(0.002)

    display('----')
    time.sleep(0.5)

else:

    def display(s):
        pass


#########################################
# MIDI IN via SERIAL PORT
#
#########################################

if USE_SERIALPORT_MIDI:
 
    import serial
    ser = serial.Serial('/dev/ttyAMA0', baudrate=38400)       # see hack in /boot/cmline.txt : 38400 is 31250 baud for MIDI!

    def MidiSerialCallback():
        message = [0, 0, 0]
        while True:
            i = 0
            while i < 3:
                data = ord(ser.read(1))  # read a byte
                if data >> 7 != 0:
                    i = 0      # status byte!   this is the beginning of a midi message: http://www.midi.org/techspecs/midimessages.php
                message[i] = data
                i += 1
                if i == 2 and message[0] >> 4 == 12:  # program change: don't wait for a third byte: it has only 2 bytes
                    message[2] = 0
                    i = 3
            MidiCallback(message, None)

    MidiThread = threading.Thread(target=MidiSerialCallback)
    MidiThread.daemon = True
    MidiThread.start()

#########################################
# DOTSTAR general star pattern
#
#########################################

if USE_DOTSTAR:
    
    def DotStarGen():
        while True:
            
            timesincestroke = datetime.datetime.now() - lastnoteplayed
            
            if timesincestroke.total_seconds() < 15: # after x seconds switch off candles
                for i in range(0,numpixels):
                    if strip.getPixelColor(i) != strokecolor:
                         strip.setPixelColor(i, defaultcolor) # set to default color
            else:
                for i in range(0,numpixels):
                    strip.setPixelColor(i, 0) # Set black=off
                    
            strip.show() # Refresh strip
            time.sleep(1)

    MidiThread = threading.Thread(target=DotStarGen)
    MidiThread.daemon = True
    MidiThread.start()

if USE_CANDLE:

    GPIO.setup(candleleftpin,GPIO.OUT)
    GPIO.setup(candlerightpin,GPIO.OUT)
    GPIO.setup(starpin,GPIO.OUT)

    GPIO.output(starpin,GPIO.LOW)    
    GPIO.output(candleleftpin,GPIO.LOW)
    GPIO.output(candlerightpin,GPIO.HIGH)

    def CandleCtrl():
        while True:
            
            timesincestroke = datetime.datetime.now() - lastnoteplayed
 
            if timesincestroke.total_seconds() < 5: # after x seconds switch off candles
                GPIO.output(candleleftpin,GPIO.HIGH) # Put the left LED on
                GPIO.output(candlerightpin,GPIO.HIGH) # Put the right LED on
                GPIO.output(starpin,GPIO.HIGH)
                print('Set pins to high')
            else:
                GPIO.output(candleleftpin,GPIO.LOW) # Put the left LED off
                GPIO.output(candlerightpin,GPIO.LOW) # Put the right LED off
                GPIO.output(starpin,GPIO.LOW)
            
            time.sleep(1)

    MidiThread = threading.Thread(target=CandleCtrl)
    MidiThread.daemon = True
    MidiThread.start()



#########################################
# LOAD FIRST SOUNDBANK
#
#########################################

preset = 0
LoadSamples()


#########################################
# MIDI DEVICES DETECTION
# MAIN LOOP
#########################################

midi_in = [rtmidi.MidiIn()]
previous = []
while True:
    for port in midi_in[0].ports:
        if port not in previous and 'Midi Through' not in port:
            midi_in.append(rtmidi.MidiIn())
            midi_in[-1].callback = MidiCallback
            midi_in[-1].open_port(port)
            print 'Opened MIDI: ' + port
    previous = midi_in[0].ports
    time.sleep(2)
