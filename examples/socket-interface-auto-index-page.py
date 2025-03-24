#!/usr/bin/env python

from nicegui import ui
from niceterminal_socket.interface import SocketInterface
from niceterminal.xterm import XTerm

#socket_interface = SocketInterface("towel.blinkenlights.nl", 23)
socket_interface = SocketInterface("iwiki.izaber.com", 80)
xterm = XTerm(socket_interface).classes("w-full")

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