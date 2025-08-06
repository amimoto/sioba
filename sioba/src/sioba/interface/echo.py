from .base import Interface, InterfaceContext, register_scheme

from loguru import logger

@register_scheme("echo")
class EchoInterface(Interface):

    default_context = InterfaceContext(
        convertEol = True,
    )

    @logger.catch
    async def receive_from_frontend(self, data: bytes):
        """ Directly transfer what was received to the output creating
            a server based echo.
        """
        await self.send_to_frontend(data)
        await super().receive_from_frontend(data)

