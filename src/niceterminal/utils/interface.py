import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios
from typing import Callable

class Interface:
    async def start(self):
        """Starts the shell process asynchronously."""
        pass

    async def write(self, data):
        """Writes data to the shell."""
        pass

    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        pass

    async def shutdown(self):
        """Shuts down the shell process."""
        pass

    def on_read(self, on_read:Callable):
        """Registers a callback for when data is available to read from the shell."""
        pass

    def get_screen_display(self) -> str:
        """Get the current screen contents as a string"""
        return ''

    def get_cursor_position(self) -> tuple:
        return (0, 0)

    def __del__(self):
        pass


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
        self._on_exit = []
        self.state = INTERFACE_STATE_INITIALIZED
        if on_read:
            self._on_read.append(on_read)
        if on_exit:
            self._on_exit.append(on_exit)

    def on_read(self, on_read:Callable):
        if on_read not in self._on_read:
            self._on_read.append(on_read)

    def on_exit(self, on_exit:Callable):
        if on_exit not in self._on_exit:
            self._on_exit.append(on_exit)

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
        for on_exit in self._on_exit:
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

import pyte

class PersistentInterface(Interface):
    """Wraps an InvokeProcess to provide pyte terminal emulation capabilities"""
    def __init__(self,
                 process: Interface,
                 columns: int = 80,
                 lines: int = 24):
        self.process = process

        # Initialize pyte screen and stream
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream(self.screen)

        # Wrap the process's on_read with our pyte handler
        self.process.on_read(self._pyte_handler)

    def _pyte_handler(self, process:Interface, data: bytes):
        """Handler that updates the pyte screen before passing data through"""
        try:
            self.stream.feed(data.decode('utf-8'))
        except UnicodeDecodeError:
            self.stream.feed(data.decode('utf-8', errors='replace'))

    # Delegate all InvokeProcess methods to the wrapped process
    def on_read(self, on_read: Callable):
        """Add a callback for when data is received"""
        self.process.on_read(on_read)

    async def start(self):
        """Starts the shell process asynchronously."""
        await self.process.start()

    async def write(self, data):
        """Writes data to the shell."""
        await self.process.write(data)

    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        self.process.set_size(row, col, xpix, ypix)
        self.screen.resize(lines=row, columns=col)

    async def shutdown(self):
        """Shuts down the shell process."""
        #await self.process.shutdown()
        pass

    # Additional pyte-specific methods
    def get_screen_display(self) -> str:
        """Get the current screen contents as a string"""
        return ''.join(self.screen.display)

    def get_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (self.screen.cursor.x, self.screen.cursor.y)

    def __getattr__(self, name):
        """Delegate any other attributes to the wrapped process"""
        return getattr(self.process, name)