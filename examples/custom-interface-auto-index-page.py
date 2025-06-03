#!/usr/bin/env python

from nicegui import ui
from sioba_nicegui.xterm.interface import XTermInterface
from sioba import Interface, register_interface

@register_interface("custom")
class CustomInterface(Interface):
    async def receive_from_control(self, data: bytes):
        if data == b"?":
            ui.label("Custom Interface: Hello, world!").classes("text-center")
        await self.send_to_control(f"Received {repr(data)} / {int(data[0])} \r\n".encode())

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