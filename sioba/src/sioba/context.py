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
from collections.abc import (
    Sequence,
)

DEFAULT_ROWS = 24
DEFAULT_COLS = 80
DEFAULT_AUTO_SHUTDOWN = True
DEFAULT_SCROLLBACK_URI = "terminal://"
DEFAULT_SCROLLBACK_BUFFER_SIZE = 10_000

class UnsetType:
    _singleton:"UnsetType" = None

    def __new__(cls, *args, **kwargs):
        """ Force Singleton of UnsetType """
        if cls._singleton is None:
            cls._singleton = super().__new__(cls)
        return cls._singleton

    def __bool__(self):
        return False  # Make instances of MyNullObject falsy

    def __eq__(self, other):
        return isinstance(other, UnsetType)

    def __ne__(self, other):
        return not isinstance(other, UnsetType)

UnsetOrNone: TypeAlias = UnsetType | None

Unset = UnsetType()

UnsetFactory = lambda *a, **kw: field(*a, default_factory=UnsetType, **kw)

def get_next_type(typ: Any) -> Any:
    """ Get the base type from a possibly wrapped type hint. """
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
                return get_next_type(non_none[0])

    # Handle the case that the type is a list
    if origin in [list, Sequence]:
        return origin

    return typ

def cast_str_to_type(data: Any, typ: Any) -> Any:
    """ Cast query parameter values to the appropriate type based on the provided type hint. """
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
                return cast_str_to_type(
                            data=data,
                            typ=non_none[0],
                        )

    # Handle the case that the type is a list
    if origin in [list, Sequence]:
        if not data:
            return []

        list_data = []
        for entry_data in data:
            list_data.append(
                cast_str_to_type(
                    data=entry_data,
                    typ=origin,
                )
            )

        return list_data

    if isinstance(data, UnsetType):
        return Unset

    if data is None:
        return

    # primitives
    if typ is str:
        return data

    if typ is int:
        return int(data)

    if typ is float:
        return float(data)

    if typ is bool:
        if isinstance(data, str):
            return data.lower() in ("1","true","yes")
        return bool(data)

    return data

@dataclass
class InterfaceContext:
    uri: str|UnsetOrNone = UnsetFactory()
    scheme: str|UnsetOrNone = UnsetFactory()
    netloc: str|UnsetOrNone = UnsetFactory()
    path: str|UnsetOrNone = UnsetFactory()
    host: str|UnsetOrNone = UnsetFactory()
    port: int|UnsetOrNone = UnsetFactory()
    username: str|UnsetOrNone = UnsetFactory()
    password: str|UnsetOrNone = UnsetFactory()
    params: str|UnsetOrNone = UnsetFactory()
    query: dict[str, list[str]] = field(default_factory=dict)

    rows: int|UnsetOrNone = UnsetFactory()
    cols: int|UnsetOrNone = UnsetFactory()
    title: str|UnsetOrNone = UnsetFactory()

    cursor_row: int|UnsetOrNone = UnsetFactory()
    cursor_col: int|UnsetOrNone = UnsetFactory()

    encoding: str|UnsetOrNone = UnsetFactory()
    convertEol: bool|UnsetOrNone = UnsetFactory()
    auto_shutdown: bool|UnsetOrNone = UnsetFactory()
    local_echo: bool|UnsetOrNone = UnsetFactory()

    scrollback_buffer_uri: str|UnsetOrNone = UnsetFactory()
    scrollback_buffer_size: int|UnsetOrNone = UnsetFactory()

    extra_params: dict[str, Any] = field(default_factory=dict) 

    @classmethod
    def from_uri(cls, uri: str, default_context:"InterfaceContext|None" = None, **extra) -> "InterfaceContext":
        """
        Parse a URI and return its components as a dictionary.
        """
        parsed = urlparse(uri)
        if parsed.query:
            query_params: dict[str, Any] = parse_qs(parsed.query)
        else:
            query_params: dict[str, Any] = {}

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

        # Normalize unset values to Unset
        for k, v in kwargs.items():
            if v is None:
                kwargs[k] = Unset

        # Due to how query_params works, it's not straightforward to
        # extract single values vs lists directly from the qs. So we
        # will use the type hints to normalize the values
        for f in fields(cls):
            if f.name not in query_params:
                continue

            base_type = get_next_type(f.type)

            if base_type in [dict]:
                # We don't handle dicts from query params
                continue

            elif base_type in [list, Sequence]:
                pass

            else:
                # Primitive type, make sure we only have one value
                if len(query_params[f.name]) > 1:
                    raise ValueError(f"Multiple values for a non-list type {query_params[f.name]}")
                query_params[f.name] = query_params[f.name][0]

        for f in fields(cls):
            if f.name not in query_params:
                continue
            raw_value = query_params[f.name]
            kwargs[f.name] = cast_str_to_type(
                data = raw_value,
                typ = f.type,
            )

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

        return context

    def asdict(self, fields:list[str]|None = None):
        if fields:
            data = {}
            for f in fields:
                if hasattr(self, f):
                    field_data = getattr(self, f)
                    if isinstance(field_data, UnsetType):
                        continue
                    data[f] = field_data
            return data
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
            if raw_value is Unset:
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
    rows: int|UnsetOrNone = DEFAULT_ROWS
    cols: int|UnsetOrNone = DEFAULT_COLS
    title: str|UnsetOrNone = ""

    cursor_col: int|UnsetOrNone = 0
    cursor_row: int|UnsetOrNone =  0

    scrollback_buffer_uri: str|UnsetOrNone = DEFAULT_SCROLLBACK_URI
    scrollback_buffer_size: int|UnsetOrNone = DEFAULT_SCROLLBACK_BUFFER_SIZE

    encoding: str|UnsetOrNone = "utf-8"
    local_echo: bool|UnsetOrNone = False

    convertEol: bool|UnsetOrNone = True
    auto_shutdown: bool|UnsetOrNone = DEFAULT_AUTO_SHUTDOWN




