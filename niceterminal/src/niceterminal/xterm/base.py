"""
NiceGUI XTerm Component
======================

This module provides an XTerm.js integration for NiceGUI, allowing for terminal
emulation in web applications. It supports both standalone terminals and shell
interfaces.

Example:
    Basic usage with shell interface:
        >>> from nicegui import ui
        >>> from niceterminal.xterm import ShellXTerm
        >>>
        >>> term = ShellXTerm()
        >>> term.classes("w-full h-full")
        >>> ui.run()

    Advanced usage with custom interface:
        >>> term = XTerm(
        ...     config=TerminalConfig(rows=40, cols=100),
        ...     interface=CustomInterface(),
        ...     on_close=lambda t: print("Terminal closed")
        ... )
"""

import asyncio
import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Set, Literal, Dict, Any

from loguru import logger
from nicegui import background_tasks, ui, core
from nicegui.client import Client
from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.awaitable_response import AwaitableResponse

from ..errors import TerminalClosedError, ClientDeleted

@dataclass
class TerminalConfig:
    """Configuration settings for XTerm terminal.

    Attributes:
        rows (int): Number of rows in the terminal.
        cols (int): Number of columns in the terminal.
        term_type (str): Terminal type (default: 'xterm-256color').
        scrollback (int): Number of lines retained when scrolling.
        encoding (str): Character encoding for terminal I/O.
        convertEol (bool): Convert new lines to CRLF.
        allowProposedApi (bool): Allow experimental APIs.
        allowTransparency (Optional[bool]): Enable transparent background.
        altClickMovesCursor (bool): Move cursor with Alt+Click.
        cursorBlink (bool): Cursor blinking enabled.
        cursorInactiveStyle (Optional[Literal['outline', 'block', 'bar', 'underline', 'none']]): Cursor style when inactive.
        cursorStyle (Literal['block', 'underline', 'bar']): Active cursor style.
        cursorWidth (Optional[int]): Cursor width in pixels.
        customGlyphs (bool): Use custom glyphs for special characters.
        disableStdin (bool): Disable standard input.
        drawBoldTextInBrightColors (bool): Render bold text in bright colors.
        fastScrollModifier (Optional[Literal['none', 'alt', 'ctrl', 'shift']]): Modifier key for fast scrolling.
        fastScrollSensitivity (Optional[int]): Speed multiplier for fast scrolling.
        fontFamily (str): Font family for rendering text.
        fontSize (int): Font size for terminal text.
        fontWeight (Optional[str]): Font weight for regular text.
        fontWeightBold (Optional[str]): Font weight for bold text.
        ignoreBracketedPasteMode (bool): Ignore bracketed paste sequences.
        letterSpacing (Optional[int]): Spacing between characters.
        lineHeight (Optional[float]): Line height for terminal text.
        logLevel (Literal['trace', 'debug', 'info', 'warn', 'error', 'off']): Logging verbosity level.
        macOptionClickForcesSelection (bool): Force selection on macOS option-click.
        macOptionIsMeta (bool): Treat macOS option as meta key.
        minimumContrastRatio (Optional[float]): Minimum contrast ratio for accessibility.
        overviewRulerWidth (Optional[int]): Width of overview ruler in pixels.
        rescaleOverlappingGlyphs (bool): Rescale glyphs to prevent overlap.
        rightClickSelectsWord (bool): Select word on right-click.
        screenReaderMode (bool): Enable support for screen readers.
        scrollOnUserInput (bool): Scroll to bottom on user input.
        scrollSensitivity (Optional[int]): Sensitivity for scrolling.
        smoothScrollDuration (Optional[int]): Duration for smooth scrolling (ms).
        tabStopWidth (int): Number of spaces per tab stop.
        theme (Optional[Dict[str, Any]]): Terminal color theme.
        windowsMode (bool): Enable Windows-specific mode adjustments.
        wordSeparator (str): Characters used as word separators.
    """

    rows: int = 24
    cols: int = 80
    term_type: str = 'xterm-256color'
    scrollback: int = 1000
    encoding: str = 'utf-8'
    convertEol: bool = True

    allowProposedApi: bool = False
    allowTransparency: Optional[bool] = None
    altClickMovesCursor: bool = True
    cursorBlink: bool = False
    cursorInactiveStyle: Optional[Literal['outline', 'block', 'bar', 'underline', 'none']] = 'outline'
    cursorStyle: Literal['block', 'underline', 'bar'] = 'block'
    cursorWidth: Optional[int] = None
    customGlyphs: bool = True
    disableStdin: bool = False
    drawBoldTextInBrightColors: bool = True
    fastScrollModifier: Optional[Literal['none', 'alt', 'ctrl', 'shift']] = 'alt'
    fastScrollSensitivity: Optional[int] = 5
    fontFamily: str = 'monospace'
    fontSize: int = 14
    fontWeight: Optional[str] = 'normal'
    fontWeightBold: Optional[str] = 'bold'
    ignoreBracketedPasteMode: bool = False
    letterSpacing: Optional[int] = None
    lineHeight: Optional[float] = None
    logLevel: Literal['trace', 'debug', 'info', 'warn', 'error', 'off'] = 'info'
    macOptionClickForcesSelection: bool = False
    macOptionIsMeta: bool = False
    minimumContrastRatio: Optional[float] = 1
    overviewRulerWidth: Optional[int] = None
    rescaleOverlappingGlyphs: bool = False
    rightClickSelectsWord: bool = False
    screenReaderMode: bool = False
    scrollOnUserInput: bool = True
    scrollSensitivity: Optional[int] = 1
    smoothScrollDuration: Optional[int] = 0
    tabStopWidth: int = 8
    theme: Optional[Dict[str, Any]] = field(default_factory=dict)
    windowsMode: bool = False
    wordSeparator: str = " \t\n()[]{}',\""

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass instance to dictionary for use with xterm.js."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


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
            default_classes = 'niceterminal-xtermjs',
        ):
    """XTerm.js integration for NiceGUI.

    This class provides a terminal emulator component that can be used in NiceGUI
    applications. It supports both direct usage and integration with various
    terminal interfaces.

    Attributes:
        component: Name of the JavaScript component
        default_classes: Default CSS classes for the terminal
        config: Terminal configuration settings
        state: Current state of the terminal
        metadata: Terminal session metadata
    """

    def __getattribute__(self, name):
        #print(f"xterm.js: {name}")
        return super().__getattribute__(name)

    def __init__(
        self,
        config: Optional[TerminalConfig] = None,
        value: str = '',
        on_change: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
        **kwargs
    ) -> None:
        """Initialize the XTerm component.

        Args:
            config: Terminal configuration settings
            value: Initial terminal content
            on_change: Callback for content changes
            on_close: Callback for terminal closure
            **kwargs: Additional arguments passed to ValueElement
        """
        self.config = config or TerminalConfig()
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
        if core.loop is None or not self._interface:
            logger.warning("No event loop available for terminal sync")
            return

        try:
            # Update screen content
            data = self._interface.get_terminal_buffer()
            if isinstance(data, str):
                data = data.encode()

            # Send screen update to frontend
            serialized_data = base64.b64encode(data).decode()
            with self:
                ui.run_javascript(
                    f"runMethod({self.id}, 'refreshScreen', ['{serialized_data}']);"
                )

            # Update cursor position
            if cursor_position := self._interface.get_terminal_cursor_position():
                self.set_cursor_location(*cursor_position)

            # Check if interface is dead
            if self._interface.is_shutdown():
                self.write(b"[Interface Exited]\033[?25l\n\r")
                self.state = TerminalState.DISCONNECTED

        except Exception as e:
            logger.error(f"Failed to sync with frontend: {e}")
