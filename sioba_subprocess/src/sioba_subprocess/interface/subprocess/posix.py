import asyncio
import os
import pty
import signal
import struct
import fcntl
import termios
import threading
import subprocess
import errno

from typing import Callable, Optional

from sioba import Interface, InterfaceState, InterfaceContext
from sioba_subprocess.utils import default_shell

from loguru import logger

READ_BUFFER_SIZE = 4096

class PosixInterface(Interface):
    """
    Threaded PTY subprocess interface for POSIX.

    Concurrency model:
      - subprocess.Popen to launch a child (usually a shell) attached to a PTY.
      - Reader thread reads from master PTY and posts bytes into the asyncio loop.
      - Waiter thread waits for process exit and triggers shutdown.
      - Public methods remain async for compatibility with the Interface base.
    """

    default_context: InterfaceContext = InterfaceContext(
        convertEol=False,
    )

    def __init__(
        self,
        invoke_command: Optional[str],
        invoke_args: Optional[list[str]] = None,
        invoke_cwd: Optional[str] = None,
        on_send_to_frontend: Optional[Callable] = None,
        on_receive_from_frontend: Optional[Callable] = None,
        on_shutdown: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            on_send_to_frontend=on_send_to_frontend,
            on_receive_from_frontend=on_receive_from_frontend,
            on_shutdown=on_shutdown,
            *args,
            **kwargs,
        )
        self.primary_fd, self.subordinate_fd = pty.openpty()
        self._subordinate_file = None
        self.invoke_command = invoke_command
        self.invoke_args = invoke_args or []
        self.invoke_cwd = invoke_cwd
        self.process: Optional[subprocess.Popen] = None

        # threading infrastructure
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._waiter_thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._write_lock = threading.Lock()
        self._shutting_down = False

    @logger.catch
    async def start_interface(self):
        """Starts the shell process using threads for I/O and monitoring."""
        self._loop = asyncio.get_running_loop()

        shell = default_shell()
        invoke_command = self.invoke_command or shell

        def _preexec():
            os.setsid()
            fcntl.ioctl(self.subordinate_fd, termios.TIOCSCTTY, 0)

        # Wrap the slave FD in a file object so Popen can dup it cleanly.
        # closefd=False so we keep the integer FD for ioctl (winsize) later.
        self._subordinate_file = os.fdopen(
            self.subordinate_fd,
            "wb+",
            buffering=0,
            closefd=False
        )

        # Launch the child attached to our PTY slave on stdin/out/err
        popen_args = [ invoke_command, *self.invoke_args ]
        logger.debug(f"Launching subprocess: {popen_args} in cwd={self.invoke_cwd}")
        self.process = subprocess.Popen(
            popen_args,
            #invoke_command,
            #shell=True,
            #executable=shell,
            stdin=self._subordinate_file,
            stdout=self._subordinate_file,
            stderr=self._subordinate_file,
            cwd=self.invoke_cwd,
            preexec_fn=_preexec,
            bufsize=0,
            close_fds=True,
        )

        self._stop_evt.clear()
        self._shutting_down = False

        # Reader thread: pump PTY -> frontend (via the loop)
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name=f"sioba-reader-{self.process.pid}", daemon=True
        )
        self._reader_thread.start()

        # Waiter thread: detect child exit
        self._waiter_thread = threading.Thread(
            target=self._waiter_loop, name=f"sioba-waiter-{self.process.pid}", daemon=True
        )
        self._waiter_thread.start()

        self.state = InterfaceState.STARTED
        logger.debug(f"Started process {self.process.pid} {self.invoke_command}")
        logger.warning(f"Started process {self.process.pid} {self.invoke_command}")

    def _reader_loop(self):
        """Blocking read from master PTY in a background thread."""
        try:
            while not self._stop_evt.is_set():
                try:
                    data = os.read(self.primary_fd, READ_BUFFER_SIZE)
                    if not data:
                        break
                    # Hand bytes back to the asyncio world via coroutine
                    if self._loop and self._loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.send_to_frontend(data),
                            self._loop
                        )
                except InterruptedError:
                    continue
                except OSError as e:
                    # EIO on master when slave closes; EBADF if we closed master
                    if e.errno in (errno.EIO, errno.EBADF):
                        break
                    logger.exception("Reader loop OSError")
                    break
        except Exception:
            logger.exception("Reader loop crashed")
        finally:
            # Nothing else to do; loop ends on shutdown or child exit.
            pass

    def _waiter_loop(self):
        """Wait for the child to exit; trigger shutdown path back on the loop."""
        try:
            if self.process is not None:
                rc = self.process.wait()
                logger.debug(f"Child process {self.process.pid} exited with rc={rc}")
        except Exception:
            logger.exception("Waiter loop crashed")
        finally:
            self._stop_evt.set()
            # If the asyncio loop is alive, schedule the exit handler.
            try:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self._on_process_exit(), self._loop)
            except RuntimeError:
                # Event loop may already be closed; nothing we can do.
                pass

    async def receive_from_frontend_handle(self, data: bytes):
        """Write bytes to the PTY master; keep async signature for Interface."""
        if self.state != InterfaceState.STARTED:
            return
        with self._write_lock:
            os.write(self.primary_fd, data)

    @logger.catch
    def set_terminal_size(self, rows, cols, xpix=0, ypix=0):
        """ Terminal event to adjust the PTY slave size and nudge
            the process group with SIGWINCH.
        """
        if self.state != InterfaceState.STARTED:
            return
        winsize = struct.pack("HHHH", rows, cols, xpix, ypix)
        fcntl.ioctl(self.subordinate_fd, termios.TIOCSWINSZ, winsize)
        try:
            pgrp = os.getpgid(self.process.pid)
            os.killpg(pgrp, signal.SIGWINCH)
            super().set_terminal_size(rows, cols, xpix, ypix)
        except ProcessLookupError:
            # Process already gone; no harm
            pass

    async def _on_process_exit(self):
        """ Called when the child exits on its own. """
        if self._shutting_down:
            return
        self._shutting_down = True
        self.state = InterfaceState.SHUTDOWN
        await self._cleanup()
        await self.shutdown()  # user hook

    @logger.catch
    async def shutdown_interface(self):
        """ Cooperative shutdown; sends signals, waits briefly, then cleans up. """
        if self.process is None or self._shutting_down:
            return
        self._shutting_down = True
        logger.info(f"Shutting down process {self.process.pid}")

        # Try graceful termination of the entire process group
        try:
            pgrp = os.getpgid(self.process.pid)
            os.killpg(pgrp, signal.SIGTERM)
        except ProcessLookupError:
            pass

        # Wait briefly; if still alive, escalate
        try:
            await asyncio.to_thread(self.process.wait, 2.0)  # timeout=2.0s
        except subprocess.TimeoutExpired:
            try:
                pgrp = os.getpgid(self.process.pid)
                os.killpg(pgrp, signal.SIGKILL)
            except ProcessLookupError:
                pass
            # Wait without timeout
            await asyncio.to_thread(self.process.wait)

        await self._cleanup()
        self.state = InterfaceState.SHUTDOWN
        await self.shutdown()  # user hook

    async def _cleanup(self):
        """ Close threads, fds, and reset state. Safe to call multiple times. """
        # Stop reader thread by closing master; it will see EBADF/EIO and exit.
        self._stop_evt.set()
        try:
            try:
                os.close(self.primary_fd)
            except OSError:
                pass

            # Join threads (off the loop)
            if self._reader_thread is not None:
                await asyncio.to_thread(self._reader_thread.join, 1.0)
            if self._waiter_thread is not None:
                await asyncio.to_thread(self._waiter_thread.join, 1.0)

            # Close the slave file wrapper (keeps FD since closefd=False)
            try:
                if self._subordinate_file:
                    self._subordinate_file.close()
            except Exception:
                pass

            # Finally close the slave FD
            try:
                os.close(self.subordinate_fd)
            except OSError:
                pass
        finally:
            self._reader_thread = None
            self._waiter_thread = None
            self._subordinate_file = None
            self.process = None
