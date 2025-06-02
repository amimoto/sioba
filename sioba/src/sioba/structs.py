from typing import (
    Any,
    List,
    Dict,
    Generator,
    Optional,
    Literal,
    Union,
    overload,
)
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs
import enum

class URIConflictResolution(enum.Enum):
    """
    Enum for URI conflict resolution strategies.
    """
    FIRST = "first"
    LAST = "last"
    ARRAY = "array"
    ERROR = "error"

@dataclass
class URIDetails:
    uri: str
    scheme: str
    netloc: Optional[str]
    path: Optional[str]
    host: Optional[str]
    port: Optional[int]
    username: Optional[str]
    password: Optional[str]
    params: Optional[str]
    query: Dict[str, List[str]]

    # When you call param("name") with no resolve=…, it defaults to FIRST → Optional[str]
    @overload
    def param(self, key: str) -> Optional[str]:
        ...

    # Overload: when resolve == URIConflictResolution.ARRAY, we guarantee a List[str]
    @overload
    def param(
        self,
        key: str,
        default: Optional[str] = ...,
        resolve: Literal[URIConflictResolution.ARRAY] = ...,
    ) -> Optional[List[str]]:
        ...

    # 2) Overload #2: when resolve is FIRST, LAST, or ERROR (or omitted), we guarantee a str
    @overload
    def param(
        self,
        key: str,
        default: Optional[str] = ...,
        resolve: Literal[
            URIConflictResolution.FIRST,
            URIConflictResolution.LAST,
            URIConflictResolution.ERROR,
        ] = ...,
    ) -> Optional[str]:
        ...

    def param(
            self,
            key: str,
            default: Optional[str] = None,
            resolve: URIConflictResolution = URIConflictResolution.FIRST
            ) ->  Optional[Union[str, List[str]]]:
        """
        Get a parameter from the query, with conflict resolution.
        :param key: The key to look for in the query.
        :param default: The default value to return if the key is not found.
        :param resolve: The conflict resolution strategy to use.
                        - URIConflictResolution.FIRST: Return the first value found.
                        - URIConflictResolution.LAST: Return the last value found.
                        - URIConflictResolution.ARRAY: Return all values as a list.
                        - URIConflictResolution.ERROR: Raise an error if multiple values are found.
        :return: The value(s) associated with the key, or the default value.
        """
        if key in self.query and self.query[key]:
            if resolve == URIConflictResolution.ERROR and len(self.query[key]) > 1:
                raise ValueError(f"Multiple values found for key {key!r} in query: {self.query[key]}")
            elif resolve == URIConflictResolution.FIRST:
                return self.query[key][0]
            elif resolve == URIConflictResolution.LAST:
                return self.query[key][-1]
            elif resolve == URIConflictResolution.ARRAY:
                return self.query[key]
        return default

def parse_uri(uri: str) -> URIDetails:
    """
    Parse a URI and return its components as a dictionary.
    """
    parsed = urlparse(uri)
    if parsed.query:
        query_params = parse_qs(parsed.query)
    else:
        query_params = {}

    return URIDetails(
        uri = uri,
        scheme = parsed.scheme,
        netloc = parsed.netloc,
        path = parsed.path,
        host = parsed.hostname,
        port = parsed.port,
        username = parsed.username,
        password = parsed.password,
        params = parsed.params,
        query = query_params,
    )

@dataclass
class InterfaceConfig:
    rows: Optional[int] = None
    cols: Optional[int] = None
    title: Optional[str] = None

    encoding: Optional[str] = None
    convertEol: Optional[bool] = None
    auto_shutdown: Optional[bool] = None
    scrollback_buffer_size: Optional[int] = None

    def load_uri_details(self, details: URIDetails) -> None:
        """Load configuration from a URIDetails instance."""
        if ( rows := details.param("rows") ) is not None:
            self.rows = int(rows)
        if ( cols := details.param("cols") ) is not None:
            self.cols = int(cols)
        if ( encoding := details.param( "encoding") ) is not None:
            self.encoding = encoding
        if ( convertEol := details.param("convertEol") ) is not None:
            self.convertEol = bool(convertEol)
        if ( auto_shutdown := details.param("auto_shutdown") ) is not None:
            self.auto_shutdown = bool(auto_shutdown)
        if ( title := details.param("title") ) is not None:
            self.title = title

    def items(self) -> Generator[tuple[str, Any], None, None]:
        """Return all keys and values."""
        for k, v in asdict(self).items():
            yield (k, v)

    def update(self, options: "InterfaceConfig") -> None:
        """Update the configuration with another TerminalConfig instance."""
        for k, v in asdict(options).items():
            if v is not None:
                setattr(self, k, v)

    def copy(self) -> "InterfaceConfig":
        """Return a copy of the configuration."""
        return InterfaceConfig(**asdict(self))