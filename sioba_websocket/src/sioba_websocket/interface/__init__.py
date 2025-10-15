from sioba import (
    register_scheme,
    Interface,
    InterfaceState,
    InterfaceContext,
    Unset,
    UnsetFactory,
    UnsetOrNone,
    DefaultValuesContext,
)
import websockets.sync.client
import threading
import asyncio
from dataclasses import dataclass
from typing import Sequence

from loguru import logger

@dataclass
class WebsocketContext(InterfaceContext):

    # Acceptable values of the Origin header, for defending against
    # Cross-Site WebSocket Hijacking attacks. Values can be str to
    # test for an exact match or regular expressions compiled by
    # re.compile() to test against a pattern. Include None in the
    # list if the lack of an origin is acceptable
    origin:str|UnsetOrNone = UnsetFactory()

    # List of supported extensions, in order in which they should be
    # negotiated and run.
    extensions:Sequence[str]|UnsetOrNone = UnsetFactory()
    subprotocols:Sequence[str]|UnsetOrNone = UnsetFactory()

    # The “permessage-deflate” extension is enabled by default. Set
    # compression to None to disable it.
    compression:str|UnsetOrNone = UnsetFactory()

    #additional_headers=UnsetOrNone

    # Value of the Server response header. It defaults to
    # "Python/x.y.z websockets/X.Y".
    user_agent_header:str = UnsetFactory()

    # Timeout for opening the connection in seconds.
    open_timeout:int|UnsetOrNone = UnsetFactory()

    # Timeout for closing the connection in seconds.
    close_timeout:int|UnsetOrNone = UnsetFactory()

    # Maximum size of incoming messages in bytes.
    max_size:int|UnsetOrNone = UnsetFactory()

    # High-water mark of the buffer where frames are received.
    # It defaults to 16 frames. The low-water mark defaults to
    # max_queue // 4. You may pass a (high, low) tuple to set the
    # high-water and low-water marks. If you want to disable flow
    # control entirely, you may set it to None, although that’s a
    # bad idea.
    max_queue:int|UnsetOrNone = UnsetFactory()

"""
ssl=None
server_hostname=None
origin=None
extensions=None
subprotocols=None
compression='deflate'
additional_headers=None
user_agent_header='Python/3.10 websockets/15.0.1'
proxy=True
proxy_ssl=None
proxy_server_hostname=None
open_timeout=10
close_timeout=10
max_size=1048576
max_queue=16
logger=None
create_connection=None
"""


@dataclass
class WebsocketDefaultValuesContext(DefaultValuesContext):

    # The “permessage-deflate” extension is enabled by default. Set
    # compression to None to disable it.
    compression:str|UnsetOrNone = 'deflate'

    #additional_headers=UnsetOrNone

    # Value of the Server response header. It defaults to
    # "Python/x.y.z websockets/X.Y".
    user_agent_header:str = 'Python/3.10 websockets/15.0.1'

    # Timeout for opening the connection in seconds.
    open_timeout:int|UnsetOrNone = 10

    # Timeout for closing the connection in seconds.
    close_timeout:int|UnsetOrNone = 10

    # Maximum size of incoming messages in bytes.
    max_size:int|UnsetOrNone = 1048576

    # High-water mark of the buffer where frames are received.
    # It defaults to 16 frames. The low-water mark defaults to
    # max_queue // 4. You may pass a (high, low) tuple to set the
    # high-water and low-water marks. If you want to disable flow
    # control entirely, you may set it to None, although that’s a
    # bad idea.
    max_queue:int|UnsetOrNone = 16



@register_scheme("ws", context_class=WebsocketContext)
@register_scheme("wss")
class WebsocketInterface(Interface):

    default_context: InterfaceContext = WebsocketDefaultValuesContext()

    handle = None

    def filehandle_create(self):
        options = dict(
            uri=self.context.uri,
            extensions=self.context.extensions,
            subprotocols=self.context.subprotocols,
            compression=self.context.compression,
            user_agent_header=self.context.user_agent_header,
            open_timeout=self.context.open_timeout,
            close_timeout=self.context.close_timeout,
        )
        connect_config = {}
        for k,v in options.items():
            if v is not Unset:
                connect_config[k] = v

        print(connect_config)
        websocket = websockets.sync.client.connect(**connect_config)
        return websocket

    def filehandle_read(self) -> bytes:
        if not self.handle:
            logger.error("Socket reader is not initialized")
            raise ConnectionError("Socket reader is not initialized")
        data = self.handle.recv()
        if isinstance(data, str):
            data = data.encode()
        return data

    def filehandle_write(self, data: bytes):
        if not self.handle:
            logger.error("Socket writer is not initialized")
            raise ConnectionError("Socket writer is not initialized")
        self.handle.send(data)

    async def start_interface(self):
        """ Setup the websocket and the read loop """
        self.handle = self.filehandle_create()
        if not self.handle:
            raise ConnectionError("Failed to create websocket connection")

        self.state = InterfaceState.STARTED
        self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
        self.read_thread.start()

        # Store the main event loop for later use
        self.main_loop = asyncio.get_running_loop()

    def read_loop(self):
        """Continuously receive data from the socket"""
        while self.state == InterfaceState.STARTED:
            try:
                if not ( data := self.filehandle_read() ):
                    break

                read_future = asyncio.run_coroutine_threadsafe(
                    coro = self.send_to_frontend(data),
                    loop = self.main_loop,
                )
                read_future.result()

            except Exception as e:
                logger.error(f"Error in read loop: {e=} {type(e)}")
                return

    async def receive_from_frontend_handle(self, data: bytes) -> None:
        """Add data to the send queue"""
        self.filehandle_write(data)




