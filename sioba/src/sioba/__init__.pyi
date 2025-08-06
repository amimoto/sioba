from __future__ import annotations

from .context import InterfaceContext as InterfaceContext

from .interface.base import (
    Interface as Interface,
    InterfaceState as InterfaceState,
)

from .interface.function import FunctionInterface as FunctionInterface
from .interface.echo import EchoInterface as EchoInterface
from .interface.socket import SocketInterface as SocketInterface
from .registry import (
    register_scheme as register_scheme,
    interface_from_uri as interface_from_uri,
    list_schemes as list_schemes,
)


__all__: list[str] = [
    "Interface",
    "InterfaceContext",
    "FunctionInterface",
    "EchoInterface",
    "SocketInterface",
    "InterfaceState",
    "register_scheme",
    "interface_from_uri",
    "list_schemes",
]

# Tell static type-checkers that runtime code *is* the source of truth
__version__ = "0.0.0"      # optional, but handy