from unittest import IsolatedAsyncioTestCase
from sioba import InterfaceContext, Interface
from sioba.interface.base import InterfaceState
import asyncio
import rich.console
import rich
from utils.terminal import strip_terminal_escapes

class TestInterfaceBase(IsolatedAsyncioTestCase):

    async def test_interface(self):
        # Test if we can create an InterfaceContext without errors
        context = InterfaceContext(
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            scrollback_buffer_uri="terminal://",
            title="Test Interface"
        )

        interface = Interface(context=context)
        self.assertIsInstance(interface, Interface)

        # Setup the capture for the print statements
        received_data = []
        def receive_callback(interface, data):
            received_data.append(data)
        interface.on_receive_from_frontend(receive_callback)

        # Setup the interface for the control
        send_data = []
        def send_callback(interface, data):
            send_data.append(data)
        interface.on_send_to_frontend(send_callback)

        #  We're initialized in this state but not running
        self.assertEqual(interface.state, InterfaceState.INITIALIZED)

        # Interface must be started
        await interface.start()
        await asyncio.sleep(0.1)
        self.assertEqual(interface.state, InterfaceState.STARTED)

        # Now let's inject some events
        await interface.receive_from_frontend(b"Hello, World!")

        # Small delay in case asyncio needs to catch up
        await asyncio.sleep(0.1)

        # Check if the data was received correctly
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0], b"Hello, World!")

        # Let's now send some data to the control
        self.assertEqual(len(send_data), 0)  # No data sent yet

        await interface.send_to_frontend(b"CONTROL DATA!")
        await asyncio.sleep(0.1)  # Allow time for the send to process

        # Check if the data was sent correctly
        self.assertEqual(len(send_data), 1)
        self.assertEqual(send_data[0], b"CONTROL DATA!")

        # Set the terminal title change callback
        terminal_titles = []
        def title_callback(interface, title):
            terminal_titles.append(title)
        interface.on_set_terminal_title(title_callback)

        # Change the terminal title
        self.assertEqual(interface.context.title, "Test Interface")
        interface.set_terminal_title("New Title")
        self.assertEqual(interface.context.title, "New Title")

        # Check if the title callback was called
        self.assertEqual(len(terminal_titles), 1)
        self.assertEqual(terminal_titles[0], "New Title")

        # Check the screen state
        buffer = interface.get_terminal_buffer()
        self.assertIsNotNone(buffer)
        self.assertIn(b"CONTROL DATA!", buffer)

        # Let's make a really long string to test widths
        full_width_string = b"0123456789" * 8
        await interface.send_to_frontend(b"\r\n" + full_width_string)
        await asyncio.sleep(0.1)  # Allow time for the send to process
        buffer = interface.get_terminal_buffer()
        self.assertIn(full_width_string, buffer)

        # Let's now change the size of the interface. This informs the underlying
        # screen state cache that we have a new terminal size. We don't have a
        # formal mechanism to push up the size of the terminal to the frontend
        interface.update_terminal_metadata({
            "rows": 10,
            "cols": 20,
        })
        buffer = interface.get_terminal_buffer()

        # Print some text into the buffer
        long_string = b"\n\rabcdefghijklmnopqrstuvwxyz"
        await interface.send_to_frontend(long_string)
        await asyncio.sleep(0.1)  # Allow time for the send to process
        buffer = interface.get_terminal_buffer()

        # Text should wrap
        self.assertNotIn(long_string, buffer)
        self.assertIn(b"abcdefghijklmnopqrst", buffer)

        # Cursor position should be checked too
        y, x = interface.get_terminal_cursor_position()
        await interface.send_to_frontend(b"XXX")
        y, x = interface.get_terminal_cursor_position()
        self.assertEqual(y, 2)
        self.assertEqual(x, 9)

        # What happens if we send it a new line?
        await interface.send_to_frontend(b"\r\n")
        y, x = interface.get_terminal_cursor_position()
        self.assertEqual(y, 3)
        self.assertEqual(x, 0)

        # Let's see some metadata
        metadata = interface.get_terminal_metadata()

        for i in range(10):
            await interface.send_to_frontend(b"\r\n")

        # State checks
        self.assertTrue(interface.is_running())
        self.assertFalse(interface.is_shutdown())

        # Check if the interface can be stopped
        await interface.shutdown()
        self.assertEqual(interface.state, InterfaceState.SHUTDOWN)

        # Check if the interface is stopped
        self.assertTrue(interface.is_shutdown())
        self.assertFalse(interface.is_running())

    async def test_send_frontend_disconnected_states(self):
        """ Test sending data when the frontend is not connected """
        interface = Interface(context=InterfaceContext())
        self.assertIsInstance(interface, Interface)

    async def test_shutdown_interface(self):
        # Test if we can create an InterfaceContext without errors
        config = InterfaceContext(
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            title="Test Interface"
        )

        interface = Interface(context=config)
        self.assertIsInstance(interface, Interface)

        # Hook the shutdown callback
        shutdown_events = []
        async def shutdown_callback(interface: Interface):
            shutdown_events.append(True)
        interface.on_shutdown(shutdown_callback)

        # Interface must be started
        await interface.start()
        await asyncio.sleep(0.1)
        self.assertEqual(interface.state, InterfaceState.STARTED)

        # Let's use the reference counter
        interface.reference_increment()

        # State checks
        self.assertTrue(interface.is_running())
        self.assertFalse(interface.is_shutdown())
        self.assertFalse(shutdown_events)

        # Decrement the reference count which should also trigger the shutdown
        interface.reference_decrement()

        # Check if the interface can be stopped
        await asyncio.sleep(0.1)

        # Check if the interface is stopped
        self.assertTrue(interface.is_shutdown())
        self.assertTrue(shutdown_events)
        self.assertFalse(interface.is_running())

    async def test_interface_filehandle(self):
        """ Test the filehandle method of the interface """
        context = InterfaceContext(
            encoding="utf-8",
            convertEol=True,
            auto_shutdown=True,
            scrollback_buffer_uri="terminal://",
            title="Test Interface"
        )

        interface = Interface(context=context)
        self.assertIsInstance(interface, Interface)

        # Start the interface
        await interface.start()
        await asyncio.sleep(0.1)

        # Get the filehandle
        filehandle = interface.filehandle()
        self.assertIsNotNone(filehandle)

        # Write to the filehandle
        written_length = filehandle.write("Hello, Filehandle!")
        self.assertEqual(written_length, len("Hello, Filehandle!"))
        await asyncio.sleep(0.1)

        # Check if the data was sent to the frontend
        buffer = interface.get_terminal_buffer()
        self.assertIn(b"Hello, Filehandle!", buffer)

        # Use the rich.Console as a way of leveraging rich to
        # write to the interface
        console = rich.console.Console(file=filehandle, force_terminal=True)
        console.print("[blue][bold]Hello[/bold][/blue]")
        console.print("[underline]underline[/underline]")
        console.print("[blink]blink[/blink]")
        console.print("[strike]strike-through[/strike]")
        console.print("[reverse]reverse[/reverse]")
        console.print("[italic]italic[/italic]")
        await asyncio.sleep(0.1)

        # Check if the data was sent to the frontend
        buffer = interface.get_terminal_buffer()
        self.assertIn(b"Hello, Filehandle!", buffer)

        console.print("Rich", style="bold white on blue")
        await asyncio.sleep(0.1)

        buffer = interface.get_terminal_buffer()

        # Shutdown the interface
        #print(interface.buffer.screen.dump_screen_state_clean(interface.buffer.screen).decode())


        print(strip_terminal_escapes(
            data=buffer,
            cols=interface.context.cols,
            rows=interface.context.rows,
        ))

        await interface.shutdown()

