from pathlib import Path
from typing import Callable, List, Literal, Optional, get_args

from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.events import GenericEventArguments, Handler, ValueChangeEventArguments

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
        on_change: Optional[Handler[ValueChangeEventArguments]] = None,
        *args,
    ) -> None:
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

