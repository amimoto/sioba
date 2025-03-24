import asyncio
from typing import Callable, Optional
from niceterminal.interface import BufferedInterface, INTERFACE_STATE_STARTED, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_SHUTDOWN
from niceterminal.errors import InterfaceNotStarted
from loguru import logger

class SocketInterface(BufferedInterface):
    def __init__(self,
                 host: str,
                 port: int,
                 on_receive: Callable = None,
                 on_send: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 ):
        super().__init__(
            on_receive_from_xterm=on_receive,
            on_send_to_xterm=on_send,
            on_shutdown=on_shutdown,
            on_set_title=on_set_title
        )
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.send_queue = asyncio.Queue()  # Async queue for send operations
        self._receive_task = None
        self._send_task = None

    @logger.catch
    async def launch_interface(self):
        """Launch the socket interface"""
        print(f"launch_interface {self.state=}")
        if self.state != INTERFACE_STATE_INITIALIZED:
            return

        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = INTERFACE_STATE_STARTED

        # Start a socket connection
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

        # Create and start the receive and send tasks
        self._receive_task = asyncio.create_task(self._receive_loop())

        return True

    @logger.catch
    async def _receive_loop(self):
        """Continuously receive data from the socket"""
        while self.state == INTERFACE_STATE_STARTED:
            try:
                print("Receive loop started")
                data = await self.reader.read(4096)
                print(f"INCOMING: {data}")
                if not data:
                    break

                # Process received data
                await self.send_to_xterm(data)

            except ConnectionResetError as e:
                logger.debug(f"Connection reset: {e}")
                await self.shutdown()
                return
            except Exception as e:
                logger.error(f"Error in receive loop: {e=} {type(e)}")
                return

    @logger.catch
    async def receive_from_xterm(self, data: bytes):
        """Add data to the send queue"""
        if self.writer:
            data = data.replace(b"\r", b"\r\n")

            # Send to the socket
            self.writer.write(data)

            # Local echo the input
            await self.send_to_xterm(data)

    @logger.catch
    async def shutdown(self):
        """Shutdown the interface"""
        if self.state != INTERFACE_STATE_STARTED:
            return

        # Cancel background tasks
        if self._receive_task:
            self._receive_task.cancel()

        # Close the writer
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        # Set state to shutdown
        self.state = INTERFACE_STATE_SHUTDOWN

        # Call on_shutdown callback if provided
        if self.on_shutdown:
            await self.on_shutdown()