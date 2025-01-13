"""
NiceTerminal Web Interface

Usage:
    niceterminal [options]
    niceterminal -h | --help
    niceterminal --version

Options:
  -h --help                    Show this help.
  --version                    Show version.
  --host=<host>                Host to bind web interface [default: 0.0.0.0].
  --port=<port>                Port for web interface [default: 8080].
  --app=<command>              Default application to start in new terminals [default: bash].
  --password=<pass>            Set authentication password
  --no-auth                    Disable authentication requirement. Incompatible with --password.
  --log-level=<level>          Set log level [default: INFO].
  --isolation=<level>          At what level are terminals shared: [default: global]
                                    - global: everyone
                                    - user: brower
                                    - tab: only for tab

Examples:
  niceterminal --host 0.0.0.0 --port 9000
  niceterminal --app 'python3' --no-auth
  niceterminal --password secret123
"""
VERSION = "0.1.0"

import os
import logging

import docopt
import hashlib

from fastapi.responses import RedirectResponse

from loguru import logger

from nicegui import ui, app, Client

from niceterminal.app import TerminalController

CONTROLLERS = {}
OPTS = {}

@ui.page('/authenticate')
@logger.catch
async def authenticate(client : Client):

    if app.storage.user.get("authenticated"):
        return RedirectResponse("/")

    with ui.card().classes('absolute-center w-full max-w-screen-sm'):

        with ui.row().classes("items-center"):
            ui.icon("security").classes('text-4xl')
            ui.label('Terminal Access Login').classes('text-4xl')

        error_container = ui.element("div").classes("mb-0")
        error_container.visible = False

        password_input = ui.input(
                                label="Password",
                                password=True,
                                password_toggle_button=True
                            )\
                            .classes('w-full')


        def display_error(message:str):
            with error_container as err:
                err.clear()
                err.classes("w-full text-red-500 font-bold mb-4")
                err.visible = True
                with ui.row():
                    ui.icon("error").classes('text-3xl')
                    ui.label(message).classes('text-3xl text-red-500 font-bold')

        def authenticate_user(a):
            password = password_input.value
            if not password:
                return display_error("Please enter a password.")

            if OPTS.get("--password") and password != OPTS.get("--password"):
                return display_error("Incorrect password.")

            app.storage.user["authenticated"] = password
            ui.navigate.to('/')

        password_input.on('keydown.enter', lambda a: authenticate_user(a))

        ui.button("Authenticate").on("click", authenticate_user)

@ui.page('/')
@logger.catch
async def index(client : Client):

    # Check if we're logged in
    if not OPTS.get("--no-auth"):
        if not app.storage.user.get("authenticated"):
            return RedirectResponse("/authenticate")

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

    logging.info(f"Isolation level is {OPTS.get('--isolation')}")
    isolation = OPTS.get("--isolation")

    # Get a terminal controller for the current level of isolation
    if isolation == "tab":
        controller_id = app.storage.tab.get("terminal_controller_id")
    elif isolation == "user":
        controller_id = app.storage.user.get("terminal_controller_id")
    elif isolation == "global":
        controller_id = 'global'
    else:
        raise ValueError("Invalid isolation level")

    controller = controller_id and CONTROLLERS.get(controller_id)
    if not controller:
        controller = TerminalController()
        CONTROLLERS[controller.id] = controller
        controller.new_interface()

        if isolation == "tab":
            app.storage.tab["terminal_controller_id"] = controller.id
        elif isolation == "user":
            app.storage.user["terminal_controller_id"] = controller.id
        elif isolation == "global":
            CONTROLLERS["global"] = controller
        else:
            raise ValueError("Invalid isolation level")

    # We need to create the new UI for the client
    terminal_app = controller.new_ui(client)
    terminal_app.render()

def main():
    reload = os.environ.get("RELOAD", False)

    # Has the user disabled the password?
    if OPTS.get("--no-auth") and OPTS.get("--password"):
        raise ValueError("Cannot use --no-auth and --password together.")

    if log_level := OPTS.get("--log-level"):
        logging.basicConfig(level=log_level)

    storage_secret = None
    # If the user has disabled authentication, we need to generate a secret
    # We'll use the host, user, and port to generate a secret that is unique to the user
    # but also consistent across restarts
    if OPTS.get("--no-auth"):
        storage_secret = "{host}-{user}-{port}".format(**OPTS)

    elif password := OPTS.get("--password"):
        # If the user has provided a password, we'll use that as the secret
        storage_secret = password

    else:
        # If the user has not provided a password, we'll generate a random password
        password = hashlib.pbkdf2_hmac(
                            "sha256",
                            os.urandom(32),
                            b"niceterminal",
                            100_000
                        ).hex()
        OPTS["--password"] = password
        logger.info(f"Generated password: {password}")
        storage_secret = password

    storage_secret = hashlib.pbkdf2_hmac(
                            "sha256",
                            storage_secret.encode("utf-8"),
                            b"niceterminal",
                            100_000
                        )

    ui.run(
        reload=OPTS.get("--reload", reload),
        host=OPTS.get("--host", "localhost"),
        port=int(OPTS.get("--port", 8080)),
        storage_secret=storage_secret,
    )

OPTS = docopt.docopt(__doc__, version=VERSION)
main()