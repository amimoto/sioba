import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios
from typing import Callable

class InvokeProcess:
    def __init__(self,
                 invoke_command:str,
                 shutdown_command:str=None,
                 on_read:Callable=None,
                 cwd:str=None,
                 ):
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None
        self._on_read = []
        self._started = False
        if on_read:
            self._on_read.append(on_read)

    def on_read(self, on_read:Callable):
        if on_read not in self._on_read:
            self._on_read.append(on_read)

    async def start(self):
        """Starts the shell process asynchronously."""
        if self._started:
            return
        self._started = True
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

    def _on_data_available(self):
        """Callback when data is available to read from the shell."""
        if data := os.read(self.primary_fd, 10240):
            for on_read in self._on_read:
                try:
                    on_read(data)
                except OSError as e:
                    print(e)
                    print(dir(e))

    async def write(self, data):
        """Writes data to the shell."""
        try:
            os.write(self.primary_fd, data.encode('utf-8'))
        except OSError as e:
            print(e)
            print(dir(e))

    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        if not self.process:
            return
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(self.subordinate_fd, termios.TIOCSWINSZ, winsize)
        pgrp = os.getpgid(self.process.pid)
        os.killpg(pgrp, signal.SIGWINCH)

    async def shutdown(self):
        """Shuts down the shell process."""
        self.process.kill()
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
        else:
            pgrp = os.getpgid(self.process.pid)
            os.killpg(pgrp, signal.SIGTERM)
        await self.process.wait()
        os.close(self.primary_fd)
        os.close(self.subordinate_fd)

    def __del__(self):
        print("BEING DELETED!!!!!")