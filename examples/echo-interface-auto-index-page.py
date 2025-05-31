#!/usr/bin/env python

from nicegui import ui
from niceterminal_interface import EchoInterface
from niceterminal.xterm import XTermInterface
import logging

logging.basicConfig(level=logging.DEBUG)

xterm = XTermInterface(EchoInterface()).classes("w-full")

# Make sure static files can be found
try:
    ui.run(
        title="NiceTerminal Function Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟"
    )
except KeyboardInterrupt:
    pass