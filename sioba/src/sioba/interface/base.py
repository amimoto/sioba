from __future__ import annotations

from importlib.metadata import entry_points

from urllib.parse import urlparse

from typing import (
    Callable,
    Optional,
    Awaitable,
    Union,
    Any,
)

import asyncio
import uuid
import enum

from loguru import logger

from ..io import VirtualIO
from ..errors import (
    TerminalClosedError,
    InterfaceNotStarted,
)
from ..context import (
    InterfaceContext,
    DefaultValuesContext,
)
from ..buffer.base import (
    Buffer,
    buffer_from_uri,
)

###########################################################
# Registry for Interfaces
###########################################################

INTERFACE_REGISTRY: dict[str, type] = {}

def register_scheme(
        *schemes: str,
        context_class: Optional[type] = None
    ):
    """
    Decorator: annotate a class (or factory) as handling the given URI schemes.
    Example:
        @register_protocol("echo")
        class EchoInterface: ...
    """
    def decorator(cls_or_factory):
        for scheme in schemes:
            lower = scheme.lower()
            if lower in INTERFACE_REGISTRY:
                raise KeyError(f"Protocol {scheme!r} is already registered")

            # Mark the context class
            if context_class:
                cls_or_factory.context_class = context_class

            INTERFACE_REGISTRY[lower] = cls_or_factory
        return cls_or_factory
    return decorator

def list_schemes() -> list[str]:
    """
    Returns a dictionary of all registered interfaces.
    The keys are the URI schemes, and the values are the interface classes.
    """
    eps = entry_points().select(group="sioba.interface")
    schemes = set([ep.name.lower() for ep in eps]) | set(INTERFACE_REGISTRY.keys())
    return list(sorted(schemes))

def interface_from_uri(
                uri: str,
                context: Optional[InterfaceContext] = None,
                on_receive_from_frontend: Optional[Callable] = None,
                on_send_to_frontend: Optional[Callable] = None,
                on_shutdown: Optional[Callable] = None,
                on_set_terminal_title: Optional[Callable] = None,
                **kwargs,
                ):

    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()

    # If we don't already have a type, let's have a looki at the
    # entry points to see if we can find a handler for this scheme.
    if scheme not in INTERFACE_REGISTRY:
        eps = entry_points().select(group="sioba.interface")
        for ep in eps:
            if ep.name.lower() == scheme:
                break
        else:
            # If we didn't find a handler, let's try to discover them.
            # This is useful for plugins that register their own interfaces.
            # We only do this if we don't already have a handler registered.
            raise ValueError(f"No interface registered for scheme {scheme!r}")

        # Load and check if the loaded class is a subclass of Interface
        loaded = ep.load()
        if not issubclass(loaded, Interface):
            raise TypeError(f"{ep.name} → {loaded} does not subclass Interface")

        # Register the loaded handler in the registry
        INTERFACE_REGISTRY[scheme] = loaded

    handler = INTERFACE_REGISTRY[scheme]

    if not context:
        context_class = handler.context_class or InterfaceContext
        default_context = handler.default_context
        context = context_class.from_uri(
                                    uri,
                                    default_context=default_context,
                                    **kwargs
                                )

    return handler(
        context=context,
        on_receive_from_frontend=on_receive_from_frontend,
        on_send_to_frontend=on_send_to_frontend,
        on_shutdown=on_shutdown,
        on_set_terminal_title=on_set_terminal_title,
        **kwargs,
    )

###########################################################
# Interface State Enum
###########################################################

class InterfaceState(enum.Enum):
    """Represents the lifecycle states of an Interface:
    
    INITIALIZED - Interface instance created but not yet started
    STARTED - Interface is running and processing IO
    SHUTDOWN - Interface has been terminated and resources cleaned up
    """
    INITIALIZED = 0
    STARTED = 1
    SHUTDOWN = 2

