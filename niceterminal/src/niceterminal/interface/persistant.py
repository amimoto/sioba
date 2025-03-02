from typing import Callable

import pyte

from .base import Interface

from loguru import logger

class EventsScreen(pyte.Screen):

    def __init__(self, columns: int, lines: int, on_set_title: Callable = None) -> None:
        super().__init__(columns=columns, lines=lines)
        self.on_set_title_handle = on_set_title

    def set_title(self, param: str) -> None:
        super().set_title(param)
        if self.on_set_title_handle:
            self.on_set_title_handle(param)


class PersistentInterface(Interface):
    """Wraps an InvokeProcess to provide pyte terminal emulation capabilities"""
    child_interface = None

    def __init__(self,
                 child_interface: Interface,
                 on_receive: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 cols: int = 80,
                 rows: int = 24) -> None:
        self.child_interface = child_interface
        super().__init__(on_receive=on_receive, on_shutdown=on_shutdown, on_set_title=on_set_title)

        # Initialize pyte screen and stream
        self.screen = EventsScreen(cols, rows, self.on_set_title_handle)
        self.stream = pyte.Stream(self.screen)

        # Wrap the process's on_receive with our pyte handler
        self.child_interface.on_receive(self._pyte_handler)

        # Wrap our own handler for exit
        self.child_interface.on_shutdown(
            lambda _: self.on_shutdown()
        )

    @logger.catch
    def _pyte_handler(self, interface:Interface, data: bytes):
        """Handler that updates the pyte screen before passing data through"""
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
            self.stream.feed(data.decode('utf-8', errors='replace'))

    # Delegate all InvokeProcess methods to the wrapped process
    @logger.catch
    def on_receive(self, on_receive: Callable):
        """Add a callback for when data is received"""
        self.child_interface.on_receive(on_receive)

    @logger.catch
    async def launch_interface(self):
        """Starts the shell process asynchronously."""
        try:
            await self.child_interface.launch_interface()
        except Exception as e:
            logger.error(f"Error launching process: {e}")

    @logger.catch
    async def send(self, data: bytes):
        """Writes data to the shell."""
        await self.child_interface.send(data)

    @logger.catch
    def set_size(self, rows, cols, xpix=0, ypix=0):
        """Sets the shell window size."""
        self.child_interface.set_size(rows=rows, cols=cols, xpix=xpix, ypix=ypix)
        self.screen.resize(lines=rows, columns=cols)

    @logger.catch
    def shutdown(self):
        """Shuts down the interface."""
        self.child_interface.shutdown()

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
                for code, color in pyte.graphics.FG_ANSI.items():
                    if color == char.fg:
                        needed_attrs.append(str(code))
                        current_state['fg'] = char.fg
                        break

            if char.bg != current_state['bg']:
                for code, color in pyte.graphics.BG_ANSI.items():
                    if color == char.bg:
                        needed_attrs.append(str(code))
                        current_state['bg'] = char.bg
                        break

            return needed_attrs

        # Process screen contents
        for y in range(screen.lines):
            buf += f"\033[{y+1};1H"  # Position cursor at start of line

            for x in range(screen.columns):
                char = screen.buffer[y][x]
                attrs = get_attribute_changes(char, current_state)

                # Write attributes if any changed
                if attrs:
                    buf += f"\033[{';'.join(attrs)}m"

                # Write the character
                buf += char.data

            # Reset attributes at end of each line
            buf += "\033[0m"
            # Reset our tracking state at end of line
            for key in current_state:
                current_state[key] = False
            current_state['fg'] = 'default'
            current_state['bg'] = 'default'

        # Reset cursor position at the end
        buf += f"\033[{screen.lines};1H"
        return buf.encode()

    @logger.catch
    def get_screen_display(self) -> bytes:
        """Get the current screen contents as a string"""
        return self.dump_screen_state(self.screen)

    @logger.catch
    def get_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (self.screen.cursor.y, self.screen.cursor.x)

    @logger.catch
    def running(self) -> bool:
        """Check if the process is running"""
        return self.child_interface.running()

    @logger.catch
    def __getattr__(self, name):
        """Delegate any other attributes to the wrapped process"""
        return getattr(self.child_interface, name)
