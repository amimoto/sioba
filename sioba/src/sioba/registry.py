from importlib.metadata import entry_points

from urllib.parse import urlparse
from typing import Dict, Optional, Callable, List
from .structs import InterfaceConfig
from .base import Interface

INTERFACE_REGISTRY: Dict[str, type] = {}

def register_interface(*schemes: str):
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
            INTERFACE_REGISTRY[lower] = cls_or_factory
        return cls_or_factory
    return decorator

def list_interfaces() -> List[str]:
    """
    Returns a dictionary of all registered interfaces.
    The keys are the URI schemes, and the values are the interface classes.
    """
    eps = entry_points().select(group="sioba.interfaces")
    return [ep.name.lower() for ep in eps]

def init_interface(
                uri: str,
                interface_config: Optional[InterfaceConfig] = None,
                on_receive_from_control: Optional[Callable] = None,
                on_send_to_control: Optional[Callable] = None,
                on_shutdown: Optional[Callable] = None,
                on_set_terminal_title: Optional[Callable] = None,
                **kwargs,
                ):
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    try:
        # If we don't already have a type, let's have a look at the
        # entry points to see if we can find a handler for this scheme.
        if scheme not in INTERFACE_REGISTRY:
            eps = entry_points().select(group="sioba.interfaces")
            for ep in eps:
                if ep.name.lower() == scheme:
                    loaded = ep.load()
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
    except KeyError:
        raise ValueError(f"No handler registered for scheme {scheme!r}")
    return handler(
        uri=uri,
        interface_config=interface_config,
        on_receive_from_control=on_receive_from_control,
        on_send_to_control=on_send_to_control,
        on_shutdown=on_shutdown,
        on_set_terminal_title=on_set_terminal_title,
        **kwargs,
    )

