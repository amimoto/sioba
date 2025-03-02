import time
import asyncio
import pytest
import pytest_asyncio


from loguru import logger

from niceterminal.errors import InterfaceNotStarted
from niceterminal.interface.base import ( Interface,
                                            INTERFACE_STATE_STARTED,
                                            INTERFACE_STATE_INITIALIZED,
                                            INTERFACE_STATE_SHUTDOWN
                                        )

@pytest.mark.asyncio
async def test_interface():

    interface = Interface()
    assert interface.state == INTERFACE_STATE_INITIALIZED

    interface.start()
    assert interface.state == INTERFACE_STATE_STARTED

    interface.shutdown()
    assert interface.state == INTERFACE_STATE_SHUTDOWN


@pytest.mark.asyncio
async def test_io():

    global captured
    captured = b""

    def on_write(interface, data: bytes):
        global captured
        captured += data
        interface.read(data)

    interface = Interface(on_write=on_write)
    interface.start()

    data = b"Hello, World!"
    await interface.write(data)
    assert captured == data

    await interface.write(data)
    assert captured != data
    assert captured == data + data
    assert id(captured) != id(data)

@pytest.mark.asyncio
async def test_subclass():
    # Subclassing Interface test
    class Subclass(Interface):
        def init(self):
            self.captured = b""

        async def write(self, data: bytes):
            await super().write(data)
            self.captured += data

    interface = Subclass()
    assert interface.state == INTERFACE_STATE_INITIALIZED

    data = b"Hello, World!"
    assert interface

    with pytest.raises(InterfaceNotStarted):
        await interface.write(data)

    # Start the interface
    interface.start()
    assert interface.state == INTERFACE_STATE_STARTED

    # Now we can write
    await interface.write(data)
    assert interface.captured == data

    await interface.write(data)
    assert interface.captured != data
    assert interface.captured == data + data
    assert id(interface.captured) != id(data)
    interface.shutdown()

    assert interface.state == INTERFACE_STATE_SHUTDOWN