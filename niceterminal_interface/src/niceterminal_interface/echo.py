from .base import Interface, InterfaceConfig

from loguru import logger

class EchoInterface(Interface):

    config = InterfaceConfig(
        convertEol = True,
    )

    @logger.catch
    async def receive_from_control(self, data: bytes):
        data = data.replace(b"\r", b"\r\n")
        await self.send_to_control(data)

    def __del__(self):
        print(f"!!!!! deleted {self}")
