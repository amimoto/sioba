"""
NiceGUI XTerm Component
======================

This module provides an XTerm.js integration for NiceGUI, allowing for terminal
emulation in web applications. It supports both standalone terminals and shell
interfaces.

Example:
    Basic usage with shell interface:
        >>> from nicegui import ui
        >>> from niceterminal.xterm import ShellXTerm
        >>>
        >>> term = ShellXTerm()
        >>> term.classes("w-full h-full")
        >>> ui.run()

    Advanced usage with custom interface:
        >>> term = XTerm(
        ...     config=TerminalConfig(rows=40, cols=100),
        ...     interface=CustomInterface(),
        ...     on_close=lambda t: print("Terminal closed")
        ... )
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple, Set

from loguru import logger
from nicegui import background_tasks, ui, core, app
from nicegui.client import Client
from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.awaitable_response import AwaitableResponse

from niceterminal.interface.base import Interface
# from niceterminal.interface.subprocess import ShellInterface, INVOKE_COMMAND
from niceterminal.errors import TerminalClosedError

@dataclass
class TerminalConfig:
    """Configuration settings for XTerm terminal.

    Attributes:
        rows: Number of rows in the terminal
        cols: Number of columns in the terminal
        term_type: Terminal type (e.g., 'xterm-256color')
        scrollback: Number of lines to keep in scrollback buffer
        encoding: Character encoding for terminal I/O
    """
    rows: int = 24
    cols: int = 80
    term_type: str = 'xterm-256color'
    scrollback: int = 1000
    encoding: str = 'utf-8'

class TerminalState(Enum):
    """Possible states of the terminal."""
    INITIALIZING = 'initializing'
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    CLOSED = 'closed'

@dataclass
class TerminalMetadata:
    """Metadata for terminal sessions.

    Attributes:
        created_at: When the terminal was created
        connected_clients: Set of client IDs connected to this terminal
        last_activity: Timestamp of last activity
    """
    created_at: datetime = field(default_factory=datetime.now)
    connected_clients: Set[str] = field(default_factory=set)
    last_activity: datetime = field(default_factory=datetime.now)

class XTerm(
            ValueElement,
            DisableableElement,
            component = 'xterm.js',
            default_classes = 'niceterminal-xtermjs',
        ):
    """XTerm.js integration for NiceGUI.

    This class provides a terminal emulator component that can be used in NiceGUI
    applications. It supports both direct usage and integration with various
    terminal interfaces.

    Attributes:
        component: Name of the JavaScript component
        default_classes: Default CSS classes for the terminal
        config: Terminal configuration settings
        state: Current state of the terminal
        metadata: Terminal session metadata
    """


    def __init__(
        self,
        config: Optional[TerminalConfig] = None,
        interface: Optional[Interface] = None,
        value: str = '',
        on_change: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs
    ) -> None:
        """Initialize the XTerm component.

        Args:
            config: Terminal configuration settings
            interface: Terminal interface implementation
            value: Initial terminal content
            on_change: Callback for content changes
            on_close: Callback for terminal closure
            **kwargs: Additional arguments passed to ValueElement
        """
        self.config = config or TerminalConfig()
        self.state = TerminalState.INITIALIZING
        self.metadata = TerminalMetadata()
        self._interface: Optional[Interface] = None
        self.on_close_callback = on_close

        super().__init__(
            value=value,
            on_value_change=on_change,
           **kwargs
        )

        self.props.options = {
                'rows': self.config.rows,
                'cols': self.config.cols,
                'termType': self.config.term_type,
                'scrollback': self.config.scrollback,
            }
 
        # Add required JavaScript resources
        self.add_resource(Path(__file__).parent / 'lib' / 'xterm.js')

        # Set up auto-close for non-shared clients
        if not self.client.shared:
            background_tasks.create(
                self._auto_close(),
                name='auto-close terminal'
            )

        if interface:
            self.connect_interface(interface)

    def focus(self) -> AwaitableResponse:
        """Focus the terminal."""
        return self.run_method("focus")

    def write(self, data: bytes) -> None:
        """Write data to the terminal.

        Args:
            data: Raw bytes to write to the terminal

        Raises:
            TypeError: If data is not bytes
            RuntimeError: If terminal is closed
        """
        if self.state == TerminalState.CLOSED:
            raise TerminalClosedError("Cannot write to closed terminal")

        if not isinstance(data, bytes):
            raise TypeError(f"data must be bytes, got {type(data)}")

        if core.loop is None:
            # logger.warning("No event loop available for terminal write")
            return

        try:
            serialized_data = base64.b64encode(data).decode()
            self.run_method("write", serialized_data)
            self.metadata.last_activity = datetime.now()
        except Exception as e:
            logger.error(f"Failed to write to terminal: {e}")
            raise

    def set_cursor_location(self, row:int, col:int) -> AwaitableResponse:
        self.run_method("setCursorLocation", row, col)

    def connect_interface(self, interface: Interface) -> None:
        """Connect a terminal interface to this XTerm instance.

        This method sets up bidirectional communication between the XTerm
        and the provided interface implementation.

        Args:
            interface: The interface to connect

        Raises:
            RuntimeError: If terminal is already closed
        """
        if self.state == TerminalState.CLOSED:
            raise TerminalClosedError("Cannot connect interface to closed terminal")

        self._interface = interface

        # Set up interface event handlers
        def handle_interface_read(_, data: bytes) -> None:
            """Handle data read from the interface."""
            if self.client.id in Client.instances:
                self.write(data)

        def handle_interface_exit(_) -> None:
            """Handle interface exit."""
            try:
                self.write(b"[Interface Exited]\033[?25l\n\r")
            # We risk triggering this exception as it won't be surprising
            # if someone closes their tab
            except TerminalClosedError:
                pass
            self.state = TerminalState.DISCONNECTED

        interface.on_read(handle_interface_read)
        interface.on_shutdown(handle_interface_exit)

        # Set up client event handlers
        async def handle_client_render(e: Any) -> None:
            """Handle client render events."""
            data, sio_sid = e.args
            client_id = f"{self.client.id}-{sio_sid}"
            self.metadata.connected_clients.add(client_id)

        async def handle_client_resize(e: Any) -> None:
            """Handle terminal resize events."""
            data, sio_sid = e.args
            client_id = f"{self.client.id}-{sio_sid}"

            rows = data.get("rows")
            cols = data.get("cols")
            if not (rows and cols):
                return

            interface.term_client_metadata_update(
                client_id,
                {
                    "rows": rows,
                    "cols": cols
                }
            )

        async def handle_client_data(e: Any) -> None:
            """Handle client data input."""
            data, _ = e.args
            if isinstance(data, str):
                await interface.write(base64.b64decode(data))
                self.metadata.last_activity = datetime.now()

        # Register event handlers
        self.on("render", handle_client_render)
        self.on("resize", handle_client_resize)
        self.on("data", handle_client_data)

        # Set up client connection handling
        def handle_client_connect(client: Client) -> None:
            """Handle client connections."""
            logger.info(f"Client connected: {client.id}")
            self.state = TerminalState.CONNECTED
            self.sync_with_frontend()

        def handle_client_disconnect(e: Any) -> None:
            """Handle client disconnections."""
            logger.info(f"Client disconnected: {e}")
            # Remove disconnected client from metadata
            client_id = f"{self.client.id}-{getattr(e, 'sid', '')}"
            self.metadata.connected_clients.discard(client_id)

        self.client.on_connect(handle_client_connect)
        self.client.on_disconnect(handle_client_disconnect)

        # Launch interface if not shared
        if not self.client.shared:
            background_tasks.create(
                interface.launch_interface(),
                name='Terminal interface task'
            )

    async def _auto_close(self) -> None:
        """Auto-close handler for terminal cleanup."""
        while self.client.id in Client.instances:
            await asyncio.sleep(1.0)

        self.state = TerminalState.CLOSED
        if self.on_close_callback:
            await self.on_close_callback(self)

    def sync_with_frontend(self) -> None:
        """Synchronize terminal state with frontend."""
        if core.loop is None or not self._interface:
            return

        try:
            # Update screen content
            data = self._interface.get_screen_display()
            if isinstance(data, str):
                data = data.encode()

            # Send screen update to frontend
            serialized_data = base64.b64encode(data).decode()
            with self:
                ui.run_javascript(
                    f"runMethod({self.id}, 'refreshScreen', ['{serialized_data}']);"
                )

            # Update cursor position
            cursor_position = self._interface.get_cursor_position()
            self.set_cursor_location(*cursor_position)

            # Check if interface is dead
            if not self._interface.running():
                self.write(b"[Interface Exited]\033[?25l\n\r")
                self.state = TerminalState.DISCONNECTED
        except Exception as e:
            logger.error(f"Failed to sync with frontend: {e}")
