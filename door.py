#!/usr/bin/env python

import csv
import logging
import signal
import sys
import thread
import time

from logging.handlers import RotatingFileHandler

import pigpio
import wiegand

W0_PIN = 24
W1_PIN = 25
LED_PIN = 5
BUZZ_PIN = 6
DOOR_PIN = 27

PIN_TIMEOUT = 5
HOLD_DOOR = 3

LOG_LEVEL = logging.INFO
LOG_FILE = '/var/log/door.log'
LOG_FORMAT = '[%(asctime)s] %(levelname)-5s: %(message)s'
LOG_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

pin = 0

# Handle Ctrl+C
def sigint_handler(signum, frame) :
        logger.info('Ctrl+C...Exiting...')
        w.cancel()
        pi.stop()
        sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# Handle pin code timeout
def pinTimeout(signum, frame) :
	global pin

	logger.debug('Timeout. Clearing pin')
	flashPin(BUZZ_PIN, 1)
        pin = 0

signal.signal(signal.SIGALRM, pinTimeout)

def readDigit(value) :
	global pin

	if value == 10 : #esc
		logger.debug('Esc pressed...Clearing pin')
		pin = 0
	elif value == 11 : #enter
		signal.alarm(0) # clear pin timeout
		tryAuth(pin)
		pin = 0
	else :
		signal.alarm(PIN_TIMEOUT) # reset pin timeout
		pin = appendDigit(pin, value)

def appendDigit(current, digit) :
	new = current
        new *= 10
        new += digit
	return new

def checkKey(key) :
	with open('/opt/door/keys.csv') as keyfile :
		records = csv.DictReader(keyfile)
		validKeys = [row for row in records]

	return filter(lambda auth: auth['key'] == str(key), validKeys)

def tryAuth(key) :
	auth = checkKey(key)
	if len(auth) > 0 :
		logger.info('Access granted for {} ({}-{})'.format(auth[0]['name'], auth[0]['type'], auth[0]['key']))
		openDoor(HOLD_DOOR)
	else :
		logger.info('Access denied for {}'.format(key))
		flashPin(BUZZ_PIN, 1)

def openDoor(hold) :
	global pi

	logger.debug('Opening door for {}s'.format(hold))
	pi.write(DOOR_PIN, 0)
	pi.write(LED_PIN, 0)
	time.sleep(hold)
	logger.debug('Locking door')
	pi.write(DOOR_PIN, 1)
	pi.write(LED_PIN, 1)
	flashPin(BUZZ_PIN, .1, 2, .1)

def flashPin(pin, length, times=1, delay=0, initial=1) :
	global pi

	logger.debug('Flashing pin {}: ({} {}s {} {}s) x {}'.format(pin, ("ON", "OFF")[initial], length, ("ON", "OFF")[1-initial], delay, times))
	for _ in range(times) :
		pi.write(pin, 1-initial)
		time.sleep(length)
		pi.write(pin, initial)
		time.sleep(delay)

def callback(bits, value):
	logger.debug('read {} bits : {}'.format(bits, value))
	if bits == 4:
		readDigit(value) # pinpad
	else:
		tryAuth(value) # fob

# Setup logging
logger = logging.getLogger("Door Log")
logger.setLevel(LOG_LEVEL)
handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter(LOG_FORMAT, LOG_TIME_FORMAT)
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.debug('Setting up wiegand decoder callbacks')
pi = pigpio.pi()
w = wiegand.decoder(pi, 24, 25, callback)

logger.debug('Setting GPIO pin modes')
pi.set_mode(BUZZ_PIN, pigpio.OUTPUT)
pi.set_mode(LED_PIN, pigpio.OUTPUT)
pi.set_mode(DOOR_PIN, pigpio.OUTPUT)

logger.debug('Setting initial GPIO pin states')
pi.write(BUZZ_PIN, 1)
pi.write(LED_PIN, 1)
pi.write(DOOR_PIN, 1)

thread.start_new_thread(flashPin, (BUZZ_PIN, .1, 4, .1))
thread.start_new_thread(flashPin, (LED_PIN, .1, 4, .1))

logger.info('Startup complete')

while True :
	time.sleep(1)
