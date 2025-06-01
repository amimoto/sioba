from sioba_nicegui.xterm import XTerm, TerminalConfig
from sioba_subprocess.interface import ShellInterface, INVOKE_COMMAND
from typing import Callable, Optional
"""
Example:
    Basic usage with shell interface:
        >>> from nicegui import ui
        >>> from sioba_nicegui.xterm import ShellXTerm
        >>>
        >>> term = ShellXTerm()
        >>> term.classes("w-full h-full")
        >>> ui.run()

"""

class ShellXTerm(XTerm):
    """A convenient XTerm subclass preconfigured for shell interaction.

    This class provides a simpler interface for creating terminal instances
    that connect to a shell process.
    """

    def __init__(
        self,
        invoke_command: str = INVOKE_COMMAND,
        shutdown_command: str = None,
        cwd: str = None,
        on_receive_from_control: Optional[Callable] = None,
        on_shutdown: Optional[Callable] = None,
        config: Optional[TerminalConfig] = None,
        **kwargs
    ) -> None:
        """Initialize a shell-connected terminal.

        Args:
            invoke_command: Command to launch the shell
            shutdown_command: Command to shut down the shell
            cwd: Working directory for the shell
            on_receive: Callback for data read from shell
            on_shutdown: Callback for shell exit
            config: Terminal configuration
            **kwargs: Additional arguments passed to XTerm
        """
        config = config or TerminalConfig()

        interface = ShellInterface(
            invoke_command=invoke_command,
            shutdown_command=shutdown_command,
            cwd=cwd,
            on_receive_from_control=on_receive_from_control,
            on_shutdown=on_shutdown,
            rows=config.rows,
            cols=config.cols,
        ).start()

        super().__init__(
            interface=interface,
            config=config,
            **kwargs
        )