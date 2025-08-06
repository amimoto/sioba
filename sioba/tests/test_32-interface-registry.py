from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    EchoInterface,
    Interface,
    list_schemes,
    register_scheme,
)

class TestInterfaces(IsolatedAsyncioTestCase):

    async def test_available_schemes(self):
        """ Checks that the schemes we expect are available """

        listed_schemes = list_schemes()
        for scheme in ["echo", "tcp", "dummy"]:
            self.assertIn(scheme, listed_schemes)

    async def test_bad_schemes(self):
        """ Checks that bad schemes raise an error  """
        with self.assertRaises(ValueError):
            await interface_from_uri("bad://")

    async def test_attempt_overwrite_scheme(self):
        """ Try and regsister a scheme that already exists """
        with self.assertRaises(KeyError):
            @register_scheme("echo")
            class AnotherEchoInterface(EchoInterface):
                pass

    async def test_dummy_interface(self):

        dummy = await interface_from_uri("dummy://").start()

        self.assertIsInstance(dummy, EchoInterface)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)

        dummy.on_send_to_frontend(on_send_to_frontend)

        await dummy.receive_from_frontend(b"Hello, World!")

        self.assertEqual(frontend_buffer, [b"Hello, World!"])

        await dummy.shutdown()

