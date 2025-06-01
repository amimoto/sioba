import asyncio
from typing import Callable
from .errors import InterfaceNotStarted, InterfaceError
from sioba.errors import TerminalClosedError
import uuid
import pyte
from enum import Enum
from typing import Optional, Any, Generator
from dataclasses import dataclass, asdict

from loguru import logger

class InterfaceState(Enum):
    INITIALIZED = 0
    STARTED = 1
    SHUTDOWN = 2

INTERFACE_THREAD = None
INTERFACE_LOOP = None

###########################################################
# Basic Interface Class that provides what XTerm expects
###########################################################

@dataclass
class InterfaceConfig:
    rows: Optional[int] = None
    cols: Optional[int] = None
    encoding: Optional[str] = None
    convertEol: Optional[bool] = None

    def items(self) -> Generator[tuple[str, Any], None, None]:
        """Return all keys and values."""
        for k, v in asdict(self).items():
            yield (k, v)

    def update(self, options: "InterfaceConfig") -> None:
        """Update the configuration with another TerminalConfig instance."""
        for k, v in asdict(options).items():
            if v is not None:
                setattr(self, k, v)

    def copy(self) -> "InterfaceConfig":
        """Return a copy of the configuration."""
        return InterfaceConfig(**asdict(self))

DEFAULT_CONFIG = InterfaceConfig(
    rows=24,
    cols=80,
    encoding="utf-8",
    convertEol=False,
)

