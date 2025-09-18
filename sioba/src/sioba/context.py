import types
from typing import (
    Any,
    Union,
    get_origin,
    get_args,
    TypeAlias,
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

class UnsetType: pass

UnsetOrNone: TypeAlias = UnsetType | None

UNSET = UnsetType()

def cast_str_to_type(raw: Any, typ: Any) -> Any:
    origin = get_origin(typ)
    args   = get_args(typ)

    # Optional[T] → just T
    if origin in [Union, types.UnionType]:
        if type(None) in args:
            non_none = []
            for t in args:
                if t is type(None):
                    continue
                if t in [UnsetOrNone, UnsetType]:
                    continue
                non_none.append(t)
            if len(non_none) == 1:
                return cast_str_to_type(raw, non_none[0])

    if isinstance(raw, UnsetType):
        return raw

    # primitives
    if typ is str:
        return raw

    if typ is int:
        if raw is None:
            return
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
    uri: str|UnsetOrNone = UNSET
    scheme: str|UnsetOrNone = UNSET
    netloc: str|UnsetOrNone = UNSET
    path: str|UnsetOrNone = UNSET
    host: str|UnsetOrNone = UNSET
    port: int|UnsetOrNone = UNSET
    username: str|UnsetOrNone = UNSET
    password: str|UnsetOrNone = UNSET
    params: str|UnsetOrNone = UNSET
    query: dict[str, list[str]] = field(default_factory=dict)

    rows: int|UnsetOrNone = UNSET
    cols: int|UnsetOrNone = UNSET
    title: str|UnsetOrNone = UNSET

    cursor_row: int|UnsetOrNone = UNSET
    cursor_col: int|UnsetOrNone = UNSET

    encoding: str|UnsetOrNone = UNSET
    convertEol: bool|UnsetOrNone = UNSET
    auto_shutdown: bool|UnsetOrNone = UNSET
    local_echo: bool|UnsetOrNone = UNSET

    scrollback_buffer_uri: str|UnsetOrNone = UNSET
    scrollback_buffer_size: int|UnsetOrNone = UNSET

    extra_params: dict[str, Any] = field(default_factory=dict) 

    @classmethod
    def from_uri(cls, uri: str, default_context:"InterfaceContext|None" = None, **extra) -> "InterfaceContext":
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

        return cls.with_defaults(options=default_context, **kwargs)

    @classmethod
    def with_defaults(
            cls,
            options: "InterfaceContext|None" = None,
            **kwargs
        ) -> "InterfaceContext":
        """ Return a copy of the configuration with default values filled in. """

        # Setup with default values
        context = cls()

        if options:
            context.update(options)

        if kwargs:
            context.update(kwargs)

        for f in fields(context.__class__):
            if getattr(context, f.name) is UNSET:
                setattr(context, f.name, None)

        return context

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
            if isinstance(raw_value, UnsetType):
                continue
            massaged_value = cast_str_to_type(raw_value, f.type)
            setattr(self, f.name, massaged_value)

        return self

    def fill_missing(self, defaults: "InterfaceContext|dict") -> "InterfaceContext":
        """Fill in missing values from another InterfaceContext instance."""

        # Normalize to dict
        attribs_as_dict = {}
        if isinstance(defaults, self.__class__):
            attribs_as_dict = asdict(defaults)
        elif isinstance(defaults, dict):
            attribs_as_dict = defaults

        for f in fields(self.__class__):
            if f.name not in attribs_as_dict:
                continue

            """
            current_value = getattr(self, f.name)

            if not isinstance(current_value, UnsetType) and current_value is not None:
                continue

            raw_value = attribs_as_dict[f.name]

            if isinstance(raw_value, UnsetType):
                continue

            massaged_value = cast_str_to_type(raw_value, f.type)
            setattr(self, f.name, massaged_value)
            """

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

@dataclass
class DefaultValuesContext(InterfaceContext):
    rows:int = DEFAULT_ROWS
    cols:int = DEFAULT_COLS
    title:str = ""

    cursor_col:int = 0
    cursor_row:int =  0

    scrollback_buffer_uri:str = DEFAULT_SCROLLBACK_URI
    scrollback_buffer_size:int = DEFAULT_SCROLLBACK_BUFFER_SIZE

    encoding:str = "utf-8"
    local_echo:bool = False

    convertEol:bool = True
    auto_shutdown:bool = DEFAULT_AUTO_SHUTDOWN




