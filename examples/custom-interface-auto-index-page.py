#!/usr/bin/env python

from nicegui import ui
from niceterminal.xterm import XTerm
from niceterminal.interface import (
                    Interface,
                    INTERFACE_STATE_STARTED,
                    INTERFACE_STATE_INITIALIZED
)
from loguru import logger

class CustomInterface(Interface):
    async def receive_from_xterm(self, data: bytes):
        await self.send_to_xterm(f"Received {repr(data)}\r\n".encode())

xterm = XTerm(
            interface=CustomInterface()
        ).classes("w-full")

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