###########################################################
# Callback Types
###########################################################
SyncSendToFrontendCallbackType = Callable[["Interface", bytes], None]
AsyncSendToFrontendCallbackType = Callable[["Interface", bytes], Awaitable[None]]
SyncReceiveFromFrontendCallbackType = Callable[["Interface", bytes], None]
AsyncReceiveFromFrontendCallbackType = Callable[["Interface", bytes], Awaitable[None]]
SyncOnSetTitleCallbackType = Callable[["Interface", str], None]
AsyncOnSetTitleCallbackType = Callable[["Interface", str], Awaitable[None]]
SyncOnShutdownCallbackType = Callable[["Interface"], None]
AsyncOnShutdownCallbackType = Callable[["Interface"], Awaitable[None]]

SendToFrontendCallbackType = Union[
    SyncSendToFrontendCallbackType
    | AsyncSendToFrontendCallbackType
]
ReceiveFromFrontendCallbackType = Union[
    SyncReceiveFromFrontendCallbackType
    | AsyncReceiveFromFrontendCallbackType
]
OnSetTitleCallbackType = Union[
    SyncOnSetTitleCallbackType
    | AsyncOnSetTitleCallbackType
]
OnShutdownCallbackType = Union[
    SyncOnShutdownCallbackType
    | AsyncOnShutdownCallbackType
]

###########################################################
# Basic Interface Class that provides what XTerm expects
###########################################################

