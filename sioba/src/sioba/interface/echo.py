from .base import (
    Interface,
    register_scheme,
)

@register_scheme("echo")
class EchoInterface(Interface):
    async def receive_from_frontend_handle(self, data: bytes) -> None:
        await self.send_to_frontend(data)


