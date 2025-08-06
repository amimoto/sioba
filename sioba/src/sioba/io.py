from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio

import io

if TYPE_CHECKING:
    from .interface.base import Interface

class VirtualIO(io.TextIOBase):
    def __init__(self, interface: Interface) -> None:
        super().__init__()
        self.interface = interface
        self.main_loop = asyncio.get_running_loop()

    def write(self, data: bytes|str) -> int:
        if isinstance(data, str):
            data = data.encode(self.interface.context.encoding)

        # Send the data to the interface
        async def send_data():
            await self.interface.send_to_frontend(data)

        # self.interface.send_to_frontend(data)
        asyncio.create_task(send_data())

        return len(data)

    def flush(self) -> None:
        # Rich sometimes flushes
        pass

    def isatty(self) -> bool:
        # Rich uses this to decide whether to emit ANSI escapes.
        # Return True since we want colours
        return True

    @property
    def encoding(self) -> str:
        # Rich may inspect this to know how to encode text.
        return 'utf-8'




