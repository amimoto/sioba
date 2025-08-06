from unittest import TestCase
from dataclasses import dataclass
from sioba import InterfaceContext


class TestingContext(TestCase):

    def test_context(self):

        # Test if we can import InterfaceContext without errors
        context = InterfaceContext(
            uri="tcp://localhost:1234",
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            title="Test Interface"
        )
        self.assertIsInstance(context, InterfaceContext)

        # Test if the parameters are set correctly
        self.assertEqual(context.uri, "tcp://localhost:1234")
        self.assertEqual(context.encoding, "utf-8")
        self.assertTrue(context.convertEol)
        self.assertTrue(context.auto_shutdown)
        self.assertEqual(context.title, "Test Interface")
        self.assertEqual(context.rows, 24)
        self.assertEqual(context.cols, 80)

        # Test the parse_uri function
        parsed = InterfaceContext.from_uri("tcp://localhost:1234?rows=52&cols=100")
        self.assertIsInstance(parsed, InterfaceContext)
        self.assertEqual(parsed.scheme, "tcp")
        self.assertEqual(parsed.netloc, "localhost:1234")
        self.assertEqual(parsed.rows, 52)
        self.assertEqual(parsed.cols, 100)
        self.assertEqual(parsed.query, {"rows": ["52"], "cols": ["100"]})
        self.assertEqual(parsed.encoding, "utf-8")
        self.assertEqual(parsed.convertEol, False)
        self.assertEqual(parsed.auto_shutdown, True)

        # Override some parameters
        parsed = InterfaceContext.from_uri(
            "tcp://localhost:1234?rows=52&cols=100",
            encoding="ascii",
            auto_shutdown=False,
        )
        self.assertIsInstance(parsed, InterfaceContext)
        self.assertEqual(parsed.encoding, "ascii")
        self.assertFalse(parsed.auto_shutdown)
        self.assertEqual(parsed.rows, 52)
        self.assertEqual(parsed.cols, 100)
        self.assertEqual(parsed.query, {"rows": ["52"], "cols": ["100"]})

        # Let's add some extra parameters
        parsed = InterfaceContext.from_uri(
            "tcp://localhost:1234?rows=52&cols=100",
            extra_params={
                "custom_param": "custom_value",
            }
        )
        self.assertEqual(parsed.extra_params, {"custom_param": "custom_value"})

        # Create a new context
        @dataclass
        class InheritedContext(InterfaceContext):
            # This class inherits from InterfaceContext to test inheritance and additional functionality
            test: str = "default_value"

        inherited_context = InheritedContext(
            uri="tcp://localhost:5678",
            title="Test Interface",
        )
        self.assertIsInstance(inherited_context, InheritedContext)
        self.assertEqual(inherited_context.uri, "tcp://localhost:5678")

        VERIFY = {
                'auto_shutdown': True,
                'cols': 80,
                'cursor_col': 0,
                'cursor_row': 0,
                'convertEol': False,
                'encoding': 'utf-8',
                'extra_params': {},
                'host': None,
                'netloc': None,
                'params': None,
                'password': None,
                'path': None,
                'port': None,
                'query': None,
                'rows': 24,
                'scheme': None,
                'scrollback_buffer_size': 10000,
                'scrollback_buffer_uri': None,
                'test': 'default_value',
                'title': 'Test Interface',
                'uri': 'tcp://localhost:5678',
                'username': None
            }

        self.assertEqual( inherited_context.asdict(), VERIFY)

        # Make sure copy works
        instance_copy = inherited_context.copy()
        self.assertIsNot(instance_copy, inherited_context)
        self.assertIsInstance(instance_copy, InheritedContext)
        self.assertEqual(instance_copy.asdict(), VERIFY)

    def test_context_extra_params(self):

        # Test if we can import InterfaceContext without errors
        context = InterfaceContext(
            extra_params={
                "banana": "yellow",
                "apple": "red",
            }
        )
        self.assertIsInstance(context, InterfaceContext)

        self.assertEqual(context.get("banana"), "yellow")



