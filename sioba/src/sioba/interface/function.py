import threading
import janus
import asyncio
import re

from rich.console import Console

from typing import Callable

from .base import Interface, InterfaceState

from ..errors import InterfaceNotStarted, InterfaceShutdown

from enum import Enum
import weakref

from loguru import logger

def get_next_line(data: bytes) -> tuple[bytes, bytes, bytes]:
    """Get the next line from the data, returning the line and the remaining data."""
    splits = re.split(rb"(\r\n|\r|\n\r|\x03|\x08|\x7f)", data, maxsplit=1)
    if len(splits) < 3:
        return data, b'', b''

    next_line, control_character, remainder = splits

    if control_character in (b'\r\n', b'\n\r', b'\r'):
        control_character = b'\n'

    return next_line, control_character, remainder

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

        # Send to frontend queue
        self.send_queue: janus.Queue[bytes] = janus.Queue()

        # Incoming input from frontend queue
        self.input_queue: janus.Queue[bytes] = janus.Queue()

        self.capture_mode: CaptureMode = default_capture_state
        self.capture_last_state: CaptureMode = self.capture_mode

        self.function_thread: threading.Thread|None = None

        self.main_loop = None  # Will store the main asyncio loop

    async def start_interface(self) -> bool:
        """Launch the wrapped function in a separate thread"""
        logger.debug("Launching function interface")

        # Store the main event loop for later use
        self.main_loop = main_loop = asyncio.get_running_loop()

        # Set the state to STARTED immediately so start() won't wait infinitely
        self.state = InterfaceState.STARTED

        # Create the send queue loop
        logger.debug("Starting send_to_frontend_loop")
        asyncio.create_task(self.send_to_frontend_loop())

        # Launch the function
        def _run_function():
            logger.debug(f"Running function {self.function}")
            try:
                res = self.function(weakref.proxy(self))
                #if asyncio.iscoroutine(res):
                #    asyncio.run(res)
            except (InterfaceShutdown, ):
                # This is just a notification that we're shutdown
                # let's just pass through to the end
                pass

            # With any exception, we want to shutdown the interface
            # and clean up the queues
            except Exception as e:
                try:
                    shutdown_future = asyncio.run_coroutine_threadsafe(
                        coro = self.shutdown(),
                        loop = main_loop,
                    )
                    shutdown_future.result()  # Wait for the shutdown to complete
                except RuntimeError as e:
                    pass
                else:
                    logger.debug("Shutdown coroutine scheduled")
            logger.debug(f"Function {self.function} finished")

        self.function_thread = threading.Thread(target=_run_function, daemon=True)
        self.function_thread.start()

        return True

    async def shutdown_handle(self) -> None:
        """Shutdown the interface"""
        if self.send_queue:
            await self.send_queue.aclose()

    async def send_to_frontend_loop(self) -> None:
        while self.state == InterfaceState.STARTED:
            try:
                # Get data from the queue with a timeout to allow checking the state
                data = await self.send_queue.async_q.get()

                # Send data to the terminal using the main event loop
                await self.send_to_frontend(data)

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
        console = Console()
        with console.capture() as capture:
            console.print(*a, **kw)
        text = capture.get()

        # Put the data in the send queue
        try:
            self.send_queue.sync_q.put(text.encode())
        except Exception as ex:
            raise InterfaceShutdown("Interface is shut down, cannot send data")

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

    def input(self, prompt: str="") -> str:
        """Get input from the terminal"""
        return self.capture(prompt, CaptureMode.INPUT)

    def getpass(self, prompt:str ="") -> str:
        # Return the collected input
        return self.capture(prompt, CaptureMode.GETPASS)

    async def receive_from_frontend(self, data: bytes) -> None:
        """ For the function interface, we receive the input from
            the frontend but unless we we're set to ECHO we don't
            send the data back to be displayed. For things like 
            INPUT and GETPASS we will send the data back, we use
            a capture into the self.input_buffer and when we receive
            a newline, throw the data into a self.send_queue. What
            is expected is that there's another async function
            waiting for the input to be ready, which is blocked until
            it receives the data via the self.send_queue
        """
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted("Interface not ready to receive data")
        if self.state == InterfaceState.SHUTDOWN:
            raise InterfaceShutdown("Interface is shut down")

        try:
            next_line, control_character, remainder = get_next_line(data)

            ##############################################
            # DISCARD mode
            ##############################################
            if self.capture_mode == CaptureMode.DISCARD:
                if control_character == b'\x03':  # Ctrl-C
                    logger.debug("Ctrl-C received, shutting down")
                    await self.shutdown()
                return

            ##############################################
            # ECHO mode
            ##############################################
            if self.capture_mode == CaptureMode.ECHO:
                self.input_buffer += next_line

                # If we have a newline, we need to mark it as a finished
                # line of text to enter
                if control_character == b'\n':
                    await self.send_queue.async_q.put(next_line)
                    await self.receive_from_frontend(remainder)  # Process the rest
                    return

                elif control_character == b'\x03':  # Ctrl-C
                    pre_break = data.split(b'\x03', maxsplit=1)[0]
                    await self.send_queue.async_q.put(pre_break)
                    logger.debug("Ctrl-C received, shutting down")
                    await self.shutdown()
                    return

                # If we're not capturing input, just send the data
                await self.send_queue.async_q.put(next_line)
                return

            ##############################################
            # INPUT or GETPASS mode
            ##############################################

            if next_line:
                # Add the character to the buffer
                self.input_buffer += next_line
                if self.capture_mode == CaptureMode.INPUT:
                    await self.send_queue.async_q.put(next_line)

            # Process based on the input character
            if control_character == b'\n':  # Enter key pressed
                # Store the result and signal it's ready
                input_result = self.input_buffer
                self.input_buffer = b""
                await self.send_queue.async_q.put(b'\n')
                self.input_queue.sync_q.put(input_result)

            elif control_character == b'\x03':  # Ctrl-C
                # Signal the input is ready
                #self.input_queue.sync_q.put(b'\x03')
                logger.debug("Ctrl-C received, shutting down")
                await self.shutdown()
                self.input_queue.sync_q.put(b"")

            # backspace or delete key pressed
            elif control_character in (b'\x7f', b'\x08'):
                if self.input_buffer:
                    # Remove the last character
                    self.input_buffer = self.input_buffer[:-1]

                    # Echo the backspace action if in INPUT mode
                    if self.capture_mode == CaptureMode.INPUT:
                        await self.send_queue.async_q.put(b'\b \b')

        except janus.QueueShutDown:
            # No longer need to respond
            pass





