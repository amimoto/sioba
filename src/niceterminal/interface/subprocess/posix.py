import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios

from typing import Callable

from ..base import Interface

INTERFACE_STATE_INITIALIZED = 0
INTERFACE_STATE_STARTED = 1
INTERFACE_STATE_SHUTDOWN = 2

class PosixInterface(Interface):
    def __init__(self,
                 invoke_command:str,
                 shutdown_command:str=None,
                 on_read:Callable=None,
                 on_exit:Callable=None,
                 cwd:str=None,
                 ):
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None
        self._on_read = []
        self.on_exit_handle = []
        self.state = INTERFACE_STATE_INITIALIZED
        if on_read:
            self._on_read.append(on_read)
        if on_exit:
            self.on_exit_handle.append(on_exit)

    def on_read(self, on_read:Callable):
        if on_read not in self._on_read:
            self._on_read.append(on_read)

    def on_exit(self, on_exit:Callable):
        if on_exit not in self.on_exit_handle:
            self.on_exit_handle.append(on_exit)

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
        loop.add_reader(self.primary_fd, self._on_data_available)
        asyncio.create_task(self._monitor_exit())  # Monitor process exit

    def _on_data_available(self):
        """Callback when data is available to read from the shell."""
        if data := os.read(self.primary_fd, 10240):
            for on_read in self._on_read:
                try:
                    on_read(self, data)
                except OSError as e:
                    print(e)
                    print(dir(e))
        else:
            print(f"NO DATA {self.process.pid} {self.process.returncode} {type(data)}")

    async def write(self, data):
        """Writes data to the shell."""
        if self.state != INTERFACE_STATE_STARTED:
            return
        try:
            os.write(self.primary_fd, data.encode('utf-8'))
        except OSError as e:
            print(e)
            print(dir(e))

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