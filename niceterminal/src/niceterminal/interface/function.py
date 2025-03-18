import concurrent.futures
import threading
import queue
import asyncio
from io import StringIO

from typing import Callable

from .base import Interface, INTERFACE_STATE_STARTED, INTERFACE_STATE_INITIALIZED
from .persistent import PersistenceMixin

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

class FunctionInterface(Interface):
    def __init__(self,
                 function: Callable,
                 on_receive: Callable = None,
                 on_send: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 default_capture_state: CaptureMode = CaptureMode.ECHO,
                 ):
        super().__init__(
            on_receive=on_receive,
            on_send=on_send,
            on_shutdown=on_shutdown,
            on_set_title=on_set_title
        )
        self.function = function
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        self.input_buffer = b""
        self.input_ready = threading.Event()
        self.input_result = None
        self.input_is_password = False

        self.capture_mode = default_capture_state
        self.capture_last_state = self.capture_mode

        self.main_loop = None  # Will store the main asyncio loop
        self.send_queue = queue.Queue()  # Thread-safe queue for send operations
        self.send_thread = None

    async def launch_interface(self):
        """Launch the wrapped function in a separate thread"""
        if self.state != INTERFACE_STATE_INITIALIZED:
            return

        # Store the main event loop for later use
        self.main_loop = asyncio.get_running_loop()

        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = INTERFACE_STATE_STARTED

        # Create and start the send thread
        self.send_thread = threading.Thread(target=self._process_send_queue, daemon=True)
        self.send_thread.start()

        # Run the wrapped function in a separate thread
        self.executor.submit(self._run_function)

        return True

    def _process_send_queue(self):
        """Process data from the send queue and send it to the terminal"""
        while self.state == INTERFACE_STATE_STARTED:
            try:
                # Get data from the queue with a timeout to allow checking the state
                data = self.send_queue.get(timeout=0.1)

                # Send data to the terminal using the main event loop
                if self.main_loop and data:
                    future = asyncio.run_coroutine_threadsafe(
                        self.send(data),
                        self.main_loop
                    )
                    # Wait for the send to complete
                    future.result()

                self.send_queue.task_done()
            except queue.Empty:
                # Queue is empty, just continue the loop
                continue
            except Exception as e:
                # Print and continue if there's an error
                logger.error(f"Error in send thread: {e=}")

    def _run_function(self):
        """Run the wrapped function in the executor thread"""
        try:
            # Execute the wrapped function, passing self as the interface
            self.function(self)
        except Exception as e:
            # Format and encode the error message
            error_msg = f"\r\nError in wrapped function: {str(e)}\r\n"
            logger.error(error_msg)
            # Put the error message in the send queue
            self.send_queue.put(error_msg.encode())
        finally:
            # Shutdown the interface
            if self.main_loop:
                asyncio.run_coroutine_threadsafe(self._async_shutdown(), self.main_loop)

    async def _async_shutdown(self):
        """Shutdown the interface asynchronously"""
        self.shutdown()

    def print(self, *a, **kw):
        """Print text to the terminal"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted("Unable to print, interface not started")

        # Use the python string handling to format the text
        s = StringIO()
        print(*a, **kw, file=s)
        text = s.getvalue()

        # Convert newlines to newline + carriage return for terminal display
        text = text.replace("\n", "\r\n")

        # Put the data in the send queue
        self.send_queue.put(text.encode())

    def input(self, prompt: str="") -> str:
        """Get input from the terminal"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted("Unable to get input, interface not started")

        # Clear any previous input
        self.input_buffer = b""
        self.input_ready.clear()
        self.capture_mode = CaptureMode.INPUT

        # Display the prompt
        if prompt:
            self.print(prompt, end="")

        # Wait for input to be ready (the event will be set in receive())
        self.input_ready.wait()

        # Reset the capture mode
        self.capture_mode = self.capture_last_state

        # Return the collected input
        return self.input_result.decode()

    def getpass(self, prompt=""):
        """Get password input (doesn't echo) from the terminal"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted("Unable to get password, interface not started")

        # Clear any previous input
        self.input_buffer = b""
        self.input_ready.clear()
        self.capture_mode = CaptureMode.GETPASS

        self.input_is_password = True

        # Display the prompt
        if prompt:
            self.print(prompt, end="")

        # Wait for input to be ready (the event will be set in receive())
        self.input_ready.wait()

        # Reset the capture mode
        self.capture_mode = self.capture_last_state

        # Return the collected input
        return self.input_result.decode()

    async def capture(self, data: bytes) -> bytes:

        # Process based on the input character
        if data == b'\r':  # Enter key pressed
            # Echo a newline

            # Store the result and signal it's ready
            self.input_result = self.input_buffer
            self.input_buffer = b""
            self.input_ready.set()

            return b'\r\n'

        elif data == b'\x7f' or data == b'\b':  # Backspace
            if self.input_buffer:
                # Remove the last character
                self.input_buffer = self.input_buffer[:-1]

                # Echo the backspace action if in INPUT mode
                if self.capture_mode == CaptureMode.INPUT:
                    return b'\b \b'
        else:
            # Add the character to the buffer
            self.input_buffer += data

            # Echo the character or * for password
            if self.capture_mode == CaptureMode.INPUT:
                return data

        return b""

    async def receive(self, data: bytes) -> None:
        """Handle received data from the terminal"""

        if not data:
            return

        # Call parent's receive to trigger callbacks
        for on_receive in self._on_receive_callbacks:
            on_receive(self, data)

        if self.capture_mode == CaptureMode.DISCARD:
            return

        elif self.capture_mode == CaptureMode.ECHO:
            # If we're not capturing input, just send the data
            await self.send(data)
            return

        try:
            if send_data := await self.capture(data):
                await self.send(send_data)
        except Exception as e:
            # Handle any errors during input processing
            logger.warn(f"Error processing input: {e}")
            await self.send(f"\r\nError processing input: {str(e)}\r\n".encode())

class PersistentFunctionInterface(PersistenceMixin, FunctionInterface):
    pass