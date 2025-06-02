from urllib.parse import urlparse
from typing import Dict, Optional, Callable
from sioba.structs import InterfaceConfig

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

