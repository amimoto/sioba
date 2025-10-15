from unittest import IsolatedAsyncioTestCase
import re
from sioba import (
    FunctionInterface,
    Interface,
    InterfaceState,
    InterfaceContext,
    DefaultValuesContext,
)
from sioba.interface.function import get_next_line, CaptureMode
from sioba.errors import InterfaceShutdown, InterfaceNotStarted
import asyncio

class TestInterfaces(IsolatedAsyncioTestCase):

    def input_test_harness(self):
        """ Creates a input test harness for FunctionInterface """

        capture_frontend_buffer = []
        def on_send_to_frontend(interface: Interface, data: bytes):
            capture_frontend_buffer.append(data)

        # We test what will happen if we try to print something
        # after the interface has been shutdown.
        def func_code(interface: FunctionInterface):
            import time
            time.sleep(1)

        capture_frontend_buffer.clear()
        func = FunctionInterface(func_code)
        func.on_send_to_frontend(on_send_to_frontend)

        return capture_frontend_buffer, func

    async def test_function_line_parser(self):
        # Basic parser. This is a test to see how the text is split into lines
        next_line_tests = [
            [ b'abcd',         (b'abcd', b'', b'') ],
            [ b'abcd\r\nefgh', (b'abcd', b'\n', b'efgh') ],
            [ b'abcd\n\refgh', (b'abcd', b'\n', b'efgh') ],
            [ b'abcd\refgh',   (b'abcd', b'\n', b'efgh') ],
            [ b'abcd\x03efgh', (b'abcd', b'\x03', b'efgh') ],
            [ b'\x03efgh',     (b'', b'\x03', b'efgh') ],
        ]
        for test_input, expected_output in next_line_tests:
            next_line = get_next_line(test_input)
            self.assertEqual(next_line, expected_output)

    async def test_function_interface(self):
        caught_exceptions = []
        def func_code(interface: FunctionInterface):
            try:
                interface.print("Hello, World!")
                interface.print("This is a simple script.")

                name = interface.input("What's your name? ")
                interface.print(f"Hello, {name}!")

                hidden = interface.getpass("Enter your hidden word: ")
                interface.print(f"Your hidden word is: {hidden}")

                import time
                time.sleep(0.2)

                _ = interface.input("Final message")

            except Exception as e:
                caught_exceptions.append(e)

            raise Exception("Random Error")

        buffer_uri = "line://"
        context = DefaultValuesContext(
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            title="Test Interface",
            scrollback_buffer_uri=buffer_uri,
            scrollback_buffer_size=10,
            rows=5,
        )
        func = FunctionInterface(func_code, context=context)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)
        func.on_send_to_frontend(on_send_to_frontend)

        await func.start()
        self.assertIsInstance(func, FunctionInterface)

        await asyncio.sleep(0.2)
        self.assertEqual(frontend_buffer[0], b"Hello, World!\r\n")

        # This will handle `input`
        await func.receive_from_frontend(b"Mochi\r\n")
        await asyncio.sleep(0.1)

        # We should see Mochi twice since we don't hide the input
        buffer = func.get_terminal_buffer()
        self.assertIn(b"your name? Mochi", buffer)
        self.assertIn(b"Hello, Mochi!", buffer)
        self.assertEqual(
            len(re.findall(b"Mochi", buffer)),
            2
        )

        # Then handle `getpass`
        await func.receive_from_frontend(b"Wasabi\r\n")
        await asyncio.sleep(0.1)

        # For getpass we only expect one showing of Wasabi
        buffer = func.get_terminal_buffer()
        self.assertEqual(
            len(re.findall(b"Wasabi", buffer)),
            1
        )

        # By doing a shutdown now, we should trigger an exception within the
        # func_code that will be caught
        await func.shutdown()
        await asyncio.sleep(0.1)

        with self.assertRaises(InterfaceShutdown):
            await func.receive_from_frontend(b"Final message\r\n")

        self.assertIn(len(caught_exceptions), [0, 1])

    async def test_function_interfaceshutdown_exception(self):
        # We want to skip the InterfaceShutdown exception
        # so let's trigger that

        # We test what will happen if we try to print something
        # after the interface has been shutdown.
        caught_exceptions = []
        def func_code2(interface: FunctionInterface):
            import time
            for i in range(200):
                interface.print("This should trigger an exception")
                time.sleep(0.2)

        func2 = FunctionInterface(func_code2)

        frontend_buffer = []
        async def on_send_to_frontend(interface: Interface, data: bytes):
            frontend_buffer.append(data)
        func2.on_send_to_frontend(on_send_to_frontend)

        # To be able to test we need to start the interface
        await func2.start()

        # Then we need to stop the interface to ensure shutdown
        await func2.shutdown()

        # Let's trigger the InterfaceShutdown exception
        with self.assertRaises(InterfaceShutdown):
            await func2.receive_from_frontend(b"baana\r\n")

    async def test_function_interfaceshutdown_exception_runtimeerror(self):
        # In this case when the shutdown is crashes if the loop has failed
        # which is fine.

        class FunctionInterfaceShutdownBoom(FunctionInterface):
            async def shutdown(self) -> None:
                raise RuntimeError("Boom!")

        # We test what will happen if we try to print something
        # after the interface has been shutdown.
        def func_code(interface: FunctionInterface):
            raise Exception("Boomboom")

        func = FunctionInterfaceShutdownBoom(func_code)

        # To be able to test we need to start the interface
        await func.start()

        await asyncio.sleep(0.2)

    async def test_function_input_capturemode_echo(self):
        """ receive_from_frontend should handle different capture modes """
        ##############################################
        # ECHO mode
        ##############################################

        capture_frontend_buffer, func = self.input_test_harness()

        # To be able to test we need to start the interface
        await func.start()

        # Let's test the capture modes
        func.capture_mode = CaptureMode.ECHO
        await func.receive_from_frontend(b"Hello World\r\n")
        await asyncio.sleep(0.1)

        # In ECHO mode, the data should be echoed back to the frontend
        self.assertEqual(len(capture_frontend_buffer), 1)
        self.assertEqual(capture_frontend_buffer[0], b"Hello World")

        # Let's hit things with the control C
        await func.receive_from_frontend(b"\x03")
        self.assertEqual(func.state, InterfaceState.SHUTDOWN)

    async def test_function_input_capturemode_discard(self):
        ##############################################
        # DISCARD mode
        ##############################################
        capture_frontend_buffer, func = self.input_test_harness()

        # To be able to test we need to start the interface
        await func.start()

        # Now let's test the DISCARD
        func.capture_mode = CaptureMode.DISCARD
        await func.receive_from_frontend(b"LINE\r\n")
        await asyncio.sleep(0.1)

        # In DISCARD mode, the data should not be echoed back
        self.assertEqual(len(capture_frontend_buffer), 0)

        # Let's hit things with the control C
        await func.receive_from_frontend(b"\x03")
        self.assertEqual(func.state, InterfaceState.SHUTDOWN)

    async def test_function_input_capturemode_input(self):
        ##############################################
        # INPUT
        ##############################################
        _, func = self.input_test_harness()

        # To be able to test we need to start the interface
        await func.start()

        self.assertEqual(func.input_buffer, b'')

        # Now let's test the INPUT
        # Here we're going to simulate a user typing a few things
        # and it should be stored in the input buffer
        func.capture_mode = CaptureMode.INPUT
        await func.receive_from_frontend(b"CHARS")
        await asyncio.sleep(0.1)
        self.assertEqual(func.input_buffer, b'CHARS')

        # Let's hit backspace to remove the last character
        await func.receive_from_frontend(b"\x7f")  # Backspace
        await asyncio.sleep(0.1)
        self.assertEqual(func.input_buffer, b'CHAR')

        # When the user presses Enter, the input buffer should be cleared
        await func.receive_from_frontend(b"\r\n")
        await asyncio.sleep(0.1)
        self.assertEqual(func.input_buffer, b'')

        # Then we can get the input from the queue
        # FIXME: this is where it's currently failing, the input_queue.sync_q is not
        # getting the data as expected and data is == to b''
        data = func.input_queue.sync_q.get()
        self.assertEqual(data, b'CHAR')

        # Let's hit things with the control C
        await func.receive_from_frontend(b"\x03")
        self.assertEqual(func.state, InterfaceState.SHUTDOWN)

    async def test_function_input_capturemode_killqueue(self):
        ##############################################
        # Kill queue midway which does weird things that
        # we need to handle. this only really will happen
        # in a weird sitaution where the interface is shutdown
        # while the function is still running.
        # We will fake it but shutting down the queue
        # directly to simulate this situation.
        ##############################################

        capture_frontend_buffer, func = self.input_test_harness()

        # To be able to test we need to start the interface
        await func.start()

        # Shutdown the interface directly without triggering
        # the normal shutdown coroutine
        await func.shutdown_handle()

        await func.receive_from_frontend(b"CHAR")

    async def test_function_input_crash(self):
        """ Check that we get errors for trying to run code
            that doesn't work when the interface hasn't been started
        """

        # We test what will happen if we try to print something
        # after the interface has been shutdown.
        def func_code(interface: FunctionInterface):
            import time
            time.sleep(1)

        func = FunctionInterface(func_code)

        with self.assertRaises(InterfaceNotStarted):
            await func.receive_from_frontend(b"BEEP\r\n")

    



