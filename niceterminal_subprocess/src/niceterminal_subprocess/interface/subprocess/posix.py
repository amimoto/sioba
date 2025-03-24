import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios

from typing import Callable

from ..base import Interface, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_STARTED, INTERFACE_STATE_SHUTDOWN
from niceterminal.utils import default_shell

from loguru import logger

class PosixInterface(Interface):
    def __init__(self,
                 invoke_command: str,
                 shutdown_command: str = None,
                 on_send: Callable = None,
                 on_receive: Callable = None,
                 on_shutdown: Callable = None,
                 cwd:str=None,
                 ):
        super().__init__(
            on_send = on_send,
            on_receive = on_receive,
            on_shutdown = on_shutdown,
        )
        self.primary_fd, self.subordinate_fd = pty.openpty()
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

        shell = default_shell()
        invoke_command = self.invoke_command or shell

        self.process = await asyncio.create_subprocess_shell(
            invoke_command,
            preexec_fn=os.setsid,
            stdin=self.subordinate_fd,
            stdout=self.subordinate_fd,
            stderr=self.subordinate_fd,
            cwd=self.cwd,
            executable=shell,
        )
        loop = asyncio.get_running_loop()
        loop.add_reader(self.primary_fd, self._read_loop)
        asyncio.create_task(self._monitor_exit())  # Monitor process exit

        logger.debug(f"Started process {self.process.pid} {self.invoke_command}")
        logger.warning(f"Started process {self.process.pid} {self.invoke_command}")

    @logger.catch
    def _read_loop(self):
        """Callback when data is available to read from the shell."""
        if data := os.read(self.primary_fd, 10240):
            self.receive(data)

    @logger.catch
    async def send(self, data: bytes):
        """Writes data to the shell."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        os.write(self.primary_fd, data)

    @logger.catch
    def set_size(self, rows, cols, xpix=0, ypix=0):
        """Sets the shell window size."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        winsize = struct.pack("HHHH", rows, cols, xpix, ypix)
        fcntl.ioctl(self.subordinate_fd, termios.TIOCSWINSZ, winsize)
        pgrp = os.getpgid(self.process.pid)
        os.killpg(pgrp, signal.SIGWINCH)

    @logger.catch
    async def _monitor_exit(self):
        """Monitors process exit and handles cleanup."""
        await self.process.wait()  # Wait until the process exits
        self.state = INTERFACE_STATE_SHUTDOWN
        await self.shutdown()

    @logger.catch
    def shutdown(self):
        """Shuts down the shell process."""
        logger.info(f"Shutting down process {self.process.pid}")
        if self.state == INTERFACE_STATE_STARTED:
            try:
                self.process.kill()
                pgrp = os.getpgid(self.process.pid)
                os.killpg(pgrp, signal.SIGTERM)
            except ProcessLookupError:
                pass
        loop = asyncio.get_running_loop()
        loop.remove_reader(self.primary_fd)

        async def _shutdown():
            if self.shutdown_command:
                shutdown_process = await asyncio.create_subprocess_shell(
                    self.shutdown_command,
                    preexec_fn=os.setsid,
                    stdin=self.subordinate_fd,
                    stdout=self.subordinate_fd,
                    stderr=self.subordinate_fd,
                    cwd=self.cwd,
                    executable='/bin/bash',
                )
                await shutdown_process.wait()
            self.state = INTERFACE_STATE_SHUTDOWN

            await self.process.wait()

            try:
                os.close(self.primary_fd)
            except OSError:
                pass
            try:
                os.close(self.subordinate_fd)
            except OSError:
                pass

            logger.debug(f"Process {self.process.pid} exited. Calling exit handlers.")
            self.shutdown()

            await super().shutdown()

        loop.run_until_complete(_shutdown())
