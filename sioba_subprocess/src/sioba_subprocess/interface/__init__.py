from typing import Callable, Optional

from sioba import register_scheme, InterfaceContext

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

@register_scheme("exec")
class ShellInterface(SubprocessInterface):
    @logger.catch
    def __init__(
                self,
                invoke_command: str = INVOKE_COMMAND,
                shutdown_command: str = None,

                scrollback_buffer_size: int = 10_000,

                # From superclass
                on_receive_from_frontend: Callable = None,
                on_send_to_frontend: Callable = None,
                on_shutdown: Callable = None,
                on_set_terminal_title: Callable = None,
                cols: int = 80,
                rows: int = 24,
                auto_shutdown: bool = True,
                context: Optional[InterfaceContext] = None,
 
            ):
        if context is None:
            context = InterfaceContext()
        super().__init__(
                invoke_command = invoke_command,
                shutdown_command = shutdown_command,

                scrollback_buffer_size = scrollback_buffer_size,

                # From superclass
                on_receive_from_frontend = on_receive_from_frontend,
                on_send_to_frontend = on_send_to_frontend,
                on_shutdown = on_shutdown,
                on_set_terminal_title = on_set_terminal_title,
                cols = cols,
                rows = rows,
                auto_shutdown = auto_shutdown,
        )