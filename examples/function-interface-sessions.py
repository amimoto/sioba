#!/usr/bin/env python

from nicegui import ui, Client
from niceterminal.interface import Interface, FunctionInterface
from niceterminal.xterm import XTerm

import time
import datetime

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

    xterm = XTerm(
                FunctionInterface(terminal_code)
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

