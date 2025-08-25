#!/usr/bin/env python

from nicegui import ui, Client
from sioba_nicegui.xterm import XTermInterface

@ui.page('/')
async def index(client: Client):
    xterm = XTermInterface.from_uri("echo://")
    xterm.classes("w-full")
    xterm.interface.on_receive_from_frontend(
        lambda interface, data: print(f"Received: {data} from {interface}")
    )

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