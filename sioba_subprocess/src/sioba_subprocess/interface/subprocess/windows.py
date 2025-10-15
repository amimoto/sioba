from __future__ import annotations

import asyncio
from logging import warning
import winpty
import threading
import sys

from typing import Callable, Optional

from sioba import Interface, InterfaceState, InterfaceContext

from loguru import logger

class WindowsInterface(Interface):

    default_context: InterfaceContext = InterfaceContext(
        convertEol=True,
    )

    def __init__(self,
                 invoke_command: str,
                 invoke_args: Optional[list[str]] = None,
                 invoke_cwd: Optional[str] = None,
                 on_receive_from_frontend: Callable = None,
                 on_shutdown: Callable = None,
                 cwd: str = None,
                 *args,
                 **kwargs
                 ):
        super().__init__(
            on_receive_from_frontend=on_receive_from_frontend,
            on_shutdown=on_shutdown,
            *args,
            **kwargs
        )

        if sys.platform == "win32":
            if invoke_command.startswith('/'):
                invoke_command = invoke_command[1:]

        self.invoke_command = invoke_command
        self.invoke_args = invoke_args or []
        self.invoke_cwd = invoke_cwd
        self.process = None
        self.main_loop = asyncio.get_event_loop()
        self.on_receive_from_frontend(self._receive_from_frontend)

    async def start_interface(self):
        """Starts the shell process asynchronously."""

        # The console handle is created by winpty and used to interact with the shell
        # Spawn a subprocess connected to the PTY
        self.process = winpty.PTY(
                            cols=self.context.cols,
                            rows=self.context.rows,
                        )
        cmdline = " ".join(self.invoke_args)
        result = self.process.spawn(
                        appname=self.invoke_command,
                        cmdline=cmdline,
                        cwd=self.invoke_cwd,
                    )
        logger.debug(f"Spawn result: {result}")

        # Start a separate thread to read from the console
        self.read_thread = threading.Thread(
                                target=self._read_loop,
                                daemon=True,
                            ).start()
#
        # Start a task to monitor process exit
        asyncio.create_task(self._on_shutdown_handlers())

    def _read_loop(self):
        """Blocking read loop in a separate thread."""
        try:
            while self.process.isalive():
                try:
                    data = self.process.read()
                except Exception as e:
                    logger.warning(f"PTY read error: {e}")
                    break
                if data:
                    asyncio.run(self.send_to_frontend(data.encode()))
        finally:
            # PTY/process ended or read failed: trigger shutdown exactly once
            if self.main_loop and not self.main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.shutdown(),
                    self.main_loop
                )

    def set_terminal_size(self, rows: int, cols: int, xpix: int = 0, ypix: int = 0):
        """Sets the shell window size."""
        if self.state != InterfaceState.STARTED:
            return
        if self.process:
            self.process.set_size(cols=cols, rows=rows)
        super().set_terminal_size(rows=rows, cols=cols)

    @staticmethod
    async def _receive_from_frontend(self, data: bytes):
        """Writes data to the shell."""
        if self.state != InterfaceState.STARTED:
            return

        # since winpty expects str input, decode bytes to str
        data_decoded = data.decode()

        # Convert LF to CRLF if needed
        data_decoded = data_decoded.replace('\n', '\r\n')
        self.process.write(data_decoded)

    async def shutdown_interface(self) -> None:
        """Shuts down the shell process."""
        try:
            if self.process and self.process.isalive():
                self.process.terminate()
                self.process = None
        except Exception as e:
            logger.warning(f"Error terminating process: {e}")

    async def _on_shutdown_handlers(self):
        """Monitors process exit and handles cleanup."""
        try:
            await asyncio.to_thread(self.process.wait())  # Wait for process exit
            self.state = InterfaceState.SHUTDOWN
            await self.shutdown()
            # self._on_shutdown_handlers()
        except Exception as e:
            logger.warning(f"Error monitoring process exit: {e}")
