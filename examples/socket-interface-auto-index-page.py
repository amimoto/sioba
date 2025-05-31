#!/usr/bin/env python

from nicegui import ui
from sioba_interface import SocketInterface
from sioba.xterm import XTermInterface

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
        title="sioba Function Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟",
    )
except KeyboardInterrupt:
    pass