from nicegui import ui, app
from niceterminal import xterm

#from niceterminal.utils.interface import PosixInterface, PersistentInterface
from niceterminal.interface.subprocess import ShellInterface

import logging
logging.basicConfig(level=logging.DEBUG)

from loguru import logger

import sys

INTERFACES = {}

logger.warning("Launching GUI")

@ui.page('/')
@logger.catch
async def index():
    logger.warning("Entered /")
    ui.page_title("Terminal")

    ui.add_head_html('''
    <style>
        .nicegui-content {
            padding: 0;
        }
    </style>
    ''')

    logger.warning("Setting dark mode")
    dark = ui.dark_mode()
    dark.enable()

    # Let's start an interface if it hasn't yet
    logger.warning("Testing storage")
    interfaces = app.storage.user.setdefault("interfaces",{})
    if (
            ( interface_id := interfaces.get("bash") )
            and ( interface := INTERFACES.get(interface_id) )
        ):
        logger.warning("Pulling from cached!")
    else:
        interface = ShellInterface()
        interface.launch_interface()
        interface_id = id(interface)
        interfaces["bash"] = interface_id
        INTERFACES[interface_id] = interface

    with ui.element("div").classes("w-full h-screen m-0 p-0"):
        with ui.column().classes("w-full h-full m-0 p-0"):
            xterm.XTerm(interface=interface).classes("w-full h-full m-0 p-0")

            with ui.row().classes("w-full m-0 p-0"):
                ui.button("Clear").on_click(lambda: interface.write("cls\n"))
                ui.button("Close").on_click(
                    lambda: sys.exit()
                )


ui.run(storage_secret="kjas;lkdjf;lasjdf;lijasd;fjaskdfa")

