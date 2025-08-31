from .base import (
    Interface,
    InterfaceContext,
    register_scheme,
)

import asyncio

@register_scheme("echo")
class EchoInterface(Interface):

    def initialize(self, **_) -> None:
        async def _on_receive_from_frontend(interface: Interface, data: bytes):
            await interface.send_to_frontend(data)
        self.on_receive_from_frontend(_on_receive_from_frontend)

