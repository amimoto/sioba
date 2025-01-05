from niceterminal import xterm
from niceterminal.utils import generate_id
import asyncio

from .ui import TerminalUI
from .interfaces import TerminalInterfaces

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

    def close_interface(self, interface_id: str) -> None:
        # Find the interface
        if interface := self.interfaces[interface_id]:

            # Close the interface
            asyncio.create_task(interface.shutdown())

            # Close the ui tab
            for terminal_ui in self.terminal_uis.values():
                terminal_ui.close_tab(interface_id)

            # Remove the interface from the controller
            del self.interfaces[interface_id]

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
