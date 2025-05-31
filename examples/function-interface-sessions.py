#!/usr/bin/env python

from nicegui import ui, Client
from sioba import Interface, FunctionInterface
from sioba_nicegui.xterm import XTermInterface

import time
import datetime
import weakref

@ui.page('/gc')
async def gc_page(client: Client):
    import gc
    print(gc.collect())
    return "foo"

@ui.page('/')
async def index(client: Client):

    def terminal_code(interface: Interface):
        interface.print("Hello, World!")
        interface.print("This is a simple script.")

        name = interface.input("What's your name? ")
        interface.print(f"Hello, {name}!")

        hidden = interface.getpass("Enter your hidden word: ")
        interface.print(f"Your hidden word is: {hidden}")

        while True:
            time.sleep(2)
            interface.print(f"It is: {datetime.datetime.now()}")

    xterm = XTermInterface(
                FunctionInterface(terminal_code)
            ).classes("w-full")

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

