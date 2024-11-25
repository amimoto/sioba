from typing import Callable, Optional

import pyte

from .base import Interface

from loguru import logger

class PersistentInterface(Interface):
    """Wraps an InvokeProcess to provide pyte terminal emulation capabilities"""
    process = None

    def __init__(self,
                 process: Interface,
                 on_read: Callable = None,
                 on_exit: Callable = None,
                 columns: int = 80,
                 lines: int = 24):
        self.process = process
        super().__init__(on_read=on_read, on_exit=on_exit)

        # Initialize pyte screen and stream
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream(self.screen)

        # Wrap the process's on_read with our pyte handler
        self.process.on_read(self._pyte_handler)

    @logger.catch
    def _pyte_handler(self, process:Interface, data: bytes):
        """Handler that updates the pyte screen before passing data through"""
        try:
            self.stream.feed(data.decode('utf-8'))
        except UnicodeDecodeError:
            self.stream.feed(data.decode('utf-8', errors='replace'))

    # Delegate all InvokeProcess methods to the wrapped process
    @logger.catch
    def on_read(self, on_read: Callable):
        """Add a callback for when data is received"""
        self.process.on_read(on_read)

    @logger.catch
    async def start(self):
        """Starts the shell process asynchronously."""
        await self.process.start()

    @logger.catch
    async def write(self, data):
        """Writes data to the shell."""
        await self.process.write(data)

    @logger.catch
    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        self.process.set_size(row, col, xpix, ypix)
        self.screen.resize(lines=row, columns=col)

    @logger.catch
    async def shutdown(self):
        """Shuts down the shell process."""
        #await self.process.shutdown()
        pass

    @logger.catch
    # Additional pyte-specific methods
    def get_screen_display(self) -> str:
        """Get the current screen contents as a string"""
        return ''.join(self.screen.display)

    @logger.catch
    def get_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (self.screen.cursor.x, self.screen.cursor.y)

    @logger.catch
    def running(self) -> bool:
        """Check if the process is running"""
        return self.process.running()

    @logger.catch
    def __getattr__(self, name):
        """Delegate any other attributes to the wrapped process"""
        return getattr(self.process, name)