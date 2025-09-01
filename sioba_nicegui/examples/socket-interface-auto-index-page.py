#!/usr/bin/env python

from nicegui import ui
from sioba import SocketInterface, InterfaceContext
from sioba_nicegui.xterm import XTermInterface

socket_interface = SocketInterface(
                        context=InterfaceContext(
                            host="example.com",
                            port=80,
                        ),
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