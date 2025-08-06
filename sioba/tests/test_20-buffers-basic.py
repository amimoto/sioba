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
