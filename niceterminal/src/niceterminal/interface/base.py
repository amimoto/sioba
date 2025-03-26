import asyncio
import time
from typing import Callable
from niceterminal.errors import InterfaceNotStarted, InterfaceError
import uuid
import pyte
import traceback

from loguru import logger

INTERFACE_STATE_INITIALIZED = 0
INTERFACE_STATE_STARTED = 1
INTERFACE_STATE_SHUTDOWN = 2

INTERFACE_THREAD = None
INTERFACE_LOOP = None

###########################################################
# Basic Interface Class that provides what XTerm expects
###########################################################

class Interface:
    def __init__(self,
                 on_receive_from_xterm: Callable = None,
                 on_send_to_xterm: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 cols: int = 80,
                 rows: int = 24) -> None:

        self.id = str(uuid.uuid4())
        self.title = ""
        self.reference_count = 0

        self._on_receive_from_xterm_callbacks = set()
        self._on_send_from_xterm_callbacks = set()
        self._on_shutdown_callbacks = set()
        self._on_set_title_callbacks = set()
        self.state = INTERFACE_STATE_INITIALIZED
        if on_receive_from_xterm:
            self.on_receive_from_xterm(on_receive_from_xterm)
        if on_send_to_xterm:
            self.on_send_to_xterm(on_send_to_xterm)
        if on_shutdown:
            self.on_shutdown(on_shutdown)
        if on_set_title:
            self.on_set_title(on_set_title)

        # Holds infomation on each terminial client
        # Things such as rows, cols
        self.term_clients = {}

        self.cols = cols
        self.rows = rows

        # Now do the subclass specific initialization
        self.init()

    # STATE

    def init(self):
        """ Subclassable method to initialize the interface """
        pass

    def reference_increment(self):
        self.reference_count += 1

    def reference_decrement(self):
        self.reference_count -= 1
        if self.reference_count <= 0:
            asyncio.create_task(
                self.shutdown()
            )

    @logger.catch
    async def start(self) -> "Interface":
        """ Start the interface.
            This is the initial entrypoint that kicks off things such as a thread
            if required. By default we work with the assumption that we're working
            in an asyncio environment. Threading left to the individual interfaces to
            implement if there are syncronous operations required.
        """

        if self.state != INTERFACE_STATE_INITIALIZED:
            return

        # Start the interface. This calls tasks required to finalize
        # the interface setup. For example, in the case of a socket
        # interface, this would start the socket connection.
        await self.launch(),

        return self

    @logger.catch
    async def launch(self) -> bool:
        """ Starts the shell process asynchronously.
            Returns a true value if the interface requires launching
        """
        if self.state != INTERFACE_STATE_INITIALIZED:
            return False
        self.state = INTERFACE_STATE_STARTED
        await self.launch_interface()
        return True

    @logger.catch
    async def launch_interface(self) -> bool:
        pass

    @logger.catch
    async def shutdown(self) -> None:
        """Callback when the shell process shutdowns."""
        self.state = INTERFACE_STATE_SHUTDOWN
        for on_shutdown in self._on_shutdown_callbacks:
            res = on_shutdown(self)
            if asyncio.iscoroutine(res):
                await res

    def is_running(self) -> bool:
        return self.state == INTERFACE_STATE_STARTED

    def is_shutdown(self) -> bool:
        return self.state == INTERFACE_STATE_SHUTDOWN

    # EVENT HOOK SETUP

    @logger.catch
    def on_send_to_xterm(self, on_send: Callable) -> None:
        """Add a callback for when data is received"""
        self._on_send_from_xterm_callbacks.add(on_send)

    @logger.catch
    def on_receive_from_xterm(self, on_receive: Callable) -> None:
        """Add a callback for when data is received"""
        self._on_receive_from_xterm_callbacks.add(on_receive)

    @logger.catch
    def on_set_title(self, on_set_title: Callable) -> None:
        """Add a callback for when the window title is set"""
        self._on_set_title_callbacks.add(on_set_title)

    @logger.catch
    def on_set_title_handle(self, title: str) -> None:
        """Callback when the window title is set."""
        self.title = title
        for on_set_title in self._on_set_title_callbacks:
            res = on_set_title(self, title)
            if asyncio.iscoroutine(res):
                asyncio.run(res)

    @logger.catch
    def on_shutdown(self, on_shutdown: Callable) -> None:
        """Add a callback for when the shell process shutdowns"""
        self._on_shutdown_callbacks.add(on_shutdown)

    # IO

    @logger.catch
    async def send_to_xterm(self, data: bytes) -> None:
        """Sends data (in bytes) to the xterm"""
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")

        # Don't bother if we don't have data
        if not data:
            return

        # Dispatch to all listeners
        for on_send in self._on_send_from_xterm_callbacks:
            logger.debug(f"Sending data to xterm: {data}")
            res = on_send(self, data)
            if asyncio.iscoroutine(res):
                await res

    @logger.catch
    async def receive_from_xterm(self, data: bytes) -> None:
        """Recieves data from the xterm as a sequence of bytes.
        """
        # Dispatch to all listeners
        for on_receive in self._on_receive_from_xterm_callbacks:
            res = on_receive(self, data)
            if asyncio.iscoroutine(res):
                await res

    # CONTROLS

    def set_title(self, name:str) -> None:
        self.on_set_title_handle(name)

    def set_size(self, rows: int, cols: int, xpix: int=0, ypix: int=0) -> None:
        """Sets the shell window size."""
        pass

    def get_screen_display(self) -> bytes:
        """Get the current screen contents as a string"""
        return b""

    def get_cursor_position(self) -> tuple[int,int]|None:
        return None

    def term_client_metadata_update(self, client_id:str, data:dict) -> None:
        self.term_clients.setdefault(client_id, {})
        self.term_clients[client_id].update(data)

        logger.debug(f"Updated client {client_id} metadata: {data}")

        min_row = None
        min_col = None
        for client_id, data in self.term_clients.items():
            if min_row is None or data["rows"] < min_row:
                min_row = data["rows"]
            if min_col is None or data["cols"] < min_col:
                min_col = data["cols"]
        self.rows = min_row
        self.cols = min_col

        self.set_size(rows=self.rows, cols=self.cols)

