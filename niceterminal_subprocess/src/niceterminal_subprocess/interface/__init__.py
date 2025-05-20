from typing import Callable

from niceterminal_interface import PersistentInterface

from loguru import logger

from typing import Callable

try:
    from .subprocess.posix import PosixInterface as SubprocessInterface
    INVOKE_COMMAND = "/bin/bash"
except ImportError as e:
    try:
        from .subprocess.windows import WindowsInterface as SubprocessInterface
        INVOKE_COMMAND = "cmd.exe"
    except ImportError as e:
        raise ImportError("No suitable subprocess interface found")

class ShellInterface(PersistentInterface, SubprocessInterface):
    pass
    '''
    @logger.catch
    def __init__(
                self,
                invoke_command: str = INVOKE_COMMAND,
                shutdown_command: str = None,
                on_receive_from_control: Callable = None,
                on_shutdown: Callable = None,
                on_set_terminal_title: Callable = None,
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
                        on_receive_from_control=on_receive_from_control,
                        on_shutdown=on_shutdown,
                        on_set_terminal_title=on_set_terminal_title,
                        cols=cols,
                        rows=rows,
                    )
    '''