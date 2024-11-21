import asyncio
from pathlib import Path
from typing import Optional

from nicegui import background_tasks
from nicegui.client import Client

from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from niceterminal.utils.subprocess import InvokeProcess 

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
    ) -> None:
        super().__init__(value=value, on_value_change=on_change)
        self.add_resource(Path(__file__).parent / 'lib' / 'xterm.js')
        print(f"UI CLIENT: {self.client}")
        self.on_close_callback = on_close

        if not self.client.shared:
            print("Creaing background task")
            background_tasks.create(
                self._auto_close(),
                name='auto-close terminal'
            )

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

    async def _auto_close(self) -> None:
        while self.client.id in Client.instances:
            await asyncio.sleep(1.0)
        if self.on_close_callback:
            await self.on_close_callback(self)

    def on_close(self, callback) -> None:
        self.on_close_callback = callback

