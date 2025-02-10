from niceterminal.interface.base import Interface, \
                    INTERFACE_STATE_STARTED, \
                    INTERFACE_STATE_INITIALIZED
from loguru import logger

class EchoInterface(Interface):
    async def write(self, data: bytes):
        if data:
            self.read(data)
