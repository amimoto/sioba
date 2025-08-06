from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    EchoInterface,
    Interface,
)

class TestInterfaces(IsolatedAsyncioTestCase):

    async def test_echo_interface(self):
        echo = await interface_from_uri("echo://").start()

        self.assertIsInstance(echo, EchoInterface)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)

        echo.on_send_to_frontend(on_send_to_frontend)

        await echo.receive_from_frontend(b"Hello, World!")

        self.assertEqual(frontend_buffer, [b"Hello, World!"])

        await echo.shutdown()
