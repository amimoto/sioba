import os
import logging
logging.basicConfig(level=logging.DEBUG)

from loguru import logger

from nicegui import ui, app, Client

from niceterminal.app import TerminalController

CONTROLLERS = {}

@ui.page('/')
@logger.catch
async def index(client : Client):
    logger.warning(f"Entered {client}")

    ui.page_title("Terminal")

    ui.add_head_html('''
    <style>
        .nicegui-content {
            padding: 0;
        }
    </style>
    ''')

    dark = ui.dark_mode()
    dark.enable()

    # Get a terminal controller for the current user
    controller_id = app.storage.user.get("terminal_controller_id")
    controller = controller_id and CONTROLLERS.get(controller_id)
    if not controller:
        controller = TerminalController()
        app.storage.user["terminal_controller_id"] = controller.id
        CONTROLLERS[controller.id] = controller
        controller.new_interface()

    # We need to create the new UI for the client
    terminal_app = controller.new_ui()
    terminal_app.render()

def main():
    reload = os.environ.get("RELOAD", False)
    ui.run(
        reload=reload,
        storage_secret="kjas;lkdjf;lasjdf;lijasd;fjaskdfa"
    )

main()