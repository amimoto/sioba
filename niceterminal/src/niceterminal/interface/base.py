import threading
import asyncio
import time
from typing import Callable
from niceterminal.errors import InterfaceNotStarted
import uuid

from loguru import logger

INTERFACE_STATE_INITIALIZED = 0
INTERFACE_STATE_STARTED = 1
INTERFACE_STATE_SHUTDOWN = 2

INTERFACE_THREAD = None
INTERFACE_LOOP = None

class Interface:
    def __init__(self,
                 on_receive: Callable = None,
                 on_send: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 ):

        self.id = str(uuid.uuid4())
        self.title = ""

        self.scrollback_buffer = b""
        self.scrollback_buffer_size = 100000

        self._on_receive_callbacks = set()
        self._on_send_callbacks = set()
        self._on_shutdown_callbacks = set()
        self._on_set_title_callbacks = set()
        self.state = INTERFACE_STATE_INITIALIZED
        if on_receive:
            self.on_receive(on_receive)
        if on_send:
            self.on_send(on_send)
        if on_shutdown:
            self.on_shutdown(on_shutdown)
        if on_set_title:
            self.on_set_title(on_set_title)

        # Holds infomation on each terminial client
        # Things such as rows, cols
        self.term_clients = {}

        # Now do the subclass specific initialization
        self.init()

    # STATE

    def init(self):
        """ Subclassable method to initialize the interface """
        pass

    def start(self) -> "Interface":
        """Start the interface."""

        global INTERFACE_THREAD
        global INTERFACE_LOOP

        if self.state != INTERFACE_STATE_INITIALIZED:
            return

        # Start a new single event loop in a separate thread for all interfaces
        def start_threading_loop():
            global INTERFACE_LOOP
            INTERFACE_LOOP = asyncio.new_event_loop()
            asyncio.set_event_loop(INTERFACE_LOOP)
            INTERFACE_LOOP.run_forever()

        if not INTERFACE_THREAD:
            INTERFACE_THREAD = threading.Thread(target=start_threading_loop, daemon=True)
            INTERFACE_THREAD.start()

        # Wait till we have a loop running
        while True:
            if INTERFACE_LOOP:
                break
            time.sleep(0.1)

        # Schedule a task in the new loop to start the shell process
        asyncio.run_coroutine_threadsafe(
                    self.launch_interface(),
                    INTERFACE_LOOP
                )

        # Wait till we have started
        while True:
            if self.state == INTERFACE_STATE_STARTED:
                break
            time.sleep(0.1)

        return self

    async def launch_interface(self):
        """ Starts the shell process asynchronously.
            Returns a true value if the interface requires launching
        """
        if self.state != INTERFACE_STATE_INITIALIZED:
            return
        self.state = INTERFACE_STATE_STARTED
        return True

    @logger.catch
    def shutdown(self):
        """Callback when the shell process shutdowns."""
        self.state = INTERFACE_STATE_SHUTDOWN
        for on_shutdown in self._on_shutdown_callbacks:
            on_shutdown(self)

    def is_running(self) -> bool:
        return self.state == INTERFACE_STATE_STARTED

    def is_shutdown(self) -> bool:
        return self.state == INTERFACE_STATE_SHUTDOWN

    # EVENT HOOK SETUP

    @logger.catch
    def on_send(self, on_send: Callable):
        """Add a callback for when data is received"""
        self._on_send_callbacks.add(on_send)

    @logger.catch
    def on_receive(self, on_receive: Callable):
        """Add a callback for when data is received"""
        self._on_receive_callbacks.add(on_receive)

    @logger.catch
    def on_set_title(self, on_set_title: Callable):
        """Add a callback for when the window title is set"""
        self._on_set_title_callbacks.add(on_set_title)

    @logger.catch
    def on_set_title_handle(self, title: str):
        """Callback when the window title is set."""
        self.title = title
        for on_set_title in self._on_set_title_callbacks:
            on_set_title(self, title)

    @logger.catch
    def on_shutdown(self, on_shutdown: Callable):
        """Add a callback for when the shell process shutdowns"""
        self._on_shutdown_callbacks.add(on_shutdown)

    # IO

    async def send(self, data: bytes):
        """Sends data (in bytes) to the xterm"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")

        # Don't bother if we don't have data
        if not data:
            return

        # Add to the scrollback buffer
        self.scrollback_buffer += data

        # Dispatch to all listeners
        for on_send in self._on_send_callbacks:
            on_send(self, data)

    @logger.catch
    async def receive(self, data: bytes):
        """Recieves data from the xterm as a sequence of bytes.
        """

        # Don't bother if we don't have data
        if not data:
            return

        # Dispatch to all listeners
        for on_receive in self._on_receive_callbacks:
            on_receive(self, data)

    # CONTROLS

    def rows(self) -> int:
        return self.rows

    def cols(self) -> int:
        return self.cols

    def set_title(self, name:str):
        self.on_set_title_handle(name)

    def set_size(self, rows: int, cols: int, xpix: int=0, ypix: int=0):
        """Sets the shell window size."""
        pass

    def get_screen_display(self) -> bytes:
        """Get the current screen contents as a string"""
        return self.scrollback_buffer

    def get_cursor_position(self) -> tuple:
        return (0, 0)

    def term_client_metadata_update(self, client_id:str, data:dict) -> None:
        self.term_clients.setdefault(client_id, {})
        self.term_clients[client_id].update(data)

        min_row = None
        min_col = None
        for client_id, data in self.term_clients.items():
            if min_row is None or data["rows"] < min_row:
                min_row = data["rows"]
            if min_col is None or data["cols"] < min_col:
                min_col = data["cols"]
        self.rows = min_row
        self.cols = min_col

        self.set_size(rows=self.rows, cols=self.cols)
