#!/usr/bin/env python

from nicegui import ui
from niceterminal.interface import EchoInterface
from niceterminal.xterm import XTerm

xterm = XTerm(EchoInterface()).classes("w-full")

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