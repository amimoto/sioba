import asyncio
from typing import Optional, TypedDict
from .base import PersistentInterface, InterfaceState, InterfaceConfig
from loguru import logger

class ConnectionConfig(TypedDict):
    """ Used to provide information into the asyncio.open_connection function """
    host: str
    port: int


class SocketInterface(PersistentInterface):

    config = InterfaceConfig(
        convertEol = True,
    )

    def __init__(self,
                 connection: ConnectionConfig,
                 **kwargs
                 ):
        super().__init__(**kwargs)
        self.connection = connection
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.send_queue = asyncio.Queue()  # Async queue for send operations
        self._receive_task = None
        self._send_task = None

    @logger.catch
    async def start_interface(self):
        """Launch the socket interface"""
        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = InterfaceState.STARTED

        # Start a socket connection
        self.reader, self.writer = await asyncio.open_connection(**self.connection)

        # Create and start the receive and send tasks
        self._receive_task = asyncio.create_task(self._receive_loop())

        return True

    @logger.catch
    async def _receive_loop(self):
        """Continuously receive data from the socket"""
        while self.state == InterfaceState.STARTED:
            try:
                data = await self.reader.read(4096)
                if not data:
                    break

                # Process received data
                await self.send_to_control(data)

            except ConnectionResetError as e:
                logger.debug(f"Connection reset: {e}")
                await self.shutdown()
                return
            except Exception as e:
                logger.error(f"Error in receive loop: {e=} {type(e)}")
                return

    @logger.catch
    async def receive_from_control(self, data: bytes):
        """Add data to the send queue"""
        if self.writer:
            data = data.replace(b"\r", b"\r\n")

            # Send to the socket
            self.writer.write(data)

            # Local echo the input
            await self.send_to_control(data)

    @logger.catch
    async def shutdown_interface(self):
        """Shutdown the interface"""
        # Cancel background tasks
        if self._receive_task:
            self._receive_task.cancel()

        # Close the writer
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()