class Interface:
    """ Interface is like the controller that abstracts the IO layer to the GUI layer.

        The basic flow is where the Instance is:

        - created with the appropriate context parameters
            - Done via __init__, subclass initialize(self, **kwargs) for additional customization
            - The instance's main loop isn't started here
        - start the main loop that handles IO
            - Done via the start(), subclass start_interface(self) for additional customization
                will allow any custom startup routines without needing super
            - By default we don't assume threading or asyncio for the main loop and start
                a new task or thread. This is left to the subclass to implement depending
                on the interface type
        - shutdown and associated processes are terminated and resources are reaped
            - Done via the shutdown(), subclass shutdown_interface(self) for additional customization

    """

    # The default context for the interface type. These are defaults for the
    # protocol level. These values can be overwritten on a case by case basis as needed
    # via the context argument. We don't use context so that it becomes available
    # for the protocol level context
    default_context: InterfaceContext = DefaultValuesContext()
    context: InterfaceContext
    context_class: Optional[type[InterfaceContext]] = None

    # The state of the interface. When initialized it's InterfaceState.INITIALIZED
    state: InterfaceState

    # This counds the number of gui controls referencing this interface.
    # Using this and the current interface state, we can figure out what the 
    reference_count: int

    # For persistence
    buffer: Buffer

    #######################################
    # Basic lifecycling handling
    #######################################

    def __init__(self,
                context: Optional[InterfaceContext] = None,
                on_receive_from_frontend: Optional[ReceiveFromFrontendCallbackType] = None,
                on_send_to_frontend: Optional[SendToFrontendCallbackType] = None,
                on_shutdown: Optional[OnShutdownCallbackType] = None,
                on_set_terminal_title: Optional[OnSetTitleCallbackType] = None,
                # Extra arguments for subclass initialization
                **extra: dict[str, Any]
                ) -> None:

        # Basic state and context
        self.id = str(uuid.uuid4())
        self.state = InterfaceState.INITIALIZED

        # For the number of GUI controls referencing this interface.
        self.reference_count = 0

        # Holds infomation on each terminial client
        # Things such as rows, cols
        self.term_clients = {}

        # Any extra parameters that a subclass might need
        self.extra = extra

        # Setup the interface context.
        if self.context_class:
            self.context = self.context_class.with_defaults(context)
        else:
            self.context = InterfaceContext.with_defaults(context)

        if self.default_context:
            self.context.fill_missing(self.default_context)

        if context:
            self.context.update(context)

        # Setup the callback registry
        self._on_receive_from_frontend_callbacks: set[ReceiveFromFrontendCallbackType] = set()
        self._on_send_from_xterm_callbacks: set[SendToFrontendCallbackType] = set()
        self._on_shutdown_callbacks = set()
        self._on_set_terminal_title_callbacks: set[OnSetTitleCallbackType] = set()
        if on_receive_from_frontend:
            self.on_receive_from_frontend(on_receive_from_frontend)
        if on_send_to_frontend:
            self.on_send_to_frontend(on_send_to_frontend)
        if on_shutdown:
            self.on_shutdown(on_shutdown)
        if on_set_terminal_title:
            self.on_set_terminal_title(on_set_terminal_title)

        # Handle the buffer if we want one
        if self.context.scrollback_buffer_uri:
            self.buffer = buffer_from_uri(
                str(self.context.scrollback_buffer_uri),
                interface=self,
                on_set_terminal_title=self.set_terminal_title,
            )
        else:
            self.buffer = Buffer(interface=self)

        # Now do the subclass specific initialization
        self.initialize()

    def initialize(self, **kwargs) -> None:
        """ Subclassable method to initialize the interface.
            This is called after the __init__ method and before the start method.
            It can be used to set up any additional state or context.
        """
        pass

    async def start(self) -> "Interface":
        """ Start the interface.
            This is the initial entrypoint that kicks off things such as a thread
            if required. By default we work with the assumption that we're working
            in an asyncio environment. Threading left to the individual interfaces to
            implement if there are syncronous operations required.
        """
        # Start the interface. This calls tasks required to finalize
        # the interface setup. For example, in the case of a socket
        # interface, this would start the socket connection.
        if self.state != InterfaceState.INITIALIZED:
            return self
        try:
            ok = await self.start_interface()
            if ok is False:
                raise RuntimeError("start_interface returned False")
            self.state = InterfaceState.STARTED
        except Exception:
            self.state = InterfaceState.SHUTDOWN
            raise
        return self

    async def start_interface(self) -> bool:
        return True

    async def shutdown(self) -> None:
        """Callback when the shell process shutdowns."""
        if self.state != InterfaceState.STARTED:
            return
        await self.shutdown_handle()
        self.state = InterfaceState.SHUTDOWN
        logger.debug(f"Shutting down interface {self.id}")
        for on_shutdown in self._on_shutdown_callbacks:
            res = on_shutdown(self)
            if asyncio.iscoroutine(res):
                await res

    def on_shutdown(self, on_shutdown: OnShutdownCallbackType) -> None:
        """Add a callback for when the shell process shutdowns"""
        self._on_shutdown_callbacks.add(on_shutdown)

    async def shutdown_handle(self) -> None:
        pass

    #######################################
    # Lifecycle state querying
    #######################################

    def is_running(self) -> bool:
        return self.state == InterfaceState.STARTED

    def is_shutdown(self) -> bool:
        return self.state == InterfaceState.SHUTDOWN

    #######################################
    # IO Events
    #######################################

    def on_send_to_frontend(self, on_send: SendToFrontendCallbackType) -> None:
        """Add a callback for when data is received"""
        self._on_send_from_xterm_callbacks.add(on_send)

    def on_receive_from_frontend(self, on_receive: ReceiveFromFrontendCallbackType) -> None:
        """Add a callback for when data is received"""
        self._on_receive_from_frontend_callbacks.add(on_receive)

    async def send_to_frontend(self, data: bytes) -> None:
        """Sends data (in bytes) to the xterm"""
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")
        elif self.state == InterfaceState.SHUTDOWN:
            raise TerminalClosedError(f"Unable to send data {repr(data)}, interface is shutdown")

        # Don't bother if we don't have data
        if not data:
            return

        if self.context.convertEol:
            tmp = data.replace(b"\n", b"\r\n")
            logger.debug(f"send_to_frontend: `{data}` [convertEol]=> `{tmp}`")
            data = tmp
        else:
            logger.debug(f"send_to_frontend: `{data}`")

        # Process the data through a subclassable function
        await self.send_to_frontend_handle(data)

        # updates the pyte screen before passing data through
        await self.buffer.feed(data)

        # Dispatch to all listeners
        for on_send in self._on_send_from_xterm_callbacks:
            logger.debug(f"Sending data to xterm: {self.context.convertEol} / {data}")
            res = on_send(self, data)
            if asyncio.iscoroutine(res):
                await res

    async def send_to_frontend_handle(self, data: bytes) -> None:
        """
        Handles sending data to the frontend.
        Available for subclasses to override.
        """
        pass

    async def receive_from_frontend(self, data: bytes) -> None:
        """Receives data from the xterm as a sequence of bytes.
        """

        if self.context.convertEol:
            # We convert all \r\n and just \r to \n since we want to
            # handle newlines in a consistent manner as \n
            tmp = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
            logger.debug(f"receive_from_frontend: `{data}` [convertEol]=> `{tmp}`")
            data = tmp
        else:
            logger.debug(f"recieve_from_frontend: `{data}`")

        # Process the data through a subclassable function
        await self.receive_from_frontend_handle(data)

        if self.context.local_echo:
            # Local echo the input
            await self.send_to_frontend(data)

        # Dispatch to all listeners
        for on_receive in self._on_receive_from_frontend_callbacks:
            res = on_receive(self, data)
            if asyncio.iscoroutine(res):
                await res

    async def receive_from_frontend_handle(self, data: bytes) -> None:
        """
        Handles receiving data from the frontend
        Available for subclasses to override.
        """
        pass

    def filehandle(self) -> VirtualIO:
        """Returns a file-like object that can be used to write to the interface."""
        return VirtualIO(self)

    #######################################
    # Terminal Buffer Abstraction
    #######################################

    def on_set_terminal_title(self, on_set_terminal_title: OnSetTitleCallbackType) -> None:
        """Add a callback for when the window title is set"""
        self._on_set_terminal_title_callbacks.add(on_set_terminal_title)

    def set_terminal_title(self, title:str) -> None:
        """ This sets the terminal title via the EventsScreen.
            This is done because we need to set the title in both
            the current Interface but also in the EventsScreen

            The buffer should set the title in the context
            but this is available so we can intercept requests and
            do anything fun with it
        """
        self.context.title = title

        self.set_terminal_title_handle(title)

        for on_set_terminal_title in self._on_set_terminal_title_callbacks:
            res = on_set_terminal_title(self, title)
            if asyncio.iscoroutine(res):
                try:
                    asyncio.get_running_loop()
                # If no running loop, we create one to run the coroutine
                except RuntimeError:
                    asyncio.run(res)
                else:
                    asyncio.create_task(res)

    def set_terminal_title_handle(self, title: str) -> None:
        """Callback when the window title is set."""
        pass

    def set_terminal_size(self, rows: int, cols: int, xpix: int=0, ypix: int=0) -> None:
        """Sets the shell window size."""
        self.buffer.set_terminal_size(
            rows=rows,
            cols=cols,
            xpix=xpix,
            ypix=ypix
        )

    def get_terminal_buffer(self) -> bytes:
        """Get the current screen contents as a string"""
        buf = self.buffer.get_terminal_buffer()
        if self.context.convertEol:
            buf = buf.replace(b"\n", b"\r\n")
        return buf

    def get_terminal_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (
            self.context.cursor_row,
            self.context.cursor_col
        )

    def update_terminal_metadata(
            self,
            data:dict,
            client_id:str='__default__',
        ) -> None:
        self.term_clients.setdefault(client_id, {})
        self.term_clients[client_id].update(data)

        logger.debug(f"Updated client {client_id} metadata: {data}")

        # Since we m,ayu have multiple clients, we search for the
        # smallest terminal size and set that as the current
        # terminal size (This is behaviour similar to tmux)
        min_row = None
        min_col = None
        for client_id, data in self.term_clients.items():
            if min_row is None or data["rows"] < min_row:
                min_row = data["rows"]
            if min_col is None or data["cols"] < min_col:
                min_col = data["cols"]

        self.context.rows = min_row
        self.context.cols = min_col

        logger.debug(f"Setting terminal size to {min_row} rows and {min_col} cols")

        self.set_terminal_size(rows=min_row, cols=min_col)

    def get_terminal_metadata(self, client_id:str='__default__') -> dict:
        if client_id not in self.term_clients:
            return {}
        return self.term_clients[client_id]

    def reference_increment(self):
        self.reference_count += 1

    def reference_decrement(self):
        self.reference_count -= 1
        if self.reference_count <= 0:
            if self.context.auto_shutdown:
                asyncio.create_task(
                    self.shutdown()
                )





