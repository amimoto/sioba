from typing import Callable, Optional

from sioba import register_scheme, InterfaceContext, DefaultValuesContext

from loguru import logger

from dataclasses import field, dataclass

try:
    from .subprocess.posix import PosixInterface as SubprocessInterface
    INVOKE_COMMAND = "/bin/bash"
except ImportError as e:
    try:
        from .subprocess.windows import WindowsInterface as SubprocessInterface
        INVOKE_COMMAND = "cmd.exe"
    except ImportError as e:
        raise ImportError("No suitable subprocess interface found")

@dataclass
class ShellContext(DefaultValuesContext):
    invoke_args: list[str] = field(default_factory=list)
    invoke_cwd: Optional[str] = None

@register_scheme("exec", context_class=ShellContext)
class ShellInterface(SubprocessInterface):
    def __init__(
                self,
                invoke_command: str = "",
                invoke_args: Optional[list[str]] = None,
                invoke_cwd: Optional[str] = None,

                scrollback_buffer_size: int = 10_000,

                # From superclass
                on_receive_from_frontend: Optional[Callable] = None,
                on_send_to_frontend: Optional[Callable] = None,
                on_shutdown: Optional[Callable] = None,
                on_set_terminal_title: Optional[Callable] = None,
                context: Optional[ShellContext] = None,
            ):

        if context is None:
            context = self.context_class()

        if not invoke_command:
            invoke_command = context.path or INVOKE_COMMAND

        if not invoke_args:
            invoke_args = context.query.get("arg", [])

        if not invoke_cwd:
            invoke_cwd = (
                context.invoke_cwd
                or context.query.get("invoke_cwd", None)
            )

        super().__init__(
                invoke_command = invoke_command,
                invoke_args = invoke_args,
                invoke_cwd = invoke_cwd,

                context = context,

                scrollback_buffer_size = scrollback_buffer_size,

                # From superclass
                on_receive_from_frontend = on_receive_from_frontend,
                on_send_to_frontend = on_send_to_frontend,
                on_shutdown = on_shutdown,
                on_set_terminal_title = on_set_terminal_title,
        )

        if not self.context:
            self.context = context
