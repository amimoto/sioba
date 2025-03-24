import threading
import queue
import janus
import asyncio
from io import StringIO

from typing import Callable

from .base import Interface, BufferedInterface, INTERFACE_STATE_STARTED, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_SHUTDOWN

from ..errors import InterfaceNotStarted

from enum import Enum

from loguru import logger

class CaptureMode(Enum):
    """ Capture mode is used to determine how the interface
        should handle incoming data. It can be used to capture
        data without echoing it back to the interface.
    """
    DISCARD = 0
    ECHO = 1
    INPUT = 2
    GETPASS = 3

class FunctionInterface(BufferedInterface):
    def __init__(self,
                 function: Callable,
                 on_receive_from_xterm: Callable = None,
                 on_send_to_xterm: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 default_capture_state: CaptureMode = CaptureMode.ECHO,
                 ):
        super().__init__(
            on_receive_from_xterm=on_receive_from_xterm,
            on_send_to_xterm=on_send_to_xterm,
            on_shutdown=on_shutdown,
            on_set_title=on_set_title
        )
        self.function = function

        # For input prompts
        self.input_buffer: bytes = b""
        self.input_ready: asyncio.Event = asyncio.Event()
        self.input_is_password = False

        # Send to xterm queue
        self.send_queue: janus.Queue[bytes] = janus.Queue()

        # Incoming input queue
        self.input_queue: janus.Queue[bytes] = janus.Queue()

        self.capture_mode: CaptureMode = default_capture_state
        self.capture_last_state: CaptureMode = self.capture_mode

        self.function_thread: threading.Thread|None = None

        self.main_loop = None  # Will store the main asyncio loop

    @logger.catch
    async def launch_interface(self) -> bool:
        """Launch the wrapped function in a separate thread"""
        if self.state != INTERFACE_STATE_INITIALIZED:
            return False

        # Store the main event loop for later use
        self.main_loop = asyncio.get_running_loop()

        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = INTERFACE_STATE_STARTED

        # Create the send queue loop
        asyncio.create_task(self.send_to_xterm_loop())

        # Launch the function
        def _run_function():
            res = self.function(self)
            if asyncio.iscoroutine(res):
                asyncio.run(res)
        self.function_thread = threading.Thread(target=_run_function, daemon=True)
        self.function_thread.start()

        return True

    @logger.catch
    async def shutdown(self) -> None:
        """Shutdown the interface"""
        if self.send_queue:
            self.send_queue.aclose()
        super().shutdown()

    @logger.catch
    async def send_to_xterm_loop(self) -> None:
        while self.state == INTERFACE_STATE_STARTED:
            try:
                # Get data from the queue with a timeout to allow checking the state
                data = await self.send_queue.async_q.get()

                # Send data to the terminal using the main event loop
                await self.send_to_xterm(data)

            except asyncio.CancelledError:
                break

    @logger.catch
    def print(self, *a, **kw) -> None:
        """Print text to the terminal"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted("Unable to print, interface not started")
        if self.state == INTERFACE_STATE_SHUTDOWN:
            raise InterfaceNotStarted("Unable to print, interface is shut down")

        # Use the python string handling to format the text
        s = StringIO()
        print(*a, **kw, file=s)
        text = s.getvalue()

        # Convert newlines to newline + carriage return for terminal display
        text = text.replace("\n", "\r\n")

        # Put the data in the send queue
        self.send_queue.sync_q.put(text.encode())

    @logger.catch
    def capture(self, prompt: str, capture_mode: CaptureMode) -> str:
        """Get password input (doesn't echo) from the terminal"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted("Unable to get input, interface not started")
        if self.state == INTERFACE_STATE_SHUTDOWN:
            raise InterfaceNotStarted("Unable to get input, interface is shut down")

        # Clear any previous input
        self.input_buffer = b""
        self.input_ready.clear()
        self.capture_mode = capture_mode

        # Display the prompt
        if prompt:
            self.print(prompt, end="")

        # Wait for input to be ready (the event will be set in receive())
        data = self.input_queue.sync_q.get()

        # Reset the capture mode
        self.capture_mode = self.capture_last_state

        # Return the collected input
        return data.decode()

    @logger.catch
    def input(self, prompt: str="") -> str:
        """Get input from the terminal"""
        return self.capture(prompt, CaptureMode.INPUT)

    @logger.catch
    def getpass(self, prompt:str ="") -> str:
        # Return the collected input
        return self.capture(prompt, CaptureMode.GETPASS)

    @logger.catch
    async def receive_from_xterm(self, data: bytes) -> None:
        if self.capture_mode == CaptureMode.DISCARD:
            return

        if self.capture_mode == CaptureMode.ECHO:
            if data == b'\r':  # Enter key pressed
                data = b'\r\n'

            # If we're not capturing input, just send the data
            print(f"<{data}>")
            await self.send_queue.async_q.put(data)
            return

        # Process based on the input character
        if data == b'\r':  # Enter key pressed
            # Echo a newline

            # Store the result and signal it's ready
            input_result = self.input_buffer
            self.input_buffer = b""
            self.input_ready.set()
            await self.send_queue.async_q.put(b'\r\n')
            self.input_queue.sync_q.put(input_result)


        elif data == b'\x7f' or data == b'\b':  # Backspace
            if self.input_buffer:
                # Remove the last character
                self.input_buffer = self.input_buffer[:-1]

                # Echo the backspace action if in INPUT mode
                if self.capture_mode == CaptureMode.INPUT:
                    await self.send_queue.async_q.put(b'\b \b')
        else:
            # Add the character to the buffer
            self.input_buffer += data

            # Echo the character or * for password
            if self.capture_mode == CaptureMode.INPUT:
                await self.send_queue.async_q.put(data)
