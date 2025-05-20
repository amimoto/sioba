#!/usr/bin/env python

from nicegui import ui
from niceterminal_interface import SocketInterface
from niceterminal.xterm import XTermInterface

socket_interface = SocketInterface(
                        connection={
                            "host": "example.com",
                            "port": 80
                        }
                    )
xterm = XTermInterface(socket_interface).classes("w-full")

# Make sure static files can be found
try:
    ui.run(
        title="NiceTerminal Function Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟",
    )
except KeyboardInterrupt:
    pass