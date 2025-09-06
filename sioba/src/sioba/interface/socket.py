import asyncio
from typing import Optional, TypedDict, Callable
from .base import Interface, InterfaceState, InterfaceContext, register_scheme
from loguru import logger
from dataclasses import dataclass

@register_scheme("tcp")
class SocketInterface(Interface):

    reader: Optional[asyncio.StreamReader] = None
    writer: Optional[asyncio.StreamWriter] = None
    _receive_task: Optional[asyncio.Task] = None
    _send_task: Optional[asyncio.Task] = None

    async def start_interface(self) -> bool:
        """Launch the socket interface"""
        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = InterfaceState.STARTED

        # Start a socket connection
        context = self.context
        connection = {
            "host": context.host,
            "port": context.port,
        }
        self.reader, self.writer = await asyncio.open_connection(**connection)

        # Create and start the receive and send tasks
        self._receive_task = asyncio.create_task(self._receive_loop())

        # Async queue for send operations
        self.send_queue = asyncio.Queue()

        return True

    @logger.catch
    async def _receive_loop(self):
        """Continuously receive data from the socket"""
        while self.state == InterfaceState.STARTED:
            try:
                if not ( reader := self.reader ):
                    logger.error("Socket reader is not initialized")
                    return

                if not ( data := await reader.read(4096) ):
                    break

                # Process received data
                await self.send_to_frontend(data)

            except ConnectionResetError as e:
                logger.debug(f"Connection reset: {e}")
                await self.shutdown()
                return

            except Exception as e:
                logger.error(f"Error in receive loop: {e=} {type(e)}")
                return

    @logger.catch
    async def receive_from_frontend_handle(self, data: bytes):
        """Add data to the send queue"""
        if not self.writer:
            return

        # Send to the socket
        data = data.replace(b"\r", b"\r\n")
        self.writer.write(data)

        # Local echo the input
        await self.send_to_frontend(data)

    async def shutdown_handle(self):
        """Shutdown the interface"""
        # Cancel background tasks
        if self._receive_task:
            self._receive_task.cancel()

        # Close the writer
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except ConnectionAbortedError:
                pass

from ssl import SSLContext, create_default_context, SSLError

@dataclass
class SecureSocketConfig(InterfaceContext):
    """Configuration for secure socket connections"""
    create_ssl_context: Optional[
                                Callable[["SecureSocketConfig"], SSLContext]
                            ]= None

@register_scheme("ssl", context_class=SecureSocketConfig)
class SecureSocketInterface(SocketInterface):

    async def start_interface(self) -> bool:
        """Launch the socket interface"""
        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = InterfaceState.STARTED

        context: SecureSocketConfig = self.context # type: ignore

        # Start a socket connection
        try:
          if context.create_ssl_context:
              ssl_ctx = context.create_ssl_context(self) # type: ignore
          else:
              ssl_ctx = create_default_context()
        except AttributeError:
            ssl_ctx = create_default_context()

        connection = {
            "host": context.host,
            "port": context.port,
            "ssl": ssl_ctx,
        }
        self.reader, self.writer = await asyncio.open_connection(**connection)

        # Create and start the receive and send tasks
        self._receive_task = asyncio.create_task(self._receive_loop())

        # Async queue for send operations
        self.send_queue = asyncio.Queue()

        return True

    async def shutdown_handle(self):
        try:
            await super().shutdown_handle()
        except SSLError as e:
            logger.warning(f"SSL error during shutdown: {e}")
