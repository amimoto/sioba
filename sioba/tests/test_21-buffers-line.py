from unittest import IsolatedAsyncioTestCase
from sioba import InterfaceContext, buffer_from_uri

class MockInterface:
    def __init__(self, context):
        self.context = context

class TestBuffers(IsolatedAsyncioTestCase):

    async def test_line_buffer(self):
        """ Test the RawBuffer implementation. """

        buffer_uri = "line://"
        context = InterfaceContext.with_defaults(
            title="Test Interface",
            scrollback_buffer_uri=buffer_uri,
            scrollback_buffer_size=10,
            rows=5,
        )

        title_change_events = []
        def on_set_terminal_title(title: str) -> None:
            """ Mock function to set terminal title. """
            title_change_events.append(title)

        buffer = buffer_from_uri(
                    buffer_uri,
                    interface=MockInterface(context),
                    on_set_terminal_title=on_set_terminal_title,
                )

        from sioba.buffer.line import LineBuffer
        self.assertIsInstance(buffer, LineBuffer)

        # Check initial state
        self.assertEqual(len(buffer.buffer_lines), 1)
        self.assertEqual(buffer.buffer_lines[0], b"")

        test_text = b"Hello"
        await buffer.feed(test_text)

        data = buffer.dump_screen_state()
        self.assertEqual(data, test_text)

        await buffer.feed(test_text)
        data = buffer.dump_screen_state()
        self.assertEqual(data, test_text*2)

        await buffer.feed(b"\n"+test_text+b"\n")
        data = buffer.dump_screen_state()
        self.assertEqual(data, test_text*2+b"\n"+test_text)

        # What happens if we feed more than max_buffer_lines?
        for i in range(1,20):
            await buffer.feed(f"<{i}>\n".encode())

        data = buffer.dump_screen_state()
        for i in range(1, 6):
            self.assertNotIn(f"<{i}>".encode(), data)
        for i in range(6, 20):
            self.assertIn(f"<{i}>".encode(), data)



