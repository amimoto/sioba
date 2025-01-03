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
            logger.info("Starting ShellInterface!")
            interface = ShellInterface()
            asyncio.create_task(interface.launch_interface())

        self.interfaces[interface.id] = interface

        return interface

    def __len__(self) -> int:
        return len(self.interfaces)

    def items(self):
        return self.interfaces.items()

    def __iter__(self):
        return iter(self.interfaces.values())

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
        with self.add_new_tab(interface.id, interface.title).classes("p-0") as content:
            xterm.XTerm(interface=interface).classes("w-full h-full m-0 p-0")
        self.tabs.set_value(content)

    def add_new_tab(self, tab_id: str = None, tab_title: str = ""):
        if not tab_id:
            tab_id = generate_id()

        # Insert new tab before the "+" tab
        with self.tabs:
            tab_title = tab_title or f'Tab {len(self.controller.interfaces)}'
            tab = ui.tab(
                        name=tab_id,
                        label="",
                    )
            tab.move(self.tabs, target_index=-1)

            # Store reference to relevant tab details
            tab_data = {
                "tab": tab,
                "label": None,
                "panel": None,
            }
            self.tab_references[tab_id] = tab_data

            # Add close button to tab
            with tab:
                with ui.row():
                    tab_data["label"] = ui.label(tab_title).classes("normal-case font-mono")
                    ui.badge('🗙', color='transparent')\
                        .props('floating')\
                        .on('click',
                            lambda t=tab_id: self.close_tab(t))

        # Add corresponding tab panel
        with self.tab_panels:
            panel = ui.tab_panel(tab)
            tab_data["panel"] = panel
            return panel

        return self.tab_panels

    def request_new_terminal(self):
        """ This is called when the user requests a new tab in the UI

            This allows us to bring the request to start a new terminal
            back to the server. Then we can send the request into the
            controller where it is then able to create a new terminal,
            then dispatch the new tab to all the connected clients
        """
        self.controller.new_terminal()

    def on_set_title_handle(self, interface: xterm.Interface, title: str) -> None:
        if tab_data := self.tab_references.get(interface.id):
            tab_data["label"].set_text(title)

    def render(self):
        if not self.parent:
            self.parent = ui.element("div").classes("w-full h-screen m-0 p-0")

        # This establishes the basic terminal layout
        with self.parent:
            with ui.column().classes("w-full h-full m-0 p-0"):

                # Create the tabs
                self.tabs = ui.tabs()
                with self.tabs:
                    self.add_tab = ui.tab(name="home", label="🏠")

                # Basic Panel
                self.tab_panels = ui.tab_panels(self.tabs, value=self.add_tab)
                self.tab_panels.classes("w-full h-full m-0 p-0")
                with self.tab_panels:
                     with ui.tab_panel(self.add_tab).classes("p-5"):
                        ui.label("Welcome to the terminal")
                        ui.button("New Terminal").on("click", self.request_new_terminal)

        for interface in self.controller.interfaces:
            self.new_terminal(interface)

        return self

class TerminalController:
    def __init__(self) -> None:
        self.interfaces = TerminalInterfaces()
        self.id = generate_id()
        self.terminal_uis = {}

    def new_ui(self) -> TerminalUI:
        terminal_ui = TerminalUI(self.interfaces, self)
        self.terminal_uis[terminal_ui.id] = terminal_ui
        return terminal_ui

    def new_interface(self, interface: xterm.Interface = None) -> xterm.Interface:
        new_interface = self.interfaces.new_interface(interface)
        new_interface.on_set_title(self.on_set_title_handle)
        return new_interface

    def on_set_title_handle(self, interface: xterm.Interface, title: str) -> None:
        for terminal_ui in self.terminal_uis.values():
            terminal_ui.on_set_title_handle(interface, title)

    def new_terminal(self, interface: xterm.Interface = None) -> None:
        """ Create a new terminal.

            This is done in 2 steps.
            1. Create a new terminal in the controller
            2. Dispatch the new terminal to all connected clients
        """
        new_interface = self.new_interface(interface)
        for terminal_ui in self.terminal_uis.values():
            terminal_ui.new_terminal(new_interface)
