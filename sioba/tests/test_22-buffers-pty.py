from unittest import IsolatedAsyncioTestCase
from sioba import InterfaceContext, buffer_from_uri

class TestTerminalBuffer(IsolatedAsyncioTestCase):

    def create_buffer(self, buffer_uri: str = "terminal://", **context_extra):

        context_args = dict(
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            title="Test Interface",
            scrollback_buffer_uri=buffer_uri,
            scrollback_buffer_size=10,
            rows=5,
            cols=80,
        )

        context_args.update(context_extra)
        context = InterfaceContext(**context_args)

        title_change_events = []
        def on_set_terminal_title(title: str) -> None:
            """ Mock function to set terminal title. """
            title_change_events.append(title)

        class MockInterface:
            def __init__(self, context):
                self.context = context

        buffer = buffer_from_uri(
                    buffer_uri,
                    interface=MockInterface(context),
                    on_set_terminal_title=on_set_terminal_title,
                )

        return buffer

    async def test_terminal_buffer(self):
        """ Test the terminal implementation. """
        buffer = self.create_buffer()

        from sioba.buffer.terminal import TerminalBuffer
        self.assertIsInstance(buffer, TerminalBuffer)

        test_text = b"Hello"
        await buffer.feed(test_text)

        data = buffer.dump_screen_state()
        self.assertIn(test_text, data)

        await buffer.feed(test_text)
        data = buffer.dump_screen_state()
        self.assertRegex(data.decode(), rf"\b{(test_text*2).decode()}\b")
        self.assertNotRegex(data.decode(), rf"\b{test_text.decode()}\b")

        await buffer.feed(b"\n"+test_text+b"\n")
        data = buffer.dump_screen_state()
        self.assertRegex(data.decode(), rf"\b{(test_text*2).decode()}\b")
        self.assertRegex(data.decode(), rf"\b{test_text.decode()}\b")

        # What happens if we feed more than max_buffer_lines?
        for i in range(1,20):
            await buffer.feed(f"<{i}>\r\n".encode())

        data = buffer.screen.dump_screen_state_clean(buffer.screen)
        for i in range(1, 6):
            self.assertNotIn(f"<{i}>".encode(), data)
        for i in range(6, 20):
            self.assertIn(f"<{i}>".encode(), data)

    async def test_terminal_buffer_long_lines(self):
        """ Test really long lines and cursor position. """

        buffer = self.create_buffer()
        context = buffer.interface.context

        long_string = b"abcdefghijklmnopqrstuvwxyz"

        await buffer.feed(b"foo")
        self.assertEqual(context.cursor_row, 0)
        self.assertEqual(context.cursor_col, 3)

        await buffer.feed(long_string)
        self.assertEqual(context.cursor_row, 0)
        self.assertEqual(context.cursor_col, 29)

        # Change the terminal size
        buffer.set_terminal_size(rows=10, cols=10)
        self.assertEqual(context.cursor_row, 0)
        self.assertEqual(context.cursor_col, 0)

        await buffer.feed(long_string)
        self.assertEqual(context.cursor_row, 2)
        self.assertEqual(context.cursor_col, 6)

    async def test_terminal_buffer_resizing(self):
        pass


