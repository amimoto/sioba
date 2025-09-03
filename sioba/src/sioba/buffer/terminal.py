from __future__ import annotations

from .base import Buffer, register_buffer
import pyte
from pyte.screens import Cursor
from typing import Any


###########################################################
# Screen Persistence via pytE
###########################################################

class EventsCursor(Cursor):
    """ Custom cursor class to handle cursor events. """

    terminal_buffer: TerminalBuffer

    def __init__(self,
                terminal_buffer: TerminalBuffer,
                *args,
                **kwargs) -> None:
        self.terminal_buffer = terminal_buffer
        super().__init__(*args, **kwargs)

    def __setattr__(self, name: str, value: Any):
        #super().__setattr__(name, value)
        object.__setattr__(self, name, value)
        if name == "x":
            self.terminal_buffer.interface.context.cursor_col = self.x
        elif name == "y":
            self.terminal_buffer.interface.context.cursor_row = self.y

    def __getattribute__(self, name: str):
        """ Override to handle cursor position changes. """
        return super().__getattribute__(name)

class EventsScreen(pyte.Screen):

    terminal_buffer: TerminalBuffer

    scrollback_buffer: list
    scrollback_buffer_size: int

    def __init__(
            self,
            terminal_buffer: TerminalBuffer,
        ) -> None:

        self.scrollback_buffer = []
        self.terminal_buffer = terminal_buffer
        self.context = context = terminal_buffer.interface.context

        super().__init__(
            columns=context.cols,
            lines=context.rows,
        )

    def set_title(self, param: str) -> None:
        """ Override the set_title method to handle terminal title changes.

        This method is called when the terminal title is set. It updates
        the title in the EventsScreen and calls the on_set_terminal_title_handle
        callback if it exists which propagates back to the Interface instance
        to trigger further hooks.
        """
        super().set_title(param)
        self.terminal_buffer.interface.set_terminal_title(title=param)

    def index(self) -> None:
        """
        Move the cursor down one line in the same column. If the
        cursor is at the last line, create a new line at the bottom.
        """
        top, bottom = self.margins or pyte.screens.Margins(0, self.lines - 1)
        if self.cursor.y == bottom:
            # TODO: mark only the lines within margins?
            self.dirty.update(range(self.lines))

            # Save the line going out of scope into the scrollback buffer
            self.scrollback_buffer.append(self.buffer[top])
            while len(self.scrollback_buffer) > self.context.scrollback_buffer_size:
                self.scrollback_buffer.pop(0)

            for y in range(top, bottom):
                self.buffer[y] = self.buffer[y + 1]
            self.buffer.pop(bottom, None)
        else:
            self.cursor_down()

    def dump_screen_state_clean(self, screen: pyte.Screen) -> bytes:
        """ Dumps current screen state to an ANSI file without style management."""
        buf = ""

        # Process scrollback buffer so we can have the history
        # Disable pylance error since pyte.graphics doesn't actually exist during
        # static analysis
        for y, line in enumerate(screen.scrollback_buffer): # type: ignore
            for x, char in line.items():
                buf += char.data
            buf += "\n"

        buf += f"             1         2         3         4         \n"
        buf += f"   01234567890123456789012345678901234567890123456789\n"
        # Process screen contents
        for y in range(screen.lines):
            buf += f"{y:02}|"
            for x in range(screen.columns):
                char = screen.buffer[y][x]
                buf += char.data
            buf += "\n"

        return buf.encode()

    def dump_screen_state(self, screen: pyte.Screen) -> bytes:
        """Dumps current screen state to an ANSI file with efficient style management"""
        buf = "\033[0m"  # Initial reset

        # Track current attributes
        current_state = {
            'bold': False,
            'italics': False,
            'underscore': False,
            'blink': False,
            'reverse': False,
            'strikethrough': False,
            'fg': 'default',
            'bg': 'default'
        }

        def get_attribute_changes(char, current_state):
            """Determine which attributes need to change"""
            needed_attrs = []
            needs_reset = False

            # Check if we need to reset everything
            if (current_state['bold'] and not char.bold or
                current_state['italics'] and not char.italics or
                current_state['underscore'] and not char.underscore or
                current_state['blink'] and not char.blink or
                current_state['reverse'] and not char.reverse or
                current_state['strikethrough'] and not char.strikethrough or
                current_state['fg'] != char.fg or
                current_state['bg'] != char.bg):
                needs_reset = True

            if needs_reset:
                needed_attrs.append('0')
                # Reset our tracking state
                for key in current_state:
                    current_state[key] = False
                current_state['fg'] = 'default'
                current_state['bg'] = 'default'

            # Add needed attributes
            if char.bold and (needs_reset or not current_state['bold']):
                needed_attrs.append('1')
                current_state['bold'] = True

            if char.italics and (needs_reset or not current_state['italics']):
                needed_attrs.append('3')
                current_state['italics'] = True

            if char.underscore and (needs_reset or not current_state['underscore']):
                needed_attrs.append('4')
                current_state['underscore'] = True

            if char.blink and (needs_reset or not current_state['blink']):
                needed_attrs.append('5')
                current_state['blink'] = True

            if char.reverse and (needs_reset or not current_state['reverse']):
                needed_attrs.append('7')
                current_state['reverse'] = True

            if char.strikethrough and (needs_reset or not current_state['strikethrough']):
                needed_attrs.append('9')
                current_state['strikethrough'] = True

            # Handle colors only if they've changed
            if char.fg != current_state['fg']:
                # Disable pylance error since pyte.graphics doesn't actually
                # exist during static analysis
                for code, color in pyte.graphics.FG_ANSI.items(): # type: ignore
                    if color == char.fg:
                        needed_attrs.append(str(code))
                        current_state['fg'] = char.fg
                        break

            if char.bg != current_state['bg']:
                # Disable pylance error since pyte.graphics doesn't actually
                # exist during static analysis
                for code, color in pyte.graphics.BG_ANSI.items(): # type: ignore
                    if color == char.bg:
                        needed_attrs.append(str(code))
                        current_state['bg'] = char.bg
                        break

            return needed_attrs

        # Process scrollback buffer so we can have the history
        # Disable pylance error since pyte.graphics doesn't actually exist during
        # static analysis
        for y, line in enumerate(screen.scrollback_buffer): # type: ignore
            buf += "\n"
            for x, char in line.items():
                attrs = get_attribute_changes(char, current_state)

                # Write attributes if any changed
                if attrs:
                    buf += f"\033[{';'.join(attrs)}m"

                # Write the character
                buf += char.data

        # Process screen contents
        for y in range(screen.lines):
            buf += "\n"  # Position cursor at start of line

            for x in range(screen.columns):
                char = screen.buffer[y][x]
                attrs = get_attribute_changes(char, current_state)

                # Write attributes if any changed
                if attrs:
                    buf += f"\033[{';'.join(attrs)}m"

                # Write the character
                buf += char.data

            # Reset attributes at end of each line
            #buf += "\033[0m"
            # Reset our tracking state at end of line
            for key in current_state:
                current_state[key] = False
            current_state['fg'] = 'default'
            current_state['bg'] = 'default'

        # Reset cursor position at the end
        buf += f"\033[{screen.lines};1H"
        return buf.encode()

    def reset(self) -> None:
        """ Reset the screen to its initial state. """
        super().reset()
        self.cursor = EventsCursor(
                            terminal_buffer=self.terminal_buffer,
                            x=0,
                            y=0
                        )
        self.cursor_position()

