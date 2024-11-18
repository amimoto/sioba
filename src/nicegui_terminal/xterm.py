from pathlib import Path
from typing import Optional

from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.events import Handler, ValueChangeEventArguments

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

    def __init__(
        self,
        value: str = '',
    ) -> None:
        on_change=None
        super().__init__(value=value, on_value_change=on_change)
        self.add_resource(Path(__file__).parent / 'lib' / 'xterm.js')

    def call_terminal_method(self, name: str, *args) -> None:
        self.run_method("call_api_method", name, *args)

    def write(self, data:str) -> None:
        self.run_method("write", data)

    def fit(self, data:str) -> None:
        self.run_method("fit", data)

    def rows(self) -> AwaitableResponse:
        return self.run_method("rows")

    def cols(self) -> AwaitableResponse:
        return self.run_method("cols")

    def sync_with_frontend(self) -> None:
        self.backend_output = "\n".join(self.screen.display)
        self.call_terminal_method("write", self.backend_output)


from nicegui_terminal.utils.subprocess import InvokeProcess 

class XTermProcess(XTerm):

    def __init__(
        self,
        invoke_command,
        shutdown_command: Optional[str] = None,
        *a, **kw
    ) -> None:
        super().__init__(*a, **kw)
        self.add_resource(Path(__file__).parent / 'lib' / 'xterm.js')

        # We launch a long running process if it hasn't been started yet
        def on_read(data):
            self.write(data.decode('utf-8'))
        self.shell = InvokeProcess('/bin/bash', None, on_read=on_read)

        async def on_render(e):
            self.shell.set_size(await self.rows(), await self.cols())
        self.on("render", on_render)

        async def on_resize(e):
            if rows := e.args.get("rows"):
                if cols := e.args.get("cols"):
                    self.shell.set_size(rows, cols)
        self.on("resize", on_resize)

        async def on_input(e):
            if isinstance(e.args, str):
                data = e.args
                await self.shell.write(data)
                #self.write(data)
        self.on("input", on_input)

    async def start(self):
        await self.shell.start()
