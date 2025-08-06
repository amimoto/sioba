"""
NiceGUI XTerm Component
======================

This module provides an XTerm.js integration for NiceGUI, allowing for terminal
emulation in web applications. It supports both standalone terminals and shell
interfaces.

Example:
    Basic usage with shell interface:
        >>> from nicegui import ui
        >>> from sioba_nicegui.xterm import ShellXTerm
        >>>
        >>> term = ShellXTerm()
        >>> term.classes("w-full h-full")
        >>> ui.run()

    Advanced usage with custom interface:
        >>> term = XTerm(
        ...     context=TerminalContext(rows=40, cols=100),
        ...     interface=CustomInterface(),
        ...     on_close=lambda t: print("Terminal closed")
        ... )
"""

__all__ = [
    'XTerm',
    'TerminalContext',
    'TerminalState',
    'TerminalMetadata',
]

import json
import asyncio
import base64
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import (
    Optional,
    Callable,
    Set,
    Literal,
    Any,
    Generator
)

from loguru import logger
from nicegui import background_tasks, ui, core
from nicegui.client import Client
from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.awaitable_response import AwaitableResponse

from sioba.errors import (
    TerminalClosedError as TerminalClosedError,
    ClientDeleted as ClientDeleted 
)

@dataclass
class TerminalContext:
    rows: Optional[int] = None
    cols: Optional[int] = None
    term_type: Optional[str] = None
    scrollback: Optional[int] = None
    encoding: Optional[str] = None
    convertEol: Optional[bool] = None

    allowProposedApi: Optional[bool] = None
    allowTransparency: Optional[bool] = None
    altClickMovesCursor: Optional[bool] = None
    cursorBlink: Optional[bool] = None
    cursorInactiveStyle: Optional[
        Literal['outline', 'block', 'bar', 'underline', 'none']
    ] = None
    cursorStyle: Optional[Literal['block', 'underline', 'bar']] = None
    cursorWidth: Optional[int] = None
    customGlyphs: Optional[bool] = None
    disableStdin: Optional[bool] = None
    drawBoldTextInBrightColors: Optional[bool] = None
    fastScrollModifier: Optional[Literal['none', 'alt', 'ctrl', 'shift']] = None
    fastScrollSensitivity: Optional[int] = None
    fontFamily: Optional[str] = None
    fontSize: Optional[int] = None
    fontWeight: Optional[str] = None
    fontWeightBold: Optional[str] = None
    ignoreBracketedPasteMode: Optional[bool] = None
    letterSpacing: Optional[int] = None
    lineHeight: Optional[float] = None
    logLevel: Optional[
        Literal['trace', 'debug', 'info', 'warn', 'error', 'off']
    ] = None
    macOptionClickForcesSelection: Optional[bool] = None
    macOptionIsMeta: Optional[bool] = None
    minimumContrastRatio: Optional[float] = None
    overviewRulerWidth: Optional[int] = None
    rescaleOverlappingGlyphs: Optional[bool] = None
    rightClickSelectsWord: Optional[bool] = None
    screenReaderMode: Optional[bool] = None
    scrollOnUserInput: Optional[bool] = None
    scrollSensitivity: Optional[int] = None
    smoothScrollDuration: Optional[int] = None
    tabStopWidth: Optional[int] = None
    theme: Optional[dict[str, Any]] = None
    windowsMode: Optional[bool] = None
    wordSeparator: Optional[str] = None

    def items(self) -> Generator[tuple[str, Any], None, None]:
        """Return all keys and values."""
        for k, v in asdict(self).items():
            yield (k, v)

    def update(self, options: "TerminalContext") -> None:
        """Update the context with another TerminalContext instance."""
        for k, v in asdict(options).items():
            if v is not None:
                setattr(self, k, v)

    def copy(self) -> "TerminalContext":
        """Return a copy of the context."""
        return TerminalContext(**asdict(self))

CONTEXT_DEFAULTS = TerminalContext(
    rows=24,
    cols=80,
    term_type="xterm-256color",
    scrollback=1000,
    encoding="utf-8",
    convertEol=True,

    allowProposedApi=False,
    altClickMovesCursor=True,
    cursorBlink=False,
    cursorInactiveStyle="outline",
    cursorStyle="block",
    customGlyphs=True,
    disableStdin=False,
    drawBoldTextInBrightColors=True,
    fastScrollModifier="alt",
    fastScrollSensitivity=5,
    fontFamily="monospace",
    fontSize=14,
    fontWeight="normal",
    fontWeightBold="bold",
    ignoreBracketedPasteMode=False,
    logLevel="info",
    macOptionClickForcesSelection=False,
    macOptionIsMeta=False,
    minimumContrastRatio=1,
    rescaleOverlappingGlyphs=False,
    rightClickSelectsWord=False,
    screenReaderMode=False,
    scrollOnUserInput=True,
    scrollSensitivity=1,
    smoothScrollDuration=0,
    tabStopWidth=8,
    theme={},                       # empty dict by default
    windowsMode=False,
    wordSeparator=" \t\n()[]{}',\""
)

