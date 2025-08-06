#!/usr/bin/env python

from nicegui import ui, Client
from sioba_nicegui.xterm import XTermInterface
import gc

@ui.page('/')
async def index(client: Client):
    interface, xterm = XTermInterface.from_uri("echo://")
    xterm.classes("w-full")
    interface.on_receive_from_frontend(lambda data: print(f"Received: {data}"))

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