class Interface:
    """ Interface is like the controller that abstracts the IO layer to the GUI layer.

        The basic flow is where the Instance is:

        - created with the appropriate configuration parameters
            - Done via __init__, subclass init_interface(self) for additional customization
            - The instance's main loop isn't started here
        - start the main loop that handles IO
            - Done via the start(), subclass start_interface(self) for additional customization
                will allow any custom startup routines without needing super
            - By default we don't assume threading or asyncio for the main loop and start
                a new task or thread. This is left to the subclass to implement depending
                on the interface type
        - shutdown and associated processes are terminated and resources are reaped
            - Done via the shutdown(), subclass shutdown_interface(self) for additional customization

    """

    # The default configuration for the interface type. These are defaults for the
    # protocol level. These values can be overwritten on a case by case basis as needed
    # via the interface_config argument. We don't use config so that it becomes available
    # for the protocol level configuration
    default_config: Optional[InterfaceConfig] = None
    interface_config: Optional[InterfaceConfig] = None

    # The state of the interface. When initialized it's InterfaceState.INITIALIZED
    state = None

    # This counds the number of gui controls referencing this interface.
    # Using this and the current interface state, we can figure out what the 
    reference_count: int = 0

    #######################################
    # Basic lifecycling handling
    #######################################

    def __init__(self,
                 on_receive_from_control: Callable = None,
                 on_send_to_control: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_terminal_title: Callable = None,
                 cols: int = 80,
                 rows: int = 24,
                 auto_shutdown: bool = True,
                 interface_config: Optional[InterfaceConfig] = None,
                 ) -> None:

        self.id = str(uuid.uuid4())
        self.title = ""
        self.reference_count = 0

        self.interface_config = DEFAULT_CONFIG.copy()
        if self.default_config:
            self.interface_config.update(self.default_config)
        if interface_config:
            self.interface_config.update(interface_config)

        self._on_receive_from_control_callbacks = set()
        self._on_send_from_xterm_callbacks = set()
        self._on_shutdown_callbacks = set()
        self._on_set_terminal_title_callbacks = set()
        self.state = InterfaceState.INITIALIZED
        if on_receive_from_control:
            self.on_receive_from_control(on_receive_from_control)
        if on_send_to_control:
            self.on_send_to_control(on_send_to_control)
        if on_shutdown:
            self.on_shutdown(on_shutdown)
        if on_set_terminal_title:
            self.on_set_terminal_title(on_set_terminal_title)

        # Holds infomation on each terminial client
        # Things such as rows, cols
        self.term_clients = {}

        self.auto_shutdown = auto_shutdown
        self.cols = cols
        self.rows = rows

        # Now do the subclass specific initialization
        self.init_interface()

    def init_interface(self):
        """ Subclassable method to initialize the interface """
        pass

    @logger.catch
    async def start(self) -> "Interface":
        """ Start the interface.
            This is the initial entrypoint that kicks off things such as a thread
            if required. By default we work with the assumption that we're working
            in an asyncio environment. Threading left to the individual interfaces to
            implement if there are syncronous operations required.
        """

        if self.state != InterfaceState.INITIALIZED:
            return

        # Start the interface. This calls tasks required to finalize
        # the interface setup. For example, in the case of a socket
        # interface, this would start the socket connection.
        if self.state != InterfaceState.INITIALIZED:
            return False
        self.state = InterfaceState.STARTED
        await self.start_interface()

        return self

    async def start_interface(self) -> bool:
        pass

    @logger.catch
    async def shutdown(self) -> None:
        """Callback when the shell process shutdowns."""
        if self.state != InterfaceState.STARTED:
            return
        await self.shutdown_interface()
        self.state = InterfaceState.SHUTDOWN
        logger.debug(f"Shutting down interface {self.id}")
        for on_shutdown in self._on_shutdown_callbacks:
            res = on_shutdown(self)
            if asyncio.iscoroutine(res):
                await res

    async def shutdown_interface(self) -> None:
        pass

    #######################################
    # Lifecycle state querying
    #######################################

    def is_running(self) -> bool:
        return self.state == InterfaceState.STARTED

    def is_shutdown(self) -> bool:
        return self.state == InterfaceState.SHUTDOWN

    #######################################
    # IO Events
    #######################################

    @logger.catch
    def on_send_to_control(self, on_send: Callable) -> None:
        """Add a callback for when data is received"""
        self._on_send_from_xterm_callbacks.add(on_send)

    @logger.catch
    def on_receive_from_control(self, on_receive: Callable) -> None:
        """Add a callback for when data is received"""
        self._on_receive_from_control_callbacks.add(on_receive)

    @logger.catch
    async def send_to_control(self, data: bytes) -> None:
        """Sends data (in bytes) to the xterm"""
        if self.state == InterfaceState.INITIALIZED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")
        elif self.state == InterfaceState.SHUTDOWN:
            raise TerminalClosedError(f"Unable to send data {repr(data)}, interface is shutdown")

        # Don't bother if we don't have data
        if not data:
            return

        if self.interface_config.convertEol:
            data = data.replace(b"\r", b"\r\n")

        # Dispatch to all listeners
        for on_send in self._on_send_from_xterm_callbacks:
            logger.debug(f"Sending data to xterm: {data}")
            res = on_send(self, data)
            if asyncio.iscoroutine(res):
                await res

    @logger.catch
    async def receive_from_control(self, data: bytes) -> None:
        """Recieves data from the xterm as a sequence of bytes.
        """
        # Dispatch to all listeners
        for on_receive in self._on_receive_from_control_callbacks:
            res = on_receive(self, data)
            if asyncio.iscoroutine(res):
                await res

    #######################################
    # Other Events handling
    #######################################

    @logger.catch
    def on_set_terminal_title(self, on_set_terminal_title: Callable) -> None:
        """Add a callback for when the window title is set"""
        self._on_set_terminal_title_callbacks.add(on_set_terminal_title)

    @logger.catch
    def on_set_terminal_title_handle(self, title: str) -> None:
        """Callback when the window title is set."""
        self.title = title
        for on_set_terminal_title in self._on_set_terminal_title_callbacks:
            res = on_set_terminal_title(self, title)
            if asyncio.iscoroutine(res):
                asyncio.run(res)

    @logger.catch
    def on_shutdown(self, on_shutdown: Callable) -> None:
        """Add a callback for when the shell process shutdowns"""
        self._on_shutdown_callbacks.add(on_shutdown)

    #######################################
    # Terminal Buffer Abstraction
    #######################################

    def set_terminal_title(self, name:str) -> None:
        self.on_set_terminal_title_handle(name)

    def set_terminal_size(self, rows: int, cols: int, xpix: int=0, ypix: int=0) -> None:
        """Sets the shell window size."""
        pass

    def get_terminal_buffer(self) -> bytes:
        """Get the current screen contents as a string"""
        return b""

    def get_terminal_cursor_position(self) -> tuple[int,int]|None:
        return None

    def update_terminal_metadata(self, client_id:str, data:dict) -> None:
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

        self.set_terminal_size(rows=self.rows, cols=self.cols)

    def get_terminal_metadata(self, client_id:str) -> dict:
        if client_id not in self.term_clients:
            return {}

        return self.term_clients[client_id]

    def reference_increment(self):
        print(f"Reference count: {self.reference_count}. Incrementing")
        self.reference_count += 1

    def reference_decrement(self):
        print(f"Reference count: {self.reference_count}. Decrementing")
        self.reference_count -= 1
        if self.reference_count <= 0 and self.auto_shutdown:
            asyncio.create_task(
                self.shutdown()
            )

###########################################################
# Output buffer
###########################################################

