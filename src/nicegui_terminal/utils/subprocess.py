import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios

class InvokeProcess:
    def __init__(self,
                 invoke_command,
                 shutdown_command,
                 on_read=None,
                 cwd=None,
                 ):
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self.invoke_command = invoke_command
        self.shutdown_command = shutdown_command
        self.cwd = cwd
        self.process = None
        self.on_read = on_read

    async def start(self):
        """Starts the shell process asynchronously."""
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
        data = os.read(self.primary_fd, 10240)
        if data and self.on_read:
            self.on_read(data)

    async def write(self, data):
        """Writes data to the shell."""
        os.write(self.primary_fd, data.encode('utf-8'))

    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(self.subordinate_fd, termios.TIOCSWINSZ, winsize)
        pgrp = os.getpgid(self.process.pid)
        os.killpg(pgrp, signal.SIGWINCH)

    async def shutdown(self):
        """Shuts down the shell process."""
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
