from pathlib import Path
from typing import Callable, List, Literal, Optional, get_args

from nicegui.elements.mixins.disableable_element import DisableableElement
from nicegui.elements.mixins.value_element import ValueElement
from nicegui.events import GenericEventArguments, Handler, ValueChangeEventArguments

class XTermJS(ValueElement, DisableableElement, component='xterm.js', default_classes='nicegui-xtermjs'):
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