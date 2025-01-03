from typing import Callable

from ..persistant import PersistentInterface

from loguru import logger

try:
    from .posix import PosixInterface as SubprocessInterface
    INVOKE_COMMAND = "/bin/bash"
except ImportError as e:
    try:
        from .windows import WindowsInterface as SubprocessInterface
        INVOKE_COMMAND = "cmd.exe"
    except ImportError as e:
        raise ImportError("No suitable subprocess interface found")

class ShellInterface(PersistentInterface):
    @logger.catch
    def __init__(
                self,
                invoke_command: str = INVOKE_COMMAND,
                shutdown_command: str = None,
                on_read: Callable = None,
                on_exit: Callable = None,
                on_set_title: Callable = None,
                cwd: str = None,
                cols: int = 80,
                rows: int = 24,
            ):
        super().__init__(
                        SubprocessInterface(
                            invoke_command=invoke_command,
                            shutdown_command=shutdown_command,
                            cwd=cwd
                        ),
                        on_read=on_read,
                        on_exit=on_exit,
                        on_set_title=on_set_title,
                        cols=cols,
                        rows=rows,
                    )
