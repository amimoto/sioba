from .base import Interface, InterfaceConfig
from .registry import register_interface

from loguru import logger

@register_interface("echo")
class EchoInterface(Interface):

    default_config = InterfaceConfig(
        convertEol = True,
    )

    @logger.catch
    async def receive_from_control(self, data: bytes):
        """ Directly transfer what was received to the output creating
            a server based echo.
        """
        await self.send_to_control(data)
