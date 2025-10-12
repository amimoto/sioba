from sioba import (
    register_scheme,
    IOInterface,
    DefaultValuesContext,
    UnsetFactory,
    UnsetOrNone,
)
from dataclasses import dataclass

import serial

@dataclass
class SerialContext(DefaultValuesContext):
    port: str|UnsetOrNone = UnsetFactory()
    baudrate: int|UnsetOrNone = UnsetFactory()
    bytesize: int|UnsetOrNone = UnsetFactory()
    parity: str|UnsetOrNone = UnsetFactory()
    stopbits: int|UnsetOrNone = UnsetFactory()
    timeout: int|UnsetOrNone = UnsetFactory()
    xonxoff: bool|UnsetOrNone = UnsetFactory()
    rtscts: bool|UnsetOrNone = UnsetFactory()
    write_timeout: bool|UnsetOrNone = UnsetFactory()
    dsrdtr: bool|UnsetOrNone = UnsetFactory()
    inter_byte_timeout: float|UnsetOrNone = UnsetFactory()
    exclusive: bool|UnsetOrNone = UnsetFactory()

    # For rfc2217
    ign_set_control: bool|UnsetOrNone = UnsetFactory()
    poll_modem: bool|UnsetOrNone = UnsetFactory()
    timeout: int|UnsetOrNone = UnsetFactory()

    # For socket
    # For loop
    logging: str|UnsetOrNone = UnsetFactory()

    # For hwgrep
    n: int|UnsetOrNone = UnsetFactory()
    skip_busy: bool|UnsetOrNone = UnsetFactory()

    # For spy
    file: str|UnsetOrNone = UnsetFactory()
    color: bool|UnsetOrNone = UnsetFactory()
    raw: bool|UnsetOrNone = UnsetFactory()
    all: bool|UnsetOrNone = UnsetFactory()

fields = (
    "port",
    "baudrate",
    "bytesize",
    "parity",
    "stopbits",
    "timeout",
    "xonxoff",
    "rtscts",
    "write_timeout",
    "dsrdtr",
    "inter_byte_timeout",
    "exclusive",
)

@register_scheme("serial", context_class=SerialContext)
@register_scheme("serial+rfc2217", context_class=SerialContext)
@register_scheme("serial+socket", context_class=SerialContext)
@register_scheme("serial+loop", context_class=SerialContext)
@register_scheme("serial+hwgrep", context_class=SerialContext)
@register_scheme("serial+spy", context_class=SerialContext)
class SerialInterface(IOInterface):

    def filehandle_create(self):
        scheme_parts: list[str] = self.context.scheme.split('+')

        serial_url: str = self.context.path
        if len(scheme_parts) > 1:
            serial_url = scheme_parts[-1] + "://" + serial_url

        config = self.context.asdict(fields=fields)
        serial_fh = serial.serial_for_url(serial_url, **config)
        return serial_fh

    def filehandle_read(self) -> bytes:
        data = self.handle.read()
        if isinstance(data, str):
            data = data.encode()
        return data

    def filehandle_write(self, data: bytes):
       self.handle.write(data)







