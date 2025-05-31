import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios

from typing import Callable

from sioba_interface import PersistentInterface, INTERFACE_STATE_STARTED, INTERFACE_STATE_SHUTDOWN
from sioba_subprocess.utils import default_shell

from loguru import logger

class PosixInterface(PersistentInterface):
    def __init__(self,
                 invoke_command: str,
                 shutdown_command: str = None,
                 cwd:str=None,

                 on_send_to_control: Callable = None,
                 on_receive_from_control: Callable = None,
                 on_shutdown: Callable = None,
                 *args,
                 **kwargs
                 ):
        super().__init__(
            on_send_to_control = on_send_to_control,
            on_receive_from_control = on_receive_from_control,
            on_shutdown = on_shutdown,
            *args,
            **kwargs
        )
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None

    @logger.catch
    async def start_interface(self):
        """Starts the shell process asynchronously."""
        shell = default_shell()
        invoke_command = self.invoke_command or shell

        def _preexec():
            os.setsid()
            # make subordinate_fd the controlling terminal
            fcntl.ioctl(self.subordinate_fd, termios.TIOCSCTTY, 0)

        self.process = await asyncio.create_subprocess_shell(
            invoke_command,
            preexec_fn=_preexec,
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
            asyncio.create_task(self.send_to_control(data))

    @logger.catch
    async def receive_from_control(self, data: bytes):
        """Writes data to the shell."""
        os.write(self.primary_fd, data)
        await super().receive_from_control(data)

    @logger.catch
    def set_terminal_size(self, rows, cols, xpix=0, ypix=0):
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
    async def shutdown_interface(self):
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
