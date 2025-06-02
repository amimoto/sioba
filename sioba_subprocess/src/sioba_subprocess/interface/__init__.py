from typing import Callable

from sioba import register_interface

from loguru import logger

try:
    from .subprocess.posix import PosixInterface as SubprocessInterface
    INVOKE_COMMAND = "/bin/bash"
except ImportError as e:
    try:
        from .subprocess.windows import WindowsInterface as SubprocessInterface
        INVOKE_COMMAND = "cmd.exe"
    except ImportError as e:
        raise ImportError("No suitable subprocess interface found")

@register_interface("exec")
class ShellInterface(SubprocessInterface):
    @logger.catch
    def __init__(
                self,
                invoke_command: str = INVOKE_COMMAND,
                shutdown_command: str = None,

                scrollback_buffer_size: int = 10_000,

                # From superclass
                on_receive_from_control: Callable = None,
                on_send_to_control: Callable = None,
                on_shutdown: Callable = None,
                on_set_terminal_title: Callable = None,
                cols: int = 80,
                rows: int = 24,
                auto_shutdown: bool = True,
 
            ):
        super().__init__(
                invoke_command = invoke_command,
                shutdown_command = shutdown_command,

                scrollback_buffer_size = scrollback_buffer_size,

                # From superclass
                on_receive_from_control = on_receive_from_control,
                on_send_to_control = on_send_to_control,
                on_shutdown = on_shutdown,
                on_set_terminal_title = on_set_terminal_title,
                cols = cols,
                rows = rows,
                auto_shutdown = auto_shutdown,
        )