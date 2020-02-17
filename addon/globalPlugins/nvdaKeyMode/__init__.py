# -*- coding: UTF-8 -*-
from logHandler import log
from  keyboardHandler import KeyboardInputGesture
from .msg import message as NVDALocale
from functools import wraps
from inputCore import manager as inputManager
from speech import speakMessage
import addonHandler
import globalPluginHandler
import globalVars
import os
import ui

addonDir = os.path.join(os.path.dirname(__file__), "..", "..")
if isinstance(addonDir, bytes):
	addonDir = addonDir.decode("mbcs")
curAddon = addonHandler.Addon(addonDir)
addonSummary = curAddon.manifest['summary']

addonHandler.initTranslation()

# status of delayed NVDA key (pressed/released)
toggling = False
# this determined by NVDA input gesture remap,
# when it calls script_nvdaKeyMode
addonKey = None

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

old_reportToggleKey = KeyboardInputGesture._reportToggleKey

# to avoid report of toggle key status
# when mapped to script_nvdaKeyMode
def new_reportToggleKey(*args):
	if toggling and addonKey.vkCode in addonKey.TOGGLE_KEYS:
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
		global toggling
		toggling = False
		KeyboardInputGesture._reportToggleKey = old_reportToggleKey

	def getScript(self, gesture):
		if not toggling:
			return globalPluginHandler.GlobalPlugin.getScript(self, gesture)
		return finally_(self.script_prefixGesture, self.finish)

	def finish(self):
		global toggling
		toggling = False

	def script_prefixGesture(self, gesture):
		id = gesture.identifiers[1][3:]
#		log.info("Received %s, %s"%(gesture.mainKeyName, id))
		if id == addonKey.identifiers[1][3:]:
			# we manage double press of delayed key
			if gesture.vkCode not in gesture.TOGGLE_KEYS:
				# delayed key has no on/off state, so release
				speakMessage(NVDALocale("{modifier} released").format(modifier="NVDA"))
			else:
				# change on/off state (and release)
				gesture.send()
			return
		# build non-delayed version of gesture
		fixedGesture = '+'.join(["NVDA", id])
		# and execute it
		inputManager.emulateGesture(KeyboardInputGesture.fromName(fixedGesture))

	def script_nvdaKeyMode(self, gesture):
		global toggling, addonKey
		if toggling:
			# when delayed key pressed twice, 
			# getScript is not called, so...
			self.script_prefixGesture(gesture)
			self.finish()
			return
		addonKey = gesture
		toggling = True
		if not inputManager.isInputHelpActive:
			speakMessage(NVDALocale("{modifier} pressed").format(modifier="NVDA"))
		elif gesture.vkCode in gesture.TOGGLE_KEYS:
			helpMessage = '  '.join([gesture.displayName, self.script_nvdaKeyMode.__doc__])
			ui.message(helpMessage)
			KeyboardInputGesture._reportToggleKey = new_reportToggleKey
	# Translators: Script presentation in NVDA gesture remap dialog
	script_nvdaKeyMode.__doc__ = _("Use this key/key combination as delayed NVDA key")
