from typing import Callable

INTERFACE_STATE_INITIALIZED = 0
INTERFACE_STATE_STARTED = 1
INTERFACE_STATE_SHUTDOWN = 2

from loguru import logger

class Interface:
    def __init__(self,
                 on_read: Callable = None,
                 on_exit: Callable = None,
                 ):
        self._on_read_callbacks = set()
        self._on_exit_callbacks = set()
        self.state = INTERFACE_STATE_INITIALIZED
        if on_read:
            self.on_read(on_read)
        if on_exit:
            self.on_exit(on_exit)

    async def start(self):
        """Starts the shell process asynchronously."""
        pass

    @logger.catch
    async def write(self, data):
        """Writes data to the shell."""
        pass

    async def shutdown(self):
        """Shuts down the shell process."""
        pass

    @logger.catch
    def on_read(self, on_read: Callable):
        """Add a callback for when data is received"""
        self._on_read_callbacks.add(on_read)

    @logger.catch
    def on_read_handle(self, data:bytes):
        """Callback when data is available to read from the shell."""
        if data:
            for on_read in self._on_read_callbacks:
                on_read(self, data)

    @logger.catch
    def on_exit(self, on_exit: Callable):
        """Add a callback for when the shell process exits"""
        self._on_exit_callbacks.add(on_exit)

    @logger.catch
    def on_exit_handle(self):
        """Callback when the shell process exits."""
        for on_exit in self._on_exit_callbacks:
            on_exit(self)

    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        pass

    def get_screen_display(self) -> str:
        """Get the current screen contents as a string"""
        return ''

    def get_cursor_position(self) -> tuple:
        return (0, 0)

    async def start(self):
        pass

    def running(self) -> bool:
        return self.state == INTERFACE_STATE_STARTED