class TerminalState(Enum):
    """Possible states of the terminal."""
    INITIALIZING = 'initializing'
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    CLOSED = 'closed'

@dataclass
class TerminalMetadata:
    """ This tracks non-control specific information such as clients connected and
        activity timestamps for the purposes of both session management and potential
        idle culling
    """
    created_at: datetime = field(default_factory=datetime.now)
    connected_clients: Set[str] = field(default_factory=set)
    last_activity: datetime = field(default_factory=datetime.now)


class XTerm(
            ValueElement,
            DisableableElement,
            component = 'xterm.js',
            default_classes = 'sioba-xtermjs',
        ):
    """XTerm.js integration for NiceGUI.

    This class provides a terminal emulator component that can be used in NiceGUI
    applications. It supports both direct usage and integration with various
    terminal interfaces.

    Attributes:
        component: Name of the JavaScript component
        default_classes: Default CSS classes for the terminal
        context: Terminal context settings
        state: Current state of the terminal
        metadata: Terminal session metadata
    """

    context: TerminalContext = None

    def __getattribute__(self, name):
        #print(f"xterm.js: {name}")
        return super().__getattribute__(name)

    def __init__(
        self,
        value: str = '',
        context: Optional[TerminalContext] = None,
        on_change: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs
    ) -> None:
        """
        Initialize the XTerm component.

        Args:
            value: Initial terminal content
            context: Terminal context settings
            on_change: Callback for content changes
            on_close: Callback for terminal closure

            **kwargs: Additional arguments passed to ValueElement
        """
        self.context = CONTEXT_DEFAULTS.copy()
        if context is not None:
            self.context.update(context) if context else None
        self.state = TerminalState.INITIALIZING
        self.metadata = TerminalMetadata()
        self.on_close_callback = on_close

        super().__init__(
            value=value,
            on_value_change=on_change,
           **kwargs
        )

        # Add required JavaScript resources
        self.add_resource(Path(__file__).parent.parent / 'lib' / 'xterm.js')

        # Set up auto-close for non-shared clients (so when it's
        # session based rather than auto-indexed)
        if not self.client.shared:
            background_tasks.create(
                self._auto_close(),
                name='auto-close terminal'
            )

    def write(self, data: bytes) -> None:
        """Write data to the terminal.

        Args:
            data: Raw bytes to write to the terminal

        Raises:
            TypeError: If data is not bytes
            RuntimeError: If terminal is closed
        """
        if self.state == TerminalState.CLOSED:
            raise TerminalClosedError("Cannot write to closed terminal")

        if not isinstance(data, bytes):
            raise TypeError(f"data must be bytes, got {type(data)}")

        if core.loop is None:
            # logger.warning("No event loop available for terminal write")
            return

        if self._deleted:
            raise ClientDeleted()

        try:
            serialized_data = base64.b64encode(data).decode()
            self.run_method("write", serialized_data)
            self.metadata.last_activity = datetime.now()
        except Exception as e:
            logger.error(f"Failed to write to terminal: {e}")
            raise

    def focus(self) -> AwaitableResponse:
        """Focus the terminal."""
        return self.run_method("focus")

    def set_cursor_location(self, row:int, col:int) -> AwaitableResponse:
        self.run_method("setCursorLocation", row, col)

    async def _auto_close(self) -> None:
        """Auto-close handler for terminal cleanup."""
        while self.client.id in Client.instances:
            await asyncio.sleep(1.0)

        self.state = TerminalState.CLOSED
        if self.on_close_callback:
            await self.on_close_callback(self)

        """Synchronize terminal state with frontend."""
        if core.loop is None or not self.interface:
            logger.warning("No event loop available for terminal sync")
            return

        try:
            # Update screen content
            data = self.interface.get_terminal_buffer()
            if isinstance(data, str):
                data = data.encode()

            # Send screen update to frontend
            serialized_data = base64.b64encode(data).decode()
            with self:
                ui.run_javascript(
                    f"runMethod({self.id}, 'refreshScreen', ['{serialized_data}']);"
                )

            # Update cursor position
            if cursor_position := self.interface.get_terminal_cursor_position():
                self.set_cursor_location(*cursor_position)

            # Check if interface is dead
            if self.interface.is_shutdown():
                self.write(b"[Interface Exited]\033[?25l\r\n")
                self.state = TerminalState.DISCONNECTED

        except Exception as e:
            logger.error(f"Failed to sync with frontend: {e}")

    def set_option(self, option, value) -> None:
        if value is None:
            return
        with self:
            json_value = json.dumps(value)
            ui.run_javascript(
                f"runMethod({self.id}, 'setOption', ['{option}', {json_value}]);"
            )

    def sync_context(self) -> None:
        """Synchronize the terminal with the frontend.

        This method updates the terminal's context settings in the
        frontend, such as cursor visibility and other metadata.

        Raises:
            Exception: Logs any errors that occur during synchronization
        """
        if core.loop is None or not self.interface:
            logger.warning("No event loop available for terminal context sync")
            return

        try:
            for k, v in self.context.items():
                self.set_option(k, v)
        except Exception as e:
            logger.error(f"Failed to sync context with frontend: {e}")


