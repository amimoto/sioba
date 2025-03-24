from niceterminal.interface.base import Interface

from loguru import logger

class EchoInterface(Interface):
    @logger.catch
    async def receive_from_xterm(self, data: bytes):
        await self.send_to_xterm(data)
