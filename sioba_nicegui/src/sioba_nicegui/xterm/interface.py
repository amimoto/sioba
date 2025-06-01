from typing import Optional, Any
from .base import (
    XTerm,
    TerminalState,
    TerminalClosedError,
    ClientDeleted,
)

from datetime import datetime
import base64

from nicegui import core, ui
from nicegui.client import Client
import weakref

from sioba.base import Interface

from loguru import logger

class XTermInterface(XTerm):
    """Controller for managing XTerm instances.

    This class provides methods to create, manage, and interact with XTerm
    instances in a NiceGUI application.
    """

    def __init__(self, interface: Optional[Interface], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._interface = interface

        if interface:
            self.connect_interface(interface)

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

        self._interface = weakref.proxy(interface)
        self._interface.reference_increment()

        # Set up interface event handlers
        async def handle_interface_send(_, data: bytes) -> None:
            """Handle data read from the interface."""
            if self.client.id in Client.instances:
                self.write(data)

        def handle_interface_exit(_) -> None:
            """Handle interface exit."""
            try:
                self.write(b"[Interface Exited]\033[?25l\n\r")
            # We risk triggering this exception as it won't be surprising
            # if someone closes their tab
            except (TerminalClosedError, ClientDeleted):
                pass
            self.state = TerminalState.DISCONNECTED

        interface.on_send_to_control(handle_interface_send)
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

            interface.update_terminal_metadata(
                client_id,
                {
                    "rows": rows,
                    "cols": cols
                }
            )

        async def handle_client_data(e: Any) -> None:
            """Handle client data input."""
            data, _ = e.args
            if not len(data):
                return

            if isinstance(data, str):
                await interface.receive_from_control(base64.b64decode(data))
                self.metadata.last_activity = datetime.now()

        async def handle_client_mount(e: Any) -> None:
            """Invoked when a client mounts the terminal."""
            logger.debug(f"New connection {e}")

        # Register event handlers
        self.on("render", handle_client_render)
        self.on("resize", handle_client_resize)
        self.on("data", handle_client_data)
        self.on("mount", handle_client_mount)

        # Set up client connection handling
        async def handle_client_connect(client: Client) -> None:
            """Handle client connections."""
            logger.info(f"Client connected: {client.id}")
            self.state = TerminalState.CONNECTED
            await self._interface.start()
            self.sync_with_frontend()
            self.sync_config()

        def handle_client_disconnect(e: Any) -> None:
            """Handle client disconnections."""
            logger.info(f"Client disconnected: {e}")
            # Remove disconnected client from metadata
            client_id = f"{self.client.id}-{getattr(e, 'sid', '')}"
            self.metadata.connected_clients.discard(client_id)

        self.config.update(interface.interface_config)

        self.client.on_connect(handle_client_connect)
        self.client.on_disconnect(handle_client_disconnect)

    def _handle_delete(self):
        if self._interface:
            self._interface.reference_decrement()

    def sync_with_frontend(self) -> None:
        """Synchronize the terminal state between backend and frontend.

        This method performs a complete state synchronization by:
        1. Fetching the current terminal buffer content
        2. Base64 encoding the buffer data for safe transmission
        3. Sending the encoded screen content to the frontend via JavaScript
        4. Updating the cursor position if available
        5. Checking if the interface has shut down and updating terminal state

        The synchronization is skipped if:
        - No event loop is available
        - No interface is connected

        Raises:
            Exception: Logs any errors that occur during synchronization
        """
        if core.loop is None or not self._interface:
            logger.warning("No event loop available for terminal sync")
            return

        try:
            # Update screen content
            data = self._interface.get_terminal_buffer()
            if isinstance(data, str):
                data = data.encode()

            # Send screen update to frontend
            serialized_data = base64.b64encode(data).decode()
            with self:
                ui.run_javascript(
                    f"runMethod({self.id}, 'refreshScreen', ['{serialized_data}']);"
                )

            # Update cursor position
            if cursor_position := self._interface.get_terminal_cursor_position():
                self.set_cursor_location(*cursor_position)

            # Check if interface is dead
            if self._interface.is_shutdown():
                self.write(b"[Interface Exited]\033[?25l\n\r")
                self.state = TerminalState.DISCONNECTED

        except Exception as e:
            logger.error(f"Failed to sync with frontend: {e}")