class BufferedInterface(Interface):

    scrollback_buffer: list = None
    scrollback_buffer_size: int = 10_000

    def __init__(self,
                scrollback_buffer_size: int = 10_000,

                # From superclass
                on_receive_from_control: Callable = None,
                on_send_to_control: Callable = None,
                on_shutdown: Callable = None,
                on_set_terminal_title: Callable = None,
                cols: int = 80,
                rows: int = 24,
                auto_shutdown: bool = True,
            ) -> None:
        self.scrollback_buffer_size = scrollback_buffer_size
        super().__init__(
            on_receive_from_control=on_receive_from_control,
            on_send_to_control=on_send_to_control,
            on_shutdown=on_shutdown,
            on_set_terminal_title=on_set_terminal_title,
            cols=cols,
            rows=rows,
            auto_shutdown=auto_shutdown,
        )

    def init_interface(self):
        self.scrollback_buffer = b""

    async def send_to_control(self, data: bytes):
        if self.state != InterfaceState.STARTED:
            raise InterfaceNotStarted(f"Unable to send data {repr(data)}, interface not started")

        # Don't bother if we don't have data
        if not data:
            return

        # Add to the scrollback buffer
        self.scrollback_buffer += data
        delta = self.scrollback_buffer_size - len(self.scrollback_buffer)
        if delta < 0:
            self.scrollback_buffer = self.scrollback_buffer[-delta:]

        return await super().send_to_control(data)

    def get_terminal_buffer(self) -> bytes:
        """Get the current screen contents as a string"""
        return self.scrollback_buffer

###########################################################
# Screen Persistance via pytE
###########################################################

class EventsScreen(pyte.Screen):

    scrollback_buffer = None
    scrollback_buffer_size = None

    def __init__(
            self,
            columns: int,
            lines: int,
            on_set_terminal_title: Callable = None,
            scrollback_buffer_size: int = 10_000,

        ) -> None:
        self.on_set_terminal_title_handle = on_set_terminal_title
        self.scrollback_buffer = []
        self.scrollback_buffer_size = scrollback_buffer_size
        super().__init__(columns=columns, lines=lines)

    def set_terminal_title(self, param: str) -> None:
        super().set_terminal_title(param)
        if self.on_set_terminal_title_handle:
            self.on_set_terminal_title_handle(param)

    def index(self) -> None:
        """Move the cursor down one line in the same column. If the
        cursor is at the last line, create a new line at the bottom.
        """
        top, bottom = self.margins or pyte.screens.Margins(0, self.lines - 1)
        if self.cursor.y == bottom:
            # TODO: mark only the lines within margins?
            self.dirty.update(range(self.lines))

            # Save the line going out of scope into the scrollback buffer
            self.scrollback_buffer.append(self.buffer[top])
            while len(self.scrollback_buffer) > self.scrollback_buffer_size:
                self.scrollback_buffer.pop(0)

            for y in range(top, bottom):
                self.buffer[y] = self.buffer[y + 1]
            self.buffer.pop(bottom, None)
        else:
            self.cursor_down()

class PersistentInterface(Interface):
    """Wraps an InvokeProcess to provide pyte terminal emulation capabilities"""

    def __init__(self,
                scrollback_buffer_size: int = 10_000,

                # From superclass
                on_receive_from_control: Callable = None,
                on_send_to_control: Callable = None,
                on_shutdown: Callable = None,
                on_set_terminal_title: Callable = None,
                cols: int = 80,
                rows: int = 24,
                auto_shutdown: bool = True,
            ) -> None:
        self.scrollback_buffer_size = scrollback_buffer_size
        super().__init__(
            on_receive_from_control=on_receive_from_control,
            on_send_to_control=on_send_to_control,
            on_shutdown=on_shutdown,
            on_set_terminal_title=on_set_terminal_title,
            cols=cols,
            rows=rows,
            auto_shutdown=auto_shutdown,
        )

    def init_interface(self):
        # Initialize pyte screen and stream
        super().init_interface()

        self.screen = EventsScreen(
            columns=self.cols,
            lines=self.rows,
            on_set_terminal_title=self.on_set_terminal_title_handle,
            scrollback_buffer_size=self.scrollback_buffer_size,
        )

        self.stream = pyte.Stream(self.screen)

    @logger.catch
    async def send_to_control(self, data: bytes):
        """Writes data to the shell."""
        await super().send_to_control(data)

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
    def set_terminal_size(self, rows: int, cols: int, xpix: int=0, ypix: int=0):
        """Sets the shell window size."""
        super().set_terminal_size(rows=rows, cols=cols, xpix=xpix, ypix=ypix)
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

        # Process scrollback buffer so we can have the history
        for y, line in enumerate(screen.scrollback_buffer):
            buf += "\n\r"
            for x, char in line.items():
                attrs = get_attribute_changes(char, current_state)

                # Write attributes if any changed
                if attrs:
                    buf += f"\033[{';'.join(attrs)}m"

                # Write the character
                buf += char.data

        # Process screen contents
        for y in range(screen.lines):
            buf += "\n\r"  # Position cursor at start of line

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
    def get_terminal_buffer(self) -> bytes:
        """Get the current screen contents as a string"""
        return self.dump_screen_state(self.screen)

    @logger.catch
    def get_terminal_cursor_position(self) -> tuple:
        """Get the current cursor position"""
        return (self.screen.cursor.y, self.screen.cursor.x)



