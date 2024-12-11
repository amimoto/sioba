from typing import Callable

import pyte

from .base import Interface

from loguru import logger

class PersistentInterface(Interface):
    """Wraps an InvokeProcess to provide pyte terminal emulation capabilities"""
    process = None

    def __init__(self,
                 process: Interface,
                 on_read: Callable = None,
                 on_exit: Callable = None,
                 cols: int = 80,
                 rows: int = 24):
        self.process = process
        super().__init__(on_read=on_read, on_exit=on_exit)

        # Initialize pyte screen and stream
        self.screen = pyte.Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)

        # Wrap the process's on_read with our pyte handler
        self.process.on_read(self._pyte_handler)

    @logger.catch
    def _pyte_handler(self, process:Interface, data: bytes):
        """Handler that updates the pyte screen before passing data through"""
        try:
            self.stream.feed(data.decode('utf-8'))
        except UnicodeDecodeError:
            self.stream.feed(data.decode('utf-8', errors='replace'))

    # Delegate all InvokeProcess methods to the wrapped process
    @logger.catch
    def on_read(self, on_read: Callable):
        """Add a callback for when data is received"""
        self.process.on_read(on_read)

    @logger.catch
    async def launch_process(self):
        """Starts the shell process asynchronously."""
        try:
            await self.process.launch_process()
        except Exception as e:
            logger.error(f"Error launching process: {e}")

    @logger.catch
    async def write(self, data: bytes):
        """Writes data to the shell."""
        await self.process.write(data)

    @logger.catch
    def set_size(self, row, col, xpix=0, ypix=0):
        """Sets the shell window size."""
        self.process.set_size(row, col, xpix, ypix)
        self.screen.resize(lines=row, columns=col)

    @logger.catch
    async def shutdown(self):
        """Shuts down the shell process."""
        #await self.process.shutdown()
        pass

    def dump_screen_state(self, screen: pyte.Screen) -> str:
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
        return buf

    # Additional pyte-specific methods
    @logger.catch
    def get_screen_display(self) -> str:
        """Get the current screen contents as a string"""
        return self.dump_screen_state(self.screen)

    @logger.catch
    def get_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (self.screen.cursor.y, self.screen.cursor.x)

    @logger.catch
    def running(self) -> bool:
        """Check if the process is running"""
        return self.process.running()

    @logger.catch
    def __getattr__(self, name):
        """Delegate any other attributes to the wrapped process"""
        return getattr(self.process, name)