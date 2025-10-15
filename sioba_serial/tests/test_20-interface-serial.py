from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    Interface,
)
import asyncio

class TestImportSerial(IsolatedAsyncioTestCase):

    async def test_serial_invoke_minimal(self):

        serial_uri = "serial+loop://?baudrate=10"

        # Construct the serial URI for the serial interface
        serial_interface = interface_from_uri(serial_uri)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)
        serial_interface.on_send_to_frontend(on_send_to_frontend)

        from sioba_serial.interface import SerialInterface
        self.assertIsInstance(serial_interface, SerialInterface)

        await serial_interface.start()
        await asyncio.sleep(0.2)

        # Send some data along
        test_message = b"Hello, serial!"
        await serial_interface.receive_from_frontend(test_message)

        await asyncio.sleep(0.2)
        self.assertTrue(len(frontend_buffer) > 0)
        buffer = b"".join(frontend_buffer)
        self.assertEqual(buffer, test_message)

