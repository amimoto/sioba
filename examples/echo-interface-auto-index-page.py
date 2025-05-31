#!/usr/bin/env python

from nicegui import ui
from sioba_interface import EchoInterface
from sioba.xterm import XTermInterface
import logging

logging.basicConfig(level=logging.DEBUG)

xterm = XTermInterface(EchoInterface()).classes("w-full")

# Make sure static files can be found
try:
    ui.run(
        title="sioba Function Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟"
    )
except KeyboardInterrupt:
    pass