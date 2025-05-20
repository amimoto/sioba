#!/usr/bin/env python

from nicegui import ui
from niceterminal_subprocess.interface import ShellInterface
from niceterminal.xterm import XTermInterface

xterm = XTermInterface(
            #ShellInterface("cmd.exe")
            ShellInterface("bash")
        ).classes("w-full")

# Make sure static files can be found
try:
    ui.run(
        title="NiceTerminal Shell Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟"
    )
except KeyboardInterrupt:
    pass