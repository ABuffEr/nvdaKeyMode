# -*- coding: UTF-8 -*-
#A simple module to bypass the addon translation system,
#so it can take advantage from the NVDA translations directly.

def message(message):
	return _(message)
