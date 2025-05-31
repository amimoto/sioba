#!/usr/bin/env python

from nicegui import ui, Client
from sioba import EchoInterface
from sioba_nicegui.xterm import XTermInterface
import gc

class TestClass(ui.label):
    def __del__(self):
        print(f"!!!!! deleted {self}")

@ui.page('/')
async def index(client: Client):
    ui.label("Echo Test in ui.page")
    xterm = XTermInterface(EchoInterface()).classes("w-full")
    TestClass("does this get baleeted?")

@ui.page('/gc')
async def gc_page(client: Client):
    print(gc.collect())
    return "foo"

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