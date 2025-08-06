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

def cast_str_to_type(raw: str, typ: Any) -> Any:
    origin = get_origin(typ)
    args   = get_args(typ)

    # Optional[T] → just T
    if origin is Union and type(None) in args:
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
        return raw.lower() in ("1","true","yes")

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
    query: Optional[dict[str, list[str]]] = None

    rows: int = 24
    cols: int = 80
    title: str = ""

    cursor_row: int = 0
    cursor_col: int = 0

    encoding: str = "utf-8"
    convertEol: bool = False
    auto_shutdown: bool = True

    scrollback_buffer_uri: Optional[str] = None
    scrollback_buffer_size: int = 10_000

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

        return cls(**kwargs)

    def asdict(self):
        return asdict(self)

    def copy(self) -> "InterfaceContext":
        """Return a copy of the configuration."""
        return self.__class__(**asdict(self))

    def update(self, options: "InterfaceContext") -> None:
        """Update the configuration with another InterfaceContext instance."""
        for k, v in asdict(options).items():
            if v is not None:
                setattr(self, k, v)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        try:
            return getattr(self, key)
        except AttributeError:
            if self.extra_params:
                return self.extra_params.get(key, default)




