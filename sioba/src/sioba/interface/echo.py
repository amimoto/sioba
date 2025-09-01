from .base import (
    Interface,
    register_scheme,
)

@register_scheme("echo")
class EchoInterface(Interface):
    async def handle_receive_from_frontend(self, data: bytes) -> None:
        await self.send_to_frontend(data)


