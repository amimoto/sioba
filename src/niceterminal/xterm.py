import asyncio
from pathlib import Path
from typing import Optional, Callable

import base64

from loguru import logger

from nicegui import background_tasks, ui, core, app
from nicegui.nicegui import sio
from nicegui.client import Client

from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement

from niceterminal.interface.base import Interface 
from niceterminal.interface.subprocess import ShellInterface, INVOKE_COMMAND

from nicegui.awaitable_response import AwaitableResponse

class XTerm(
        ValueElement,
        DisableableElement,
        component='xterm.js',
        default_classes='nicegui-xtermjs'
    ):

    # TODO: Cargo culted code - Should this be a value/loopback?
    VALUE_PROP = 'value'
    LOOPBACK = None

    on_close_callback = None

    def __init__(
        self,
        value: str = '',
        on_change: Optional[callable] = None,
        on_close: Optional[callable] = None,
        interface: Interface = None,
        rows:int = 24,
        cols:int = 80,
        **kwargs
    ) -> None:

        #props = kwargs.getdefault('props', {})
        #options = props.setdefault('options', {})
        #options.setdefault('termType', 'xterm-256color')

        super().__init__(value=value, on_value_change=on_change, **kwargs)
        self.add_resource(Path(__file__).parent / 'lib' / 'xterm.js')
        self.on_close_callback = on_close

        # Holds infomation on each terminial client
        # Things such as rows, cols
        self.term_clients = {}

        self.rows = rows
        self.cols = cols

        if not self.client.shared:
            background_tasks.create(
                self._auto_close(),
                name='auto-close terminal'
            )

        if interface:
            self.connect_process(interface)

        # Check if the root route is defined
        for route in app.routes:
            print(route)
        is_auto_index = '/' not in [route.path for route in app.routes]

        if is_auto_index:
            print('Running in auto-index mode')
        else:
            print('Custom route for / is defined')

        print("CLIENT:", self.client)
        print("AUTOINDEX:", self.client.is_auto_index_client)

    def call_terminal_method(self, name: str, *args) -> None:
        self.run_method("callAPIMethod", name, *args)

    def write(self, data:bytes) -> None:
        if core.loop is None:
            return
        if isinstance(data, str):
            raise TypeError("data must be bytes")
        with self:
            serialized_data = base64.b64encode(data).decode()
            ui.run_javascript(
                f"runMethod({self.id}, 'write', ['{serialized_data}']);"
            )

    def fit(self, data:str) -> None:
        if core.loop is None:
            return
        self.run_method("fit", data)

    def rows(self) -> int:
        return self.rows

    def cols(self) -> AwaitableResponse:
        return self.cols

    def set_cursor_location(self, row:int, col:int) -> AwaitableResponse:
        self.run_method("setCursorLocation", row, col)

    def sync_with_frontend(self) -> None:
        #self.backend_output = "\n".join(self.screen.display)
        #self.call_terminal_method("write", self.backend_output)

        if core.loop is None:
            return

        cursor_position = self.process.get_cursor_position()

        data = self.process.get_screen_display()
        if isinstance(data, str):
            data = data.encode()

        with self:
            serialized_data = base64.b64encode(data).decode()
            ui.run_javascript(
                f"runMethod({self.id}, 'refreshScreen', ['{serialized_data}']);"
            )
        self.set_cursor_location(*cursor_position)

    async def _auto_close(self) -> None:
        while self.client.id in Client.instances:
            await asyncio.sleep(1.0)
        if self.on_close_callback:
            await self.on_close_callback(self)

    def on_close(self, callback) -> None:
        self.on_close_callback = callback

    @property
    def client_is_auto_index(self) -> bool:
        return self.client.is_auto_index_client

    def term_client_metadata_update(self, client_id:str, data:dict) -> None:
        self.term_clients.setdefault(client_id, {})
        self.term_clients[client_id].update(data)

        min_row = None
        min_col = None
        for client_id, data in self.term_clients.items():
            if min_row is None or data["rows"] < min_row:
                min_row = data["rows"]
            if min_col is None or data["cols"] < min_col:
                min_col = data["cols"]
        self.rows = min_row
        self.cols = min_col

    def connect_process(self, process:Interface) -> None:
        """ Connects the XTerm to an InvokeProcess object """ 
        self.process = process

        #######################################################################

        def process_on_read(_, data):
            if self.client.id in Client.instances:
                self.write(data)
        process.on_read(process_on_read)

        def on_exit(_):
            self.write("[Process Exited]\n\r")
        process.on_exit(on_exit)

        #######################################################################

        async def client_on_render(e):
            self.process.set_size(self.rows, self.cols)
        self.on("render", client_on_render)

        async def client_on_resize(e):
            (data, sio_sid) = e.args

            rows = data.get("rows")
            cols = data.get("cols")
            if not (rows and cols):
                return

            self.term_client_metadata_update(
                        f"{self.client.id}-{sio_sid}",
                        {
                            "rows": rows,
                            "cols": cols
                        })
            self.process.set_size(rows, cols)
        self.on("resize", client_on_resize)

        async def client_on_data(e):
            (data, _) = e.args
            if isinstance(data, str):
                await self.process.write(base64.b64decode(data))
        self.on("data", client_on_data)

        async def process_on_close(self):
            await self.process.shutdown()
        self.on_close(process_on_close)

        def client_on_connect(client: Client):
            print("CONNECTED!", client)
            self.sync_with_frontend()
        self.client.on_connect(client_on_connect)

        def client_on_disconnect(e):
            # We don't know who disconnected so we'll need to
            # go through the list of clients and remove the one
            # that disconnected
            print(f"DISCONECTED! {e=}")
        self.client.on_disconnect(client_on_disconnect)

        async def on_mount(e):
            (data, _) = e.args
            if self.client_is_auto_index:
                self.sync_with_frontend()
            else:
                await self.run_method("noop")
        self.on("mount", on_mount)

        #######################################################################

        if not self.client.shared:
            background_tasks.create(
                self.process.launch_process(),
                name='Invoke process handling'
            )

    def __getattr__(self, name):
        print(f"GETATTR {name}")
        return object.__getattribute__(self, name)

class ShellXTerm(
                XTerm,
                ValueElement,
                DisableableElement,
                component='xterm.js',
                default_classes='nicegui-xtermjs'
            ):

    def __init__(
                self,
                invoke_command: str = INVOKE_COMMAND,
                shutdown_command: str = None,
                on_read: Callable = None,
                on_exit: Callable = None,
                cwd: str = None,
                rows: int = 80,
                cols: int = 24,
                value: str = '',
                on_change: Optional[callable] = None,
                on_close: Optional[callable] = None,
            ):

        interface = ShellInterface(
                            invoke_command=invoke_command,
                            shutdown_command=shutdown_command,
                            cwd=cwd,
                            on_read=on_read,
                            on_exit=on_exit,
                            rows=rows,
                            cols=cols,
                    ).start()

        super().__init__(
            interface=interface,
            value=value,
            on_change=on_change,
            on_close=on_close,
            rows=rows,
            cols=cols,
        )

