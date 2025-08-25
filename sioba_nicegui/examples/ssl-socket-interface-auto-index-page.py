#!/usr/bin/env python

from nicegui import ui
from sioba import SocketInterface
from sioba_nicegui.xterm import XTermInterface
import ssl

ssl_context = ssl.create_default_context()

socket_interface = SocketInterface(
                        connection={
                            "host": "example.com",
                            "port": 443,
                            "ssl": ssl_context,
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