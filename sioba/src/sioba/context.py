import types
from typing import (
    Any,
    Optional,
    Union,
    get_origin,
    get_args,
)
from dataclasses import (
    dataclass,
    field,
    fields,
    asdict,
)
from urllib.parse import urlparse, parse_qs

DEFAULT_ROWS = 24
DEFAULT_COLS = 80
DEFAULT_AUTO_SHUTDOWN = True
DEFAULT_SCROLLBACK_URI = "terminal://"
DEFAULT_SCROLLBACK_BUFFER_SIZE = 10_000

DEFAULT_VALUES = dict(
    rows=DEFAULT_ROWS,
    cols=DEFAULT_COLS,
    title="",

    cursor_col=0,
    cursor_row=0,

    scrollback_buffer_uri=DEFAULT_SCROLLBACK_URI,
    scrollback_buffer_size=DEFAULT_SCROLLBACK_BUFFER_SIZE,

    encoding="utf-8",

    convertEol=True,
    auto_shutdown=DEFAULT_AUTO_SHUTDOWN,
)

def cast_str_to_type(raw: str, typ: Any) -> Any:
    origin = get_origin(typ)
    args   = get_args(typ)

    # Optional[T] → just T
    if origin in [Union, types.UnionType]:
        if type(None) in args:
            non_none = [t for t in args if t is not type(None)]
            if len(non_none) == 1:
                return cast_str_to_type(raw, non_none[0])

    # primitives
    if typ is str:
        return raw

    if typ is int:
        return int(raw)

    if typ is float:
        return float(raw)

    if typ is bool:
        if isinstance(raw, str):
            return raw.lower() in ("1","true","yes")
        return bool(raw)

    return raw

@dataclass
class InterfaceContext:
    uri: Optional[str] = None
    scheme: Optional[str] = None
    netloc: Optional[str] = None
    path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    params: Optional[str] = None
    query: dict[str, list[str]] = field(default_factory=dict)

    rows: int|None = None
    cols: int|None = None
    title: str|None = None

    cursor_row: int|None = None
    cursor_col: int|None = None

    encoding: str|None = None
    convertEol: bool|None = None
    auto_shutdown: bool|None = None

    scrollback_buffer_uri: Optional[str] = None
    scrollback_buffer_size: int|None = None

    extra_params: dict[str, Any] = field(default_factory=dict) 

    @classmethod
    def from_uri(cls, uri: str, **extra) -> "InterfaceContext":
        """
        Parse a URI and return its components as a dictionary.
        """
        parsed = urlparse(uri)
        if parsed.query:
            query_params = parse_qs(parsed.query)
        else:
            query_params = {}

        kwargs = {
            "uri": uri,
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "host": parsed.hostname,
            "port": parsed.port,
            "username": parsed.username,
            "password": parsed.password,
            "query": query_params,
        }

        for f in fields(cls):
            if f.name not in query_params:
                continue
            raw_value = query_params[f.name][0]
            kwargs[f.name] = cast_str_to_type(raw_value, f.type)

        kwargs.update(extra)

        return cls.with_defaults(kwargs)

    @classmethod
    def with_defaults(cls, options: "InterfaceContext|None" = None, **kwargs) -> "InterfaceContext":
        """ Return a copy of the configuration with default values filled in. """

    def asdict(self):
        return asdict(self)

    def copy(self) -> "InterfaceContext":
        """Return a copy of the configuration."""
        return self.__class__(**asdict(self))

    def update(self, options: "InterfaceContext|dict") -> "InterfaceContext":
        """Update the configuration with another InterfaceContext instance."""
        attribs_as_dict = {}
        if isinstance(options, self.__class__):
            attribs_as_dict = asdict(options)
        elif isinstance(options, dict):
            attribs_as_dict = options

        for f in fields(self.__class__):
            if f.name not in attribs_as_dict:
                continue
            raw_value = attribs_as_dict[f.name]
            if raw_value is None:
                continue
            massaged_value = cast_str_to_type(raw_value, f.type)
            setattr(self, f.name, massaged_value)

        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        try:
            return getattr(self, key)
        except AttributeError:
            val = self.query.get(
                        key,
                        self.extra_params.get(
                            key,
                            default
                        )
                    )
            return val
        # Setup with default values
        context = cls().update(DEFAULT_VALUES)

        if options:
            context.update(options)

        if kwargs:
            context.update(kwargs)

        return context



