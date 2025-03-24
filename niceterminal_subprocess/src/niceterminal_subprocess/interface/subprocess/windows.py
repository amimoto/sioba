import asyncio
import winpty
import threading
import subprocess

from typing import Callable

from niceterminal.interface import Interface, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_STARTED, INTERFACE_STATE_SHUTDOWN

from loguru import logger

class WindowsInterface(Interface):
    def __init__(self,
                 invoke_command: str,
                 shutdown_command: str = None,
                 on_receive_from_xterm: Callable = None,
                 on_shutdown: Callable = None,
                 cwd: str = None,
                 ):
        super().__init__(
            on_receive_from_xterm=on_receive_from_xterm,
            on_shutdown=on_shutdown)
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None
        self.main_loop = None

    @logger.catch
    async def launch_interface(self):
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
                asyncio.run(self.send_to_xterm(data.encode()))

    @logger.catch
    def set_size(self, rows, cols, xpix=0, ypix=0):
        """Sets the shell window size."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        super().set_size(rows=rows, cols=cols)

    @logger.catch
    async def receive_from_xterm(self, data: bytes):
        """Writes data to the shell."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        self.process.write(data.decode())
        await super().receive_from_xterm(data)

    @logger.catch
    async def shutdown(self):
        """Shuts down the shell process."""
        await super().shutdown()
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
            self.state = INTERFACE_STATE_SHUTDOWN
            await self.shutdown()
            # self._on_shutdown_handlers()
        except Exception as e:
            logger.warning(f"Error monitoring process exit: {e}")
