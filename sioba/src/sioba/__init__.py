from __future__ import annotations

from .context import (
    InterfaceContext as InterfaceContext,
    Unset as Unset,
    UnsetType as UnsetType,
    UnsetFactory as UnsetFactory,
    UnsetOrNone as UnsetOrNone,
    DefaultValuesContext as DefaultValuesContext,
)

from .interface.base import (
    Interface as Interface,
    InterfaceState as InterfaceState,
    register_scheme as register_scheme,
    interface_from_uri as interface_from_uri,
    list_schemes as list_schemes,
)

from .buffer.base import (
    register_buffer as register_buffer,
    list_buffer_schemes as list_buffer_schemes,
    buffer_from_uri as buffer_from_uri,
)

from .interface.function import FunctionInterface as FunctionInterface
from .interface.echo import EchoInterface as EchoInterface
from .interface.socket import (
    SocketInterface as SocketInterface,
    SecureSocketInterface as SecureSocketInterface,
    UDPInterface as UDPInterface,
)
from .interface.io import (
    IOInterface as IOInterface,
)

__all__: list[str] = [
    "Interface",
    "InterfaceContext",
    "FunctionInterface",
    "EchoInterface",
    "SocketInterface",
    "SecureSocketInterface",
    "UDPInterface",
    "IOInterface",
    "InterfaceState",

    "register_scheme",
    "interface_from_uri",
    "list_schemes",

    "register_buffer",
    "list_buffer_schemes",
    "buffer_from_uri",
]

# Tell static type-checkers that runtime code *is* the source of truth
__version__ = "0.0.0"      # optional, but handy