###########################################################
# Output buffer
###########################################################

class BufferedInterface(Interface):

    scrollback_buffer = None
    scrollback_buffer_size = 1_000_000

    def init(self):
        self.scrollback_buffer = b""

    async def send_to_xterm(self, data: bytes):
        if self.state != INTERFACE_STATE_STARTED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")

        # Don't bother if we don't have data
        if not data:
            return
 
        # Add to the scrollback buffer
        self.scrollback_buffer += data
        delta = self.scrollback_buffer_size - len(self.scrollback_buffer)
        if delta < 0:
            self.scrollback_buffer = self.scrollback_buffer[-delta:]

        return await super().send_to_xterm(data)

    def get_screen_display(self) -> bytes:
        """Get the current screen contents as a string"""
        return self.scrollback_buffer

###########################################################
# Screen Persistance via pytE
###########################################################

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

    def init(self):
        # Initialize pyte screen and stream
        super().init()
        print("PersistenceMixin init")

        self.screen = EventsScreen(self.cols, self.rows, self.on_set_title_handle)
        self.stream = pyte.Stream(self.screen)

    @logger.catch
    async def send_to_xterm(self, data: bytes):
        """Writes data to the shell."""
        await super().send_to_xterm(data)

        """Handler that updates the pyte screen before passing data through"""
        try:
            if not isinstance(data, bytes):
                raise InterfaceError(f"Expected bytes, got {type(data)}")
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

    @logger.catch
    def set_size(self, rows, cols, xpix=0, ypix=0):
        """Sets the shell window size."""
        super().set_size(rows=rows, cols=cols, xpix=xpix, ypix=ypix)
        self.screen.resize(lines=rows, columns=cols)

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
