from __future__ import annotations
from typing import TYPE_CHECKING

from importlib.metadata import entry_points
from urllib.parse import urlparse

from typing import Any

from weakref import ProxyType

if TYPE_CHECKING:
    from ..interface.base import Interface

BUFFER_REGISTRY: dict[str, type] = {}

def register_buffer(
        *schemes: str,
    ):
    """
    Decorator: annotate a class (or factory) as handling the given URI schemes.
    Example:
        @register_buffer("lines")
        class LineBuffer: ...
    """
    def decorator(cls_or_factory):
        for scheme in schemes:
            lower = scheme.lower()
            if lower in BUFFER_REGISTRY:
                raise KeyError(f"Protocol {scheme!r} is already registered")
            BUFFER_REGISTRY[lower] = cls_or_factory
        return cls_or_factory
    return decorator

def list_buffer_schemes() -> list[str]:
    """
    Returns a dictionary of all registered buffers.
    The keys are the URI schemes, and the values are the interface classes.
    """
    eps = entry_points().select(group="sioba.buffer")
    schemes = set([ep.name.lower() for ep in eps]) | set(BUFFER_REGISTRY.keys())
    return list(sorted(schemes))

def buffer_from_uri(uri: str, **kwargs):

    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()

    # If we don't already have a type, let's have a look at the
    # entry points to see if we can find a handler for this scheme.
    if scheme not in BUFFER_REGISTRY:
        eps = entry_points().select(group="sioba.buffer")
        for ep in eps:
            if ep.name.lower() == scheme:
                break
        else:
            # If we didn't find a handler, let's try to discover them.
            # This is useful for plugins that register their own buffers.
            # We only do this if we don't already have a handler registered.
            raise ValueError(f"No buffer registered for scheme {scheme!r}")

        # Load and check if the loaded class is a subclass of buffer
        loaded = ep.load()
        if not issubclass(loaded, Buffer):
            raise TypeError(f"{ep.name} → {loaded} does not subclass buffer")

        # Register the loaded handler in the registry
        BUFFER_REGISTRY[scheme] = loaded

    handler = BUFFER_REGISTRY[scheme]

    return handler(**kwargs)

class Buffer:
    """
    Base class for buffer implementations.
    This class should be inherited by all buffer implementations.
    """

    interface: ProxyType[Interface]

    def __init__(
            self,
            interface,
            **extra: dict[str, Any]
        ):
        """
        Initialize the buffer with optional arguments.
        """

        self.interface = interface
        self.context = interface.context
        self.scrollback_buffer_size = interface.context.scrollback_buffer_size

        self.initialize(**extra)

    def initialize(self, **extra):
        """ Subclassable method to initialize the interface.
            This is called after the __init__ method
            It can be used to set up any additional state or configuration.
        """
        pass

    async def feed(self, data: bytes) -> None:
        """ This intercepts data sent to the frontend.
            We will use this to capture the data sent to the frontend
            and store it in the scrollback buffer.
        """
        pass

    def set_terminal_size(
            self,
            rows: int,
            cols: int,
            xpix: int=0,
            ypix: int=0
        ) -> None:
        pass

    def dump_screen_state(self) -> bytes:
        """ Dump the current screen state as bytes.
            This is used to dump the current state of the buffer.
        """
        return b""

    def get_terminal_buffer(self) -> bytes:
        return self.dump_screen_state()





