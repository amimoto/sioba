import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios

from typing import Callable

from ..base import Interface, INTERFACE_STATE_INITIALIZED, INTERFACE_STATE_STARTED, INTERFACE_STATE_SHUTDOWN

from loguru import logger

class PosixInterface(Interface):
    def __init__(self,
                 invoke_command:str,
                 shutdown_command:str=None,
                 on_read:Callable=None,
                 on_exit:Callable=None,
                 cwd:str=None,
                 ):
        super().__init__(on_read, on_exit)
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None

    @logger.catch
    async def start(self):
        """Starts the shell process asynchronously."""
        if self.state != INTERFACE_STATE_INITIALIZED:
            return
        self.state = INTERFACE_STATE_STARTED
        self.process = await asyncio.create_subprocess_shell(
            self.invoke_command,
            preexec_fn=os.setsid,
            stdin=self.subordinate_fd,
            stdout=self.subordinate_fd,
            stderr=self.subordinate_fd,
            cwd=self.cwd,
            executable='/bin/bash',
        )
        loop = asyncio.get_running_loop()
        loop.add_reader(self.primary_fd, self._read_loop)
        asyncio.create_task(self._monitor_exit())  # Monitor process exit

    @logger.catch
    def _read_loop(self):
        """Callback when data is available to read from the shell."""
        if data := os.read(self.primary_fd, 10240):
            self.on_read_handle(data)
        else:
            print(f"NO DATA {self.process.pid} {self.process.returncode} {type(data)}")

    @logger.catch
    async def write(self, data):
        """Writes data to the shell."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        os.write(self.primary_fd, data.encode('utf-8'))

    @logger.catch
    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(self.subordinate_fd, termios.TIOCSWINSZ, winsize)
        pgrp = os.getpgid(self.process.pid)
        os.killpg(pgrp, signal.SIGWINCH)

    async def _monitor_exit(self):
        """Monitors process exit and handles cleanup."""
        await self.process.wait()  # Wait until the process exits
        self.state = INTERFACE_STATE_SHUTDOWN
        await self.shutdown()
        for on_exit in self.on_exit_handle:
            on_exit(self)

    async def shutdown(self):
        """Shuts down the shell process."""
        if self.state == INTERFACE_STATE_STARTED:
            try:
                self.process.kill()
                pgrp = os.getpgid(self.process.pid)
                os.killpg(pgrp, signal.SIGTERM)
            except ProcessLookupError:
                pass
        loop = asyncio.get_running_loop()
        loop.remove_reader(self.primary_fd)
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
        os.close(self.primary_fd)
        os.close(self.subordinate_fd)