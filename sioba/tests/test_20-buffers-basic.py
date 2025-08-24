from unittest import IsolatedAsyncioTestCase
from sioba import list_buffer_schemes

class TestBufferBasic(IsolatedAsyncioTestCase):

    async def test_buffer_list(self):
        """ Test if we can list buffers without errors. """
        buffers = list_buffer_schemes()
        self.assertIsInstance(buffers, list)
        self.assertGreater(len(buffers), 0)

        for expected_buffer_name in ["terminal", "line"]:
            self.assertIn(expected_buffer_name, buffers)

    async def test_buffer_registration(self):
        """ Test if we can register a new buffer without errors. """
        from sioba.buffer.base import register_buffer, list_buffer_schemes

        @register_buffer("dummy")
        class DummyBuffer:
            pass

        buffers = list_buffer_schemes()
        self.assertIn("dummy", buffers)

        # Let's see what happens if we try to register the same buffer again
        with self.assertRaises(KeyError):
            @register_buffer("dummy")
            class DummyBuffer2:
                pass

