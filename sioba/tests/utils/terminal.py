import pyte


class EventsScreen(pyte.Screen):

    scrollback_buffer: list
    scrollback_buffer_size: int

    def __init__(self, *args, **kwargs) -> None:
        self.scrollback_buffer = []
        super().__init__(*args, **kwargs)

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
            buf += "\033[0m"
            # Reset our tracking state at end of line
            for key in current_state:
                current_state[key] = False
            current_state['fg'] = 'default'
            current_state['bg'] = 'default'

        # Reset cursor position at the end
        buf += f"\033[{screen.lines};1H"
        return buf.encode()

class EventsStream(pyte.Stream):
    """
    Custom Stream class to handle terminal data with event handling.
    This class extends pyte.Stream to provide additional functionality.
    """
    def feed(self, data: str) -> None:
        """
        Feed data to the stream and handle events.
        This method overrides the default feed method to add custom behavior.

        :param str data: a blob of data to feed from.
        """
        super().feed(data)

def strip_terminal_escapes(data: bytes, cols: int=80, rows: int=24) -> str:
    """ Strip ANSI escape sequences from terminal data. """
    screen = EventsScreen(cols, rows)
    stream = EventsStream(screen)
    stream.feed(data.decode())
    return "\n".join(screen.display)




