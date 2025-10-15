from unittest import IsolatedAsyncioTestCase
from sioba import (
    interface_from_uri,
    EchoInterface,
    Interface,
    InterfaceContext,
    list_schemes,
    register_scheme,
)

@register_scheme("testfalse")
class TestFalseInterface(Interface):
    __test__ = False
    default_context = InterfaceContext(
        convertEol=True,
    )

@register_scheme("testfalse2")
class TestFalseInterface2(Interface):
    __test__ = False
    default_context = InterfaceContext(
        convertEol=False,
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

    async def test_context_is_true(self):
        """ Ensure we can change a default True value to
            False via URI
        """

        test = interface_from_uri("testfalse://")

        self.assertIsInstance(test, TestFalseInterface)
        self.assertTrue(test.context.convertEol)

    async def test_context_to_false(self):
        """ Ensure we can change a default True value to
            False via URI
        """

        test = interface_from_uri("testfalse://?convertEol=0")

        self.assertIsInstance(test, TestFalseInterface)
        self.assertFalse(test.context.convertEol)

    async def test_context_to_default_false(self):
        """ While convertEol defaults to True in base, we want to
            ensure that if an interface defaults it to False,
            we can keep it False
        """

        test = interface_from_uri("testfalse2://")

        self.assertIsInstance(test, TestFalseInterface2)
        self.assertFalse(test.context.convertEol)








