from nicegui import ui, app, Client
from niceterminal import xterm
import asyncio

#from niceterminal.utils.interface import PosixInterface, PersistentInterface
from niceterminal.interface.subprocess import ShellInterface

import uuid

import logging
logging.basicConfig(level=logging.DEBUG)

from loguru import logger

import sys

logger.warning("Launching GUI")

def generate_id():
    return str(uuid.uuid4())[:8]

class TerminalInterfaces:
    """ This provides multiple terminals and services for a single user
    """
    def __init__(self, controller: "TerminalController" = None):
        self.controller = controller

        # We do take advantage of the fact that dicts are ordered
        self.interfaces = {}

    def new_interface(self, interface: xterm.Interface = None):
        """
        """
        if not interface:
            logger.warning("Starting ShellInterface!")
            interface = ShellInterface()
            asyncio.create_task(interface.launch_interface())

        self.interfaces[interface.id] = interface

        return interface

    def __len__(self) -> int:
        return len(self.interfaces)

    def items(self):
        return self.interfaces.items()

    def __getitem__(self, k):
        if isinstance(k, int):
            return list(self.interfaces.values())[k]
        return self.interfaces[k]


class TerminalUI:

    # Reference to the nicegui tabs element we organize everything into
    tabs = None

    # Contains the references to each content displayed
    tab_references = None

    def __init__(self, interfaces, controller: "TerminalController" = None, parent=None):
        self.controller = controller
        self.interfaces = interfaces
        self.parent = parent

        self.tab_references = {}

        self.id = generate_id()

    def new_terminal(self, interface: xterm.Interface = None):
        """ When the controller creates a new terminal, we need to add a new tab
            in each client UI
        """
        with self.add_new_tab("xterm").classes("p-0") as content:
            xterm.XTerm(interface=interface).classes("w-full h-full m-0 p-0")
        self.tabs.set_value(content)

    def add_new_tab(self, tab_id: str, tab_title: str = ""):
        tab_id = generate_id()

        # Insert new tab before the "+" tab
        with self.tabs:
            tab = ui.tab(f'Tab {len(self.controller.interfaces)}')
            #tab = ui.tab("x")
            #tab.move(target_slot="primary")
            #tab.move(target_container=self.add_tab, position="before")
            #tab.move(self.tabs, target_slot='primary', target_index=1)
            tab.move(self.tabs, target_index=-1)

            self.tab_references[tab_id] = tab

            # Add close button to tab
            with tab:
                with ui.row():
                    ui.label(tab_title)
                    ui.badge('🗙', color='transparent')\
                        .props('floating')\
                        .on('click',
                            lambda t=tab_id: self.close_tab(t))

        # Add corresponding tab panel
        with self.tab_panels:
            #self.tab_contents[tab_id] = ui.tab_panel(tab_title)
            #with self.tab_contents[tab_id]:
            #with ui.tab_panel(tab):
            #    ui.label(f'TAB CONTENT! {len(self.controller.interfaces)}')
            #    #xterm.XTerm(interface=self.sessions[tab_index]).classes("w-full h-full m-0 p-0")
            return ui.tab_panel(tab)

        return self.tab_panels

    def request_new_terminal(self):
        """ This is called when the user requests a new tab in the UI

            This allows us to bring the request to start a new terminal
            back to the server. Then we can send the request into the
            controller where it is then able to create a new terminal,
            then dispatch the new tab to all the connected clients
        """
        self.controller.new_terminal()

    def render(self):
        if not self.parent:
            self.parent = ui.element("div").classes("w-full h-screen m-0 p-0")

        # This establishes the basic terminal layout
        with self.parent:
            with ui.column().classes("w-full h-full m-0 p-0"):
            #with ui.column():

                # Create the tabs
                self.tabs = ui.tabs()
                with self.tabs:
                    self.add_tab = ui.tab("🏠")

                # Basic Panel
                self.tab_panels = ui.tab_panels(self.tabs, value=self.add_tab)
                self.tab_panels.classes("w-full h-full m-0 p-0")
                with self.tab_panels:
                     with ui.tab_panel(self.add_tab).classes("p-5"):
                        ui.label("Welcome to the terminal")
                        ui.button("New Terminal").on("click", self.request_new_terminal)

        # TODO: display all existing xterminals in the UI

        return self

class TerminalController:
    def __init__(self):
        self.interfaces = TerminalInterfaces()
        self.id = generate_id()

        self.terminal_uis = {}

    def new_ui(self):
        terminal_ui = TerminalUI(self.interfaces, self)
        self.terminal_uis[terminal_ui.id] = terminal_ui
        return terminal_ui

    def new_interface(self, interface: xterm.Interface = None):
        return self.interfaces.new_interface(interface)

    def new_terminal(self, interface: xterm.Interface = None):
        """ Create a new terminal.

            This is done in 2 steps.
            1. Create a new terminal in the controller
            2. Dispatch the new terminal to all connected clients
        """
        new_interface = self.new_interface(interface)
        for terminal_ui in self.terminal_uis.values():
            terminal_ui.new_terminal(new_interface)

INTERFACES = {}
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

ui.run(storage_secret="kjas;lkdjf;lasjdf;lijasd;fjaskdfa")