@register_buffer("terminal")
class TerminalBuffer(Buffer):
    """
    Base class for Terminal buffer implementations.
    This class should be inherited by all PTY buffer implementations.
    """

    screen: EventsScreen
    stream: pyte.Stream

    def initialize(self, **extra):
        """ Initialize the PTY buffer with a screen and stream. """
        self.screen = EventsScreen(terminal_buffer=self)
        self.stream = pyte.Stream(self.screen)

    async def feed(self, data: bytes) -> None:
        """ This intercepts data sent to the frontend. """
        try:
            self.stream.feed(data.decode('utf-8'))
        except TypeError as ex:
            # We occasionally get errors like
            # TypeError: Screen.select_graphic_rendition() got
            # an unexpected keyword argument 'private'. It might be
            # related to using xterm rather than vt100 see:
            # https://github.com/selectel/pyte/issues/126
            if ex.args and "unexpected keyword argument 'private'" in ex.args[0]:
                pass
            else:
                raise
        except UnicodeDecodeError:
            self.stream.feed(bytes(data).decode('utf-8', errors='replace'))

    def dump_screen_state(self) -> bytes:
        """ Dumps the current screen state to an ANSI file with
            efficient style management. """
        return self.screen.dump_screen_state(self.screen)

    def set_terminal_size(
                self,
                rows: int,
                cols: int,
                xpix: int=0,
                ypix: int=0
            ) -> None:
        """Sets the shell window size."""
        self.screen.resize(lines=rows, columns=cols)
        self.screen.cursor_position()





