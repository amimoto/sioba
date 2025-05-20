from .base import Interface

from loguru import logger

class EchoInterface(Interface):
    @logger.catch
    async def receive_from_control(self, data: bytes):
        await self.send_to_control(data)

    def __del__(self):
        print(f"!!!!! deleted {self}")
