import asyncio
import winpty
import threading
import subprocess

from typing import Callable

from sioba import PersistentInterface, InterfaceState

from loguru import logger

class WindowsInterface(PersistentInterface):
    def __init__(self,
                 invoke_command: str,
                 shutdown_command: str = None,
                 on_receive_from_control: Callable = None,
                 on_shutdown: Callable = None,
                 cwd: str = None,
                 *args,
                 **kwargs
                 ):
        super().__init__(
            on_receive_from_control=on_receive_from_control,
            on_shutdown=on_shutdown,
            *args,
            **kwargs
        )
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None
        self.main_loop = None

    @logger.catch
    async def start_interface(self):
        """Starts the shell process asynchronously."""

        # The console handle is created by winpty and used to interact with the shell
        # Spawn a subprocess connected to the PTY
        self.process = winpty.PTY(
                            cols=self.cols,
                            rows=self.rows,
                        )
        result = self.process.spawn(
                        self.invoke_command,
                        cwd=self.cwd
                    )
        logger.warning(f"Spawn result: {result}")

        # Start a separate thread to read from the console
        self.read_thread = threading.Thread(
                                target=self._read_loop,
                                daemon=True,
                            ).start()
#
        # Start a task to monitor process exit
        #asyncio.create_task(self._on_shutdown_handlers())

    @logger.catch
    def _read_loop(self):
        """Blocking read loop in a separate thread."""
        while self.process.isalive():
            data = self.process.read()
            if data:
                asyncio.run(self.send_to_control(data.encode()))

    @logger.catch
    def set_terminal_size(self, rows: int, cols: int, xpix: int = 0, ypix: int = 0):
        """Sets the shell window size."""
        if self.state != InterfaceState.STARTED:
            return
        super().set_terminal_size(rows=rows, cols=cols)

    @logger.catch
    async def receive_from_control(self, data: bytes):
        """Writes data to the shell."""
        if self.state != InterfaceState.STARTED:
            return
        self.process.write(data.decode())
        await super().receive_from_control(data)

    @logger.catch
    async def shutdown_interface(self) -> None:
        """Shuts down the shell process."""
        try:
            if self.process:
                self.process.terminate()
                self.process = None
        except Exception as e:
            logger.warning(f"Error terminating process: {e}")

    @logger.catch
    async def _on_shutdown_handlers(self):
        """Monitors process exit and handles cleanup."""
        try:
            await asyncio.to_thread(self.process.wait())  # Wait for process exit
            self.state = InterfaceState.SHUTDOWN
            await self.shutdown()
            # self._on_shutdown_handlers()
        except Exception as e:
            logger.warning(f"Error monitoring process exit: {e}")
