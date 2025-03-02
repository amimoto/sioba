from niceterminal.interface.base import Interface, \
                    INTERFACE_STATE_STARTED, \
                    INTERFACE_STATE_INITIALIZED
from loguru import logger

class SimpleInterface(Interface):
    def __init__(self,
                 on_receive: Callable = None,
                 on_shutdown: Callable = None,
                 on_set_title: Callable = None,
                 ):
        super().__init__(
            on_receive=on_receive,
            on_shutdown=on_shutdown,
            on_set_title=on_set_title
        )

