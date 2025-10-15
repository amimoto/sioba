import asyncio
from .base import Interface, InterfaceState
from loguru import logger
import threading

from sioba.errors import (
    TerminalClosedError as TerminalClosedError,
)

class IOInterface(Interface):
    handle = None

    def filehandle_create(self):
        raise NotImplementedError()

    async def start_interface(self) -> bool:
        """ Setup the serial and the read loop """
        self.handle = self.filehandle_create()
        if not self.handle:
            raise ConnectionError("Failed to open connection")

        self.state = InterfaceState.STARTED
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()

        # Store the main event loop for later use
        self.main_loop = asyncio.get_running_loop()

        return True

    ###################################
    # Receiving data from the filehandle
    ###################################

    def filehandle_read(self) -> bytes:
        return self.handle.read() # type: ignore

    def read_loop(self):
        """Continuously receive data from the socket"""
        while self.state == InterfaceState.STARTED:
            try:
                if not self.handle:
                    logger.error("Reader is not initialized")
                    raise ConnectionError("Reader is not initialized")

                data = self.filehandle_read()
                if data is None:
                    break

                if isinstance(data, str):
                    data = data.encode()

                read_future = asyncio.run_coroutine_threadsafe(
                    coro = self.send_to_frontend(data),
                    loop = self.main_loop,
                )
                read_future.result()

            except TerminalClosedError:
                logger.debug("Terminal closed, stopping read loop")
                return
            except Exception as e:
                logger.error(f"Error in read loop: {e=} {type(e)}")
                return

    ###################################
    # Sending data to the filehandle
    ###################################

    def filehandle_write(self, data: bytes):
        self.handle.write(data) # type: ignore

    async def receive_from_frontend_handle(self, data: bytes) -> None:
        """Add data to the send queue"""
        if not self.handle:
            logger.error("Writer is not initialized")
            raise ConnectionError("Writer is not initialized")
        self.filehandle_write(data)


