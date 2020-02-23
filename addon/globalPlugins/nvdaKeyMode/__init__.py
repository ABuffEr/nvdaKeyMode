# -*- coding: UTF-8 -*-
from logHandler import log
from  keyboardHandler import KeyboardInputGesture
from .msg import message as NVDALocale
from functools import wraps
from inputCore import manager as inputManager
import addonHandler
import globalPluginHandler
import globalVars
import os
import ui
from threading import Thread
from time import sleep

addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(addonDir, bytes):
	addonDir = addonDir.decode("mbcs")
curAddon = addonHandler.Addon(addonDir)
addonSummary = curAddon.manifest['summary']

addonHandler.initTranslation()

# status of add-on key (pressed/released)
toggling = False
# this determined by NVDA input gesture remap,
# when it calls script_nvdaKeyMode
addonKey = None
# last pressed gesture identifier
lastGesture = None
# to enable logging
DEBUG = False

def debugLog(message):
	if DEBUG:
		log.info(message)

# Below toggle code came from InstantTranslate add-on,
# that is, from Tyler Spivey's code, with enhancements by Joseph Lee.
def finally_(func, final):
	"""Calls final after func, even if it fails."""
	def wrap(f):
		@wraps(f)
		def new(*args, **kwargs):
			try:
				func(*args, **kwargs)
			finally:
				final()
		return new
	return wrap(final)

# tuple of waiting times after each keypress
timerTimes = (0.2, 0.25, 0.1)
# last position in time tuple
timerTimePos = 0
# current timer
gestureTimer = None

# create a new Thread instance for timer
def restartTimer():
	global timerTimePos, gestureTimer
	# waiting time for next keypress
	timerTime = timerTimes[timerTimePos]
	# increase tuple position
	timerTimePos = (timerTimePos+1)%len(timerTimes)
	# a Thread consuming specified time
	gestureTimer = Thread(target=sleep, args=(timerTime,))
	debugLog("Starting timer of %s"%timerTime)
	# ...now!
	gestureTimer.start()

# a backup of original reportToggleKey func
old_reportToggleKey = KeyboardInputGesture._reportToggleKey

# to avoid report of toggle key status
# when mapped to script_nvdaKeyMode
def new_reportToggleKey(*args):
	if (toggling or inputManager.isInputHelpActive) and addonKey.vkCode in addonKey.TOGGLE_KEYS:
		return
	old_reportToggleKey(*args)

KeyboardInputGesture._reportToggleKey = new_reportToggleKey

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = addonSummary

	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		if globalVars.appArgs.secure:
			return
		global toggling
		toggling = False

	def terminate(self):
		global toggling, timerTimePos
		toggling = False
		timerTimePos = 0
		KeyboardInputGesture._reportToggleKey = old_reportToggleKey

# for a better comprehension of add-on mechanism,
# following func are sorted according to the
# order of an usual complete execution of
# a gesture, like addonKey+t.

	# main script, where things begin
	def script_nvdaKeyMode(self, gesture):
		global toggling, addonKey, timerTimePos
		if toggling:
			# when add-on key pressed twice, 
			# getScript is not called, so...
			self.script_prefixGesture(gesture)
			self.finish()
			return
		# set initial conditions
		addonKey = gesture
		timerTimePos = 0
		if not inputManager.isInputHelpActive:
			toggling = True
			ui.message(NVDALocale("{modifier} pressed").format(modifier="NVDA"))
		elif gesture.vkCode in gesture.TOGGLE_KEYS:
			# force help message announcement during input help
			helpMessage = '  '.join([gesture.displayName, self.script_nvdaKeyMode.__doc__])
			ui.message(helpMessage)
	# Translators: Script presentation in NVDA gesture remap dialog
	script_nvdaKeyMode.__doc__ = _("Use this key/key combination as delayed NVDA key")

	def getScript(self, gesture):
		if not toggling:
			# return usual script for gesture
			return globalPluginHandler.GlobalPlugin.getScript(self, gesture)
		else:
			# start or restart timer
			restartTimer()
		# return add-on script followed by finish func
		return finally_(self.script_prefixGesture, self.finish)

	def script_prefixGesture(self, gesture):
		# get clean gesture identifiers
		id = gesture.identifiers[1][3:]
		debugLog("Received %s to prefix"%id)
		if id == addonKey.identifiers[1][3:]:
			# manage double press of add-on key
			if gesture.vkCode not in gesture.TOGGLE_KEYS:
				# add-on key has no on/off state, so release
				ui.message(NVDALocale("{modifier} released").format(modifier="NVDA"))
			else:
				# change on/off state (and release)
				gesture.send()
			return
		global lastGesture
		lastGesture = id

	def finish(self):
		global toggling, lastGesture, gestureTimer
		# keep a local var to gestureTimer
		tempTimer = gestureTimer
		# while ensure all timers started have finished now
		while tempTimer and tempTimer.is_alive():
			debugLog("Waiting timer thread termination...")
			tempTimer.join()
			# update local var to current running timer
			tempTimer = gestureTimer
		toggling = False
		# lastGesture may be None if add-on key was pressed and released
		if lastGesture:
			# build whole gesture
			fixedGesture = '+'.join(["NVDA", lastGesture])
			debugLog("Executing %s"%fixedGesture)
			inputManager.emulateGesture(KeyboardInputGesture.fromName(fixedGesture))
		lastGesture = None
