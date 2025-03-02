import asyncio
import winpty
import threading

from typing import Callable

from ..base import Interface, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_STARTED, INTERFACE_STATE_SHUTDOWN

from loguru import logger

class WindowsInterface(Interface):
    def __init__(self,
                 invoke_command: str,
                 shutdown_command: str = None,
                 on_receive: Callable = None,
                 on_shutdown: Callable = None,
                 cwd: str = None,
                 ):
        super().__init__(on_receive=on_receive, on_shutdown=on_shutdown)
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None

    @logger.catch
    async def launch_interface(self):
        """Starts the shell process asynchronously."""
        if self.state != INTERFACE_STATE_INITIALIZED:
            return
        self.state = INTERFACE_STATE_STARTED

        # The console handle is created by winpty and used to interact with the shell
        self.process = winpty.PTY(80, 24)
        result = self.process.spawn(self.invoke_command, cwd=self.cwd)
        logger.warning(f"Spawn result: {result}")

        # Start a separate thread to read from the console
        self.read_thread = threading.Thread(
                                target=self._read_loop,
                                daemon=True,
                            ).start()

        # Start a task to monitor process exit
        asyncio.create_task(self._on_shutdown_handlers())

    @logger.catch
    def set_size(self, rows, cols, xpix=0, ypix=0):
        """Sets the shell window size."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        self.process.set_size(rows=rows, cols=cols)

    @logger.catch
    def _read_loop(self):
        """Blocking read loop in a separate thread."""
        while self.process.isalive():
            data = self.process.read()
            self.read(data.encode())

    @logger.catch
    async def write(self, data: bytes):
        """Writes data to the shell."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        self.process.write(data.decode())

    @logger.catch
    def shutdown(self):
        """Shuts down the shell process."""
        if self.state == INTERFACE_STATE_STARTED:
            try:
                self.process.terminate()
            except Exception as e:
                logger.warning(f"Error terminating process: {e}")
        self.state = INTERFACE_STATE_SHUTDOWN

    @logger.catch
    async def _on_shutdown_handlers(self):
        """Monitors process exit and handles cleanup."""
        try:
            await asyncio.to_thread(self.con.wait)  # Wait for process exit
            self.state = INTERFACE_STATE_SHUTDOWN
            await self.shutdown()
            self._on_shutdown_handlers()
        except Exception as e:
            logger.wraning(f"Error monitoring process exit: {e}")
