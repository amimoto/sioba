#!/usr/bin/env python

from nicegui import ui
from niceterminal.interface import Interface, FunctionInterface
from niceterminal.xterm import XTerm
import asyncio

import time
import datetime

def terminal_code(interface: FunctionInterface):
    interface.print("Hello, World!")
    interface.print("This is a simple script.")

    name = interface.input("What's your name? ")
    interface.print(f"Hello, {name}!")

    hidden = interface.getpass("Enter your hidden word: ")
    interface.print(f"Your hidden word is: {hidden}")

    while True:
        #await asyncio.sleep(2)
        time.sleep(1)
        interface.print(f"It is: {datetime.datetime.now()}")

xterm = XTerm(
            interface=FunctionInterface(terminal_code)
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

