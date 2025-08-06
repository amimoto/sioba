#!/usr/bin/env python

from nicegui import ui
from sioba_nicegui.xterm.interface import XTermInterface
from sioba import Interface, register_scheme

# Register a custom interface scheme for ourselves
@register_scheme("custom")
class CustomInterface(Interface):
    async def receive_from_frontend(self, data: bytes):
        await self.send_to_frontend(f"Received {repr(data)} / {int(data[0])} \r\n".encode())

interface, xterm = XTermInterface.from_uri("custom://")
xterm.classes("w-full")

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