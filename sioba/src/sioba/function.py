import threading
import janus
import asyncio
from io import StringIO

from typing import Callable

from .base import Interface, InterfaceState

from .errors import InterfaceNotStarted, InterfaceShutdown

from enum import Enum
import weakref

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
                 default_capture_state: CaptureMode = CaptureMode.ECHO,
                 **kwargs
                 ):
        super().__init__(**kwargs)
        self.function = function

        # For input prompts
        self.input_buffer: bytes = b""
        self.input_is_password = False

        # Send to xterm queue
        self.send_queue: janus.Queue[bytes] = janus.Queue()

        # Incoming input queue
        self.input_queue: janus.Queue[bytes] = janus.Queue()

        self.capture_mode: CaptureMode = default_capture_state
        self.capture_last_state: CaptureMode = self.capture_mode

        self.function_thread: threading.Thread|None = None

        self.main_loop = None  # Will store the main asyncio loop

    async def start_interface(self) -> bool:
        logger.debug("Launching function interface")
        """Launch the wrapped function in a separate thread"""

        # Store the main event loop for later use
        self.main_loop = asyncio.get_running_loop()

        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = InterfaceState.STARTED

        # Create the send queue loop
        logger.debug("Starting send_to_control_loop")
        asyncio.create_task(self.send_to_control_loop())

        # Launch the function
        def _run_function():
            logger.debug(f"Running function {self.function}")
            try:
                res = self.function(weakref.proxy(self))
                #if asyncio.iscoroutine(res):
                #    asyncio.run(res)
            except InterfaceShutdown:
                # This is just a notification that we're shutdown
                # let's just pass through to the end
                pass
            except Exception as e:
                logger.error(f"Error in function: {e=} {type(e)}")
                asyncio.run_coroutine_threadsafe(
                    coro = self.shutdown(),
                    loop = asyncio.get_running_loop(),
                )
            logger.debug(f"Function {self.function} finished")

        self.function_thread = threading.Thread(target=_run_function, daemon=True)
        self.function_thread.start()

        return True

    @logger.catch
    async def shutdown_interface(self) -> None:
        """Shutdown the interface"""
        if self.send_queue:
            await self.send_queue.aclose()
        await super().shutdown()

    @logger.catch
    async def send_to_control_loop(self) -> None:
        while self.state == InterfaceState.STARTED:
            try:
                # Get data from the queue with a timeout to allow checking the state
                data = await self.send_queue.async_q.get()

                # Send data to the terminal using the main event loop
                await self.send_to_control(data)

            except janus.QueueShutDown:
                break

            except asyncio.CancelledError:
                break

            except InterfaceShutdown:
                break

    def print(self, *a, **kw) -> None:
        """Print text to the terminal"""
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted("Unable to print, interface not started")
        if self.state == InterfaceState.SHUTDOWN:
            raise InterfaceShutdown("Unable to print, interface is shut down")

        # Use the python string handling to format the text
        s = StringIO()
        print(*a, **kw, file=s)
        text = s.getvalue()

        # Convert newlines to newline + carriage return for terminal display
        text = text.replace("\n", "\r\n")

        # Put the data in the send queue
        logger.debug(f"Sending to xterm: {text}")
        self.send_queue.sync_q.put(text.encode())

    @logger.catch
    def capture(self, prompt: str, capture_mode: CaptureMode) -> str:
        """Get password input (doesn't echo) from the terminal"""
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted("Unable to get input, interface not started")
        if self.state == InterfaceState.SHUTDOWN:
            raise InterfaceShutdown("Unable to get input, interface is shut down")

        # Clear any previous input
        self.input_buffer = b""
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
    async def receive_from_control(self, data: bytes) -> None:
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted("Interface not ready to receive data")
        if self.state == InterfaceState.SHUTDOWN:
            raise InterfaceShutdown("Interface is shut down")

        try:
            if self.capture_mode == CaptureMode.DISCARD:
                if data == b'\x03':  # Ctrl-C
                    logger.debug("Ctrl-C received, shutting down")
                    await self.shutdown()
                return

            if self.capture_mode == CaptureMode.ECHO:
                if data == b'\r':  # Enter key pressed
                    data = b'\r\n'

                elif data == b'\x03':  # Ctrl-C
                    logger.debug("Ctrl-C received, shutting down")
                    await self.shutdown()

                # If we're not capturing input, just send the data
                await self.send_queue.async_q.put(data)
                return

            # Process based on the input character
            if data == b'\r':  # Enter key pressed
                # Echo a newline

                # Store the result and signal it's ready
                input_result = self.input_buffer
                self.input_buffer = b""
                await self.send_queue.async_q.put(b'\r\n')
                self.input_queue.sync_q.put(input_result)

            elif data == b'\x03':  # Ctrl-C
                # Signal the input is ready
                #self.input_queue.sync_q.put(b'\x03')
                logger.debug("Ctrl-C received, shutting down")
                await self.shutdown()
                self.input_queue.sync_q.put(b"")

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

        except janus.QueueShutDown:
            # No longer need to respond
            pass


