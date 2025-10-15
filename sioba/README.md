# sioba — IO abstraction layer for terminal-like interfaces

A small Python library that unifies interactive IO (functions, TCP/SSL sockets) behind a single async `Interface` API with pluggable scrollback buffers (terminal emulator or simple line buffer).

<img src="https://raw.githubusercontent.com/amimoto/sioba/refs/heads/main/sioba/sioba-image.png" width="300" />

---

## Overview

* **Interfaces**: concrete implementations for `echo://`, `tcp://host:port`, and `ssl://host:port`, plus a `FunctionInterface` to wrap regular Python functions into an interactive session.
* **Buffers (scrollback/state)**: choose `terminal://` (ANSI/VT via **pyte**) or `line://` (raw lines). Both keep cursor position and bounded history.
* **URI-driven config**: `InterfaceContext.from_uri()` parses connection + runtime options (rows/cols/title/encoding/convertEol/auto\_shutdown, etc.).
* **Callbacks**: hook `on_send_to_frontend`, `on_receive_from_frontend`, `on_shutdown`, `on_set_terminal_title`.
* **Plugin registries**: register new interface schemes or buffers via decorators, or expose them via entry points.
* **Rich integration**: `Interface.filehandle()` returns a TTY-like handle (isatty=True) so `rich.Console` writes render with color.

---

## Installation

```bash
pip install sioba
```

**Using uv:**

```bash
uv pip install sioba
```

* Requires **Python ≥ 3.10**.
* Runtime deps: `loguru`, `rich`, `pyte`, `janus`.

---

## Quickstart

### Echo interface (minimal)

```python
import asyncio
from sioba import interface_from_uri, Interface

async def main():
    # uri-like creation of interface instances for consistent
    # invocation syntax that can be easily put into a conf
    echo = await interface_from_uri("echo://").start()

    # Example of callback
    captured = []
    async def on_send_to_frontend(_i: Interface, data: bytes):
        captured.append(data)
    echo.on_send_to_frontend(on_send_to_frontend)

    # Manually inject data into the interface instance
    await echo.receive_from_frontend(b"Hello, World!")

    # We should have received the data in our callback
    print(captured[0])           # b"Hello, World!"

    # Finally cleanup
    await echo.shutdown()

asyncio.run(main())
```

---

## Core Concepts / Features

* **Interface & lifecycle**

  * `sioba.interface_from_uri("tcp://host:1234?rows=52&cols=100")` parses URI + query into fields (scheme, host, port, rows, cols, etc.) creates InterfaceContext, Buffer, and the Interface itself.
  * `Interface` manages state (`INITIALIZED` → `STARTED` → `SHUTDOWN`), send/receive, callbacks, and a **buffer**.
  * `await interface.start()` then interact via `receive_from_frontend()` (input) and `on_send_to_frontend()` (output).
  * `get_terminal_buffer()` returns a snapshot of current screen/buffer; `get_terminal_cursor_position()` exposes (row, col).

* **Context**

  * `InterfaceContext.from_uri("tcp://host:1234?rows=52&cols=100")` parses URI + query into fields (scheme, host, port, rows, cols, etc.).
  * Defaults: rows=24, cols=80, encoding=`utf-8`, `convertEol=True`, `auto_shutdown=True`, `scrollback_buffer_uri="terminal://"`, `scrollback_buffer_size=10000`.

* **Buffers**

  * `terminal://` uses **pyte** to emulate ANSI terminals (title changes, scrollback, style attributes, cursor updates).
  * `line://` stores raw lines with simple newline splitting.

* **Registries & plugins**

  * Interfaces: decorate with `@register_scheme("myscheme")` or provide entry points under `sioba.interface`.
  * Buffers: `@register_buffer("mybuffer")` or entry point `sioba.buffer`.

---

## High Level Architecture

sioba is composed of 3 primary concepts: **transport/control** from **screen state** and **configuration**:

* **Interface** (`sioba.interface.base.Interface`) owns the lifecycle, transports, and callback wiring.
* **Buffer** (`sioba.buffer.base.Buffer` and implementations) is a sidecar that maintains a *screen/scrollback view* of what the user should see.
* **InterfaceContext** (`sioba.context.InterfaceContext`) is the shared config/runtime state that both Interface and Buffer read and update.

---

### 1 Interface (transport + lifecycle)

**Where it lives:** `sioba.interface.base.Interface` (base class) with concrete types like:

* `EchoInterface` (`echo://`) (`sioba.interface.echo`)
* `SocketInterface` (`tcp://host:port?args`) & `SecureSocketInterface` (`ssl://host:port?args`) (`sioba.interface.socket`)
* `FunctionInterface` (`sioba.interface.function`): Base class, doesn't provide direct functionality but makes scripted behaviors possible

**What it does:**

* Manages **state** (`InterfaceState.INITIALIZED/STARTED/SHUTDOWN`) and lifecycle: `await start()`, `await shutdown()`.
* Normalizes **IO**:

  * `receive_from_frontend(data)` handles *incoming* user data (e.g., keystrokes). If `convertEol=True`, `\r\n`/`\r` → `\n`. Calls an overridable `receive_from_frontend_handle`.
  * `send_to_frontend(data)` handles *outgoing* data (e.g., server output). If `convertEol=True`, `\n` → `\r\n`. Calls an overridable `send_to_frontend_handle`.
  * **Always** feeds outgoing bytes to the **Buffer** (`await buffer.feed(data)`) before dispatching to registered `on_send_to_frontend` callbacks.
* Wires **callbacks**: `on_send_to_frontend`, `on_receive_from_frontend`, `on_shutdown`, `on_set_terminal_title`.
* Owns a **Buffer** instance, created from the context’s `scrollback_buffer_uri` via `buffer_from_uri(...)`.
* Exposes **screen helpers** backed by the Buffer:

  * `get_terminal_buffer()` → bytes snapshot (after optional EOL conversion).
  * `get_terminal_cursor_position()` → `(row, col)`.
  * `set_terminal_size(...)` → delegates to the Buffer.
  * `update_terminal_metadata({...})` → merges per-client sizes and applies the *smallest* rows/cols.
* Provides a **file-like** handle (`filehandle()`) via `VirtualIO` so libraries like `rich` can write colored output to the interface.

**Transport examples:**

* `SocketInterface` opens an asyncio TCP stream, reads in a background task, and echoes user input locally while writing to the socket.
* `SecureSocketInterface` does the same over TLS; its scheme is registered with a **custom context class** (`SecureSocketConfig`) to accept a `create_ssl_context` callable.
* `FunctionInterface` runs your function in a thread; it offers `print()`, `input()`, `getpass()` built on internal queues and capture modes.

**Discovery / plugins:**

* New schemes register with `@register_scheme("myscheme", context_class=...)`.
* Or ship via **entry points** (`sioba.interface`)—loaded by `interface_from_uri("myscheme://...")`.

---

### 2 Buffer (screen/scrollback model)

**Where it lives:** `sioba.buffer.base.Buffer` (base) with two built-ins:

* `LineBuffer` (`sioba.buffer.line`, URI: `line://`) – minimal, newline-split lines.
* `TerminalBuffer` (`sioba.buffer.terminal`, URI: `terminal://`) – ANSI/VT handling via **pyte**.

**What it does:**

* Receives every **outgoing** byte stream from the Interface (`feed(data)`) and updates a persistent view of the screen.
* Maintains **scrollback** bounded by `context.scrollback_buffer_size` (+rows for the line buffer).
* Provides `dump_screen_state()` to serialize the view (used by `Interface.get_terminal_buffer()`).

* `TerminalBuffer` is based upon pyte to provide a terminal code aware buffer.
  * It overrides `set_title` to call `interface.set_terminal_title(...)`, which updates `context.title` and fires title callbacks.
  * Tracks **cursor position** and **title** and writes these into the shared **Context**:
  * Responds to window **resize**: `set_terminal_size(rows, cols, ...)`.

**Discovery / plugins:**

* New buffers register with `@register_buffer("mybuffer")` or via entry points under `sioba.buffer`.
* Selected by the context’s `scrollback_buffer_uri` and created through `buffer_from_uri("terminal://", interface=..., ...)`.

---

### 3 InterfaceContext (shared config + runtime state)

**Where it lives:** `sioba.context.InterfaceContext` (a dataclass).

**How it’s created:**

* From a URI: `InterfaceContext.from_uri("tcp://host:1234?rows=52&cols=100")`
* Or filled with defaults: `InterfaceContext.with_defaults(...)`

**What it holds:**

* **Connection/identity**: `uri, scheme, host, port, username, password, query, extra_params`.
* **Terminal geometry & behavior**: `rows, cols, encoding, convertEol, auto_shutdown`.
* **Buffer config**: `scrollback_buffer_uri` (default `"terminal://"`), `scrollback_buffer_size` (default `10000`).
* **Runtime metadata** written by buffers: `cursor_row`, `cursor_col`, `title`.

**Type-aware URI parsing:**

* Query params are cast to the right types (int/bool/etc.) via `cast_str_to_type`.
* `update()`, `copy()`, and `asdict()` help compose and inspect context instances.

**Per-scheme context:**

* An Interface can declare a specialized `context_class` (e.g., `SecureSocketConfig` for SSL) when registering the scheme; `interface_from_uri` uses it to build the context from the URI.

---

## Data flow (two directions)

### 1) Frontend → Interface (user input)

```
bytes from UI
   └─► Interface.receive_from_frontend(...)
        ├─ if convertEol: normalize CR/LF to '\n'
        ├─ call receive_from_frontend_handle(...)  # transport-specific
        └─ fire on_receive_from_frontend callbacks
```

* Example behaviors:

  * `SocketInterface`: writes to the socket (and locally echoes).
  * `FunctionInterface`: parses input by line / control chars (Enter, Ctrl-C, Backspace) and pushes through its queues.

### 2) Transport/app → Interface → Buffer → UI (output)

```
producer (socket read, function print)
   └─► Interface.send_to_frontend(data)
        ├─ if convertEol: '\n' → '\r\n'
        ├─ send_to_frontend_handle(...)   # optional, per interface
        ├─ Buffer.feed(data)              # updates scrollback, cursor, title
        └─ fire on_send_to_frontend callbacks (UI emit)
```

* Because **Buffer.feed** sits in the send path, the UI’s **screen snapshot** and **cursor/title** are always consistent with what was emitted.

---

## Lifecycle & sizing

* `await interface.start()` transitions to **STARTED** and lets the concrete interface initialize its tasks/threads (e.g., open sockets, start read loop, spawn function thread).
* `await interface.shutdown()` runs `shutdown_handle()`, switches to **SHUTDOWN**, then notifies `on_shutdown` callbacks.
* UI can call `update_terminal_metadata({"rows": R, "cols": C}, client_id=...)`. The Interface chooses the **smallest** rows/cols across all clients (tmux-like behavior) and updates the Buffer via `set_terminal_size(...)`.

---

## Extending: new Interfaces & Buffers

* **New transport**: subclass `Interface`, implement `start_interface`, `receive_from_frontend_handle`, optional `send_to_frontend_handle`/`shutdown_handle`, then `@register_scheme("yours")` (optionally with a custom `context_class`).
* **New buffer**: subclass `Buffer`, implement `initialize`, `feed`, `dump_screen_state`, and optional `set_terminal_size`, then `@register_buffer("yours")`.
* **Plugin packaging**: expose classes through entry points `sioba.interface` or `sioba.buffer` so `interface_from_uri(...)` / `buffer_from_uri(...)` can discover them dynamically.

Absolutely—here’s a focused “how-to extend sioba” that shows subclassing, decorators, entry points, and how `InterfaceContext.from_uri()` is used under the hood to create instances.

---

### How discovery works (registry + entry points)

* At import time, using the decorators:

  * `@register_scheme("name", context_class=...)` adds an `Interface` subclass to the in-process registry.
  * `@register_buffer("name")` adds a `Buffer` subclass to the buffer registry.

* Lazy discovery via **entry points** (recommended for plugins):

  * If a scheme/buffer isn’t already in the registry, `interface_from_uri` / `buffer_from_uri` will look up the relevant entry point group and `ep.load()` the class:

    * Interfaces: group **`sioba.interface`**
    * Buffers: group **`sioba.buffer`**

This means your plugin can be installed as a separate package and only loaded on demand when a user calls `interface_from_uri("yourscheme://...")` or selects your buffer via `scrollback_buffer_uri="yourbuffer://"`.

---

### The creation pipeline (what happens under the hood)

When you call:

```python
iface = interface_from_uri("myscheme://host:1234?rows=40&cols=100", my_flag=True)
```

1. `interface_from_uri` parses the URI (`urlparse`), extracts the **scheme** (`myscheme`).
2. If not already registered, it searches entry points in group `sioba.interface`, loads the matching class, verifies it subclasses `Interface`, and caches it in the registry.
3. It picks a **context class**:

   * If your handler set `context_class` in `@register_scheme(..., context_class=MyContext)`, that’s used.
   * Otherwise the default `InterfaceContext` is used.
4. It builds the **context** with `context_class.from_uri(uri, **kwargs)`:

   * `from_uri` parses `host/port/query` and **casts** known fields to the right types.
   * Any extra kwargs you pass (e.g., `my_flag=True`) are merged if they match fields on the context dataclass.
   * Defaults are filled via `with_defaults(...)` (rows=24, cols=80, `convertEol=True`, `auto_shutdown=True`, `scrollback_buffer_uri="terminal://"`, etc.).
5. It constructs your `Interface` with that context and any provided callbacks.
6. Inside `Interface.__init__`, the chosen **Buffer** is created via `buffer_from_uri(context.scrollback_buffer_uri, interface=self, ...)`. If the buffer scheme isn’t registered, the loader resolves it via entry points in group `sioba.buffer`.
7. You then `await iface.start()`; your subclass’s `start_interface()` is called to actually connect/launch resources.

---

## Example 1: A custom Interface with a custom Context

### 1a) Define a context (extend `InterfaceContext`)

```python
# mypkg/myproto/context.py
from dataclasses import dataclass
from sioba import InterfaceContext

@dataclass
class MyProtoContext(InterfaceContext):
    # Parsed from URI query or kwargs in interface_from_uri(...)
    my_flag: bool = False
    timeout_ms: int = 5000
```

Notes:

* `InterfaceContext.from_uri()` will **cast** `?my_flag=true&timeout_ms=2500` to the right types.
* You get all the base fields too (`host`, `port`, `rows`, `cols`, `encoding`, `scrollback_buffer_uri`, etc.).

### 1b) Implement the Interface

```python
# mypkg/myproto/interface.py
import asyncio
from sioba.interface.base import Interface, InterfaceState, register_scheme
from .context import MyProtoContext

@register_scheme("myproto", context_class=MyProtoContext)
class MyProtoInterface(Interface):
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    _recv_task: asyncio.Task | None = None

    async def start_interface(self) -> bool:
        # Mark started (base does this as well; harmless to be explicit).
        self.state = InterfaceState.STARTED

        ctx: MyProtoContext = self.context  # typed context
        # Use URI parts parsed into context (e.g., host/port) and custom fields:
        self.reader, self.writer = await asyncio.open_connection(ctx.host, ctx.port)
        self._recv_task = asyncio.create_task(self._receive_loop(timeout_ms=ctx.timeout_ms))
        return True

    async def _receive_loop(self, timeout_ms: int):
        try:
            while self.state == InterfaceState.STARTED:
                data = await asyncio.wait_for(self.reader.read(4096), timeout_ms/1000)
                if not data:
                    break
                await self.send_to_frontend(data)   # feeds Buffer, fires callbacks
        except asyncio.TimeoutError:
            # Optional: emit a heartbeat or warning
            pass
        finally:
            await self.shutdown()

    async def receive_from_frontend_handle(self, data: bytes) -> None:
        # normalize CR/LF already handled; you may add protocol framing here:
        if self.writer:
            self.writer.write(data)
            await self.writer.drain()
            # Local echo if you want (SocketInterface does this):
            await self.send_to_frontend(data)

    async def shutdown_handle(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except ConnectionAbortedError:
                pass
```

### 1c) Use it

```python
from sioba import interface_from_uri

iface = await interface_from_uri(
    "myproto://example.com:9000?rows=40&cols=100&my_flag=true&timeout_ms=2000"
).start()

# interact
await iface.receive_from_frontend(b"HELLO\n")
buf = iface.get_terminal_buffer()
await iface.shutdown()
```

Everything above mirrors the built-in `SocketInterface`/`SecureSocketInterface` pattern, but with your own knobs on the context.

---

## Example 2: A custom Buffer

A buffer transforms **outgoing** bytes into a durable “screen” snapshot and updates cursor/title on the shared Context.

```python
# mypkg/mybuffer/buffer.py
from sioba.buffer.base import Buffer, register_buffer

@register_buffer("ring")
class RingBuffer(Buffer):
    """
    A tiny byte ring buffer (no ANSI processing).
    """
    def initialize(self, **extra):
        self.capacity = int(extra.get("capacity", 8192))
        self._buf = bytearray()

    async def feed(self, data: bytes) -> None:
        # Called for every Interface.send_to_frontend(data)
        self._buf.extend(data)
        if len(self._buf) > self.capacity:
            # drop oldest
            drop = len(self._buf) - self.capacity
            del self._buf[:drop]

        # Maintain a “cursor” approximation on the shared context
        # (optional but consistent with built-ins):
        text = bytes(self._buf).split(b"\n")[-1]
        col = len(text)
        # rows/cols are bounds in Context; keep within them:
        rows = self.interface.context.rows
        cols = self.interface.context.cols
        row = min(rows - 1, len(bytes(self._buf).splitlines()))
        col = min(cols - 1, col)
        self.interface.context.cursor_row = row
        self.interface.context.cursor_col = col

    def dump_screen_state(self) -> bytes:
        return bytes(self._buf)

    def set_terminal_size(self, rows: int, cols: int, xpix: int = 0, ypix: int = 0) -> None:
        # Nothing needed for a raw ring buffer; could trim to new “visible” size if desired.
        pass
```

Use it by pointing a context at `ring://`:

```python
from sioba import Interface, InterfaceContext

ctx = InterfaceContext.with_defaults(
    title="RB",
    rows=10, cols=40,
    scrollback_buffer_uri="ring://",    # uses our RingBuffer
)
iface = Interface(context=ctx)
await iface.start()
await iface.send_to_frontend(b"hello\nworld\n")
print(iface.get_terminal_buffer())     # bytes from our ring
await iface.shutdown()
```

> Internals: `Interface.__init__` calls `buffer_from_uri(context.scrollback_buffer_uri, interface=self, on_set_terminal_title=self.set_terminal_title)`. If your buffer scheme isn’t in the process registry, it’s resolved via the `sioba.buffer` entry point group.

---

## Example 3: Packaging as a plugin with entry points

To make your `myproto` interface and `ring` buffer discoverable **without importing your module explicitly**, expose them via entry points in your package’s `pyproject.toml`:

```toml
[project]
name = "mypkg-sioba-plugins"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["sioba>=0.3"]  # pin to your desired version

[project.entry-points]
"sioba.interface".myproto = "mypkg.myproto.interface:MyProtoInterface"
"sioba.buffer".ring = "mypkg.mybuffer.buffer:RingBuffer"
```

Now, anywhere `sioba` is installed:

```python
from sioba import interface_from_uri

# "myproto" is lazily discovered via entry points:
iface = await interface_from_uri("myproto://example.com:9000?rows=40&cols=100").start()
```

No need to import `mypkg.myproto.interface` manually; `interface_from_uri` will load it on demand.

---

## Tips & conventions (from sioba internals)

* **Context casting**: add fields to your custom context (dataclass) and pass values via URI query (`?flag=true`) or kwargs to `interface_from_uri(...)`. `from_uri` will **cast** strings to the declared types (int/bool/float).
* **EOL policy**: `Interface.receive_from_frontend` normalizes CR/LF to `\n`; `send_to_frontend` converts `\n` to `\r\n` if `convertEol=True`. Your transport code should assume normalized `\n` on input and rely on `send_to_frontend` for outbound normalization.
* **Screen & title**:

  * Buffers should call/trigger `interface.set_terminal_title(title)` when titles change (the terminal buffer does this inside `EventsScreen.set_title`).
  * Buffers should update `context.cursor_row/col` so `Interface.get_terminal_cursor_position()` remains accurate.
* **Lifecycle**: override `start_interface()` and `shutdown_handle()` for resources; always handle cancellation and closed streams cleanly.
* **Async vs thread**: if you need sync code, see `FunctionInterface` for a queue-driven pattern and capture modes (`ECHO`, `DISCARD`, `INPUT`, `GETPASS`).

---

### End-to-end checklist for a new scheme

1. Create a `@dataclass class MyContext(InterfaceContext)` with any extra fields you need.
2. Implement `@register_scheme("myscheme", context_class=MyContext)` on your subclass of `Interface`.
3. (Optional) Implement a custom buffer and `@register_buffer("mybuffer")`.
4. Package both via `pyproject.toml` entry points:

   * `"sioba.interface".myscheme = "pkg.mod:Class"`
   * `"sioba.buffer".mybuffer = "pkg.mod:Class"`
5. Use it:

   ```python
   await interface_from_uri("myscheme://host:1234?rows=40&my_flag=true").start()
   ```

That’s it—your interface/buffer will be discoverable and type-safe, created with a fully-populated `InterfaceContext` derived from the URI plus any kwargs you pass.


---

## A few concrete behaviors tied together

* **EOL policy** is centralized:

  * Incoming keystrokes normalized (`\r\n` / `\r` → `\n`) before reaching a transport.
  * Outgoing data normalized (`\n` → `\r\n`) before it hits the Buffer/UI.
* **Title changes** originate in the **Buffer** (e.g., `TerminalBuffer`’s `EventsScreen.set_title`) and propagate up through `Interface.set_terminal_title(...)` to the **Context** and any registered callbacks.
* **Cursor position** is a **Context** field (`cursor_row`, `cursor_col`) maintained by the Buffer (via `EventsCursor` in the terminal buffer, or computed in the line buffer).
* **Rich integration** uses `Interface.filehandle()` (a `TextIOBase` that sets `isatty=True`) so things like `rich.Console(file=...)` print straight into the Interface; internally that just calls `send_to_frontend(...)`, which flows through the Buffer and callbacks.

---

That’s the architectural core: **Interface** moves bytes and orchestrates the session, **Buffer** turns bytes into a durable screen model (plus cursor/title), and **Context** binds configuration and runtime metadata that both of the others read and write.


---

## Usage

### 1) `FunctionInterface` (interactive script)

```python
import asyncio, time
from sioba import FunctionInterface, Interface

def app(ui: FunctionInterface):
    ui.print("Welcome!")
    name = ui.input("What's your name? ")
    ui.print(f"Hello, {name}!")
    hidden = ui.getpass("Enter your hidden word: ")
    ui.print(f"Length noted: {len(hidden)}")
    time.sleep(0.2)

async def main():
    f = FunctionInterface(app)
    await f.start()
    # Simulate terminal input for the two prompts:
    await f.receive_from_frontend(b"Mochi\r\n")
    await f.receive_from_frontend(b"Wasabi\r\n")
    # Read what the function printed to the screen:
    print(f.get_terminal_buffer().decode("utf-8", errors="replace"))
    await f.shutdown()

asyncio.run(main())
```

* Input capture modes (internal): `ECHO`, `DISCARD`, `INPUT`, `GETPASS`. The prompts above demonstrate `INPUT` and `GETPASS`.

### 2) TCP / SSL sockets

```python
import asyncio, ssl
from sioba import interface_from_uri, SocketInterface, SecureSocketInterface

async def tcp_demo():
    sock = await interface_from_uri("tcp://localhost:12345").start()
    out = []
    sock.on_send_to_frontend(lambda _i, d: out.append(d))
    await sock.receive_from_frontend(b"HELLO\n")
    await asyncio.sleep(0.1)
    await sock.shutdown()

async def ssl_demo():
    ctx = ssl._create_unverified_context()  # example from tests
    ssli = await interface_from_uri(
        "ssl://localhost:12345",
        create_ssl_context=lambda _cfg: ctx,  # SecureSocketConfig hook
    ).start()
    await ssli.shutdown()
```

### 3) Choosing a buffer & reading state

```python
from sioba import Interface, InterfaceContext

ctx = InterfaceContext.with_defaults(
    title="Demo",
    scrollback_buffer_uri="terminal://",   # or "line://"
    rows=5, cols=80,
)
iface = Interface(context=ctx)
await iface.start()
await iface.send_to_frontend(b"Rich text and ANSI go here\n")
print(iface.get_terminal_buffer())         # bytes snapshot
await iface.shutdown()
```

### 4) Registering a custom scheme / buffer

```python
from sioba import register_scheme, register_buffer
from sioba.interface.base import Interface

@register_scheme("myproto")
class MyProto(Interface):
    async def receive_from_frontend_handle(self, data: bytes):
        await self.send_to_frontend(b"ok:" + data)

@register_buffer("dummy")
class DummyBuffer:
    pass
```

---

## API Highlights

* `sioba.Interface` — base class: lifecycle, callbacks, buffer, screen helpers.
* `sioba.InterfaceContext` — dataclass; parse/update/copy context; `from_uri`, `with_defaults`, `asdict`, `get`.
* `sioba.interface_from_uri(uri, **kw)` — build interface from `scheme://…` (+ optional context overrides).
* `sioba.register_scheme(*schemes, context_class=None)` / `sioba.list_schemes()` — plugin registration & discovery.
* `sioba.FunctionInterface` — wrap a Python function with `print()`, `input()`, `getpass()` over an interface.
* `sioba.EchoInterface` — `echo://` passthrough for testing.
* `sioba.SocketInterface` — `tcp://host:port` using asyncio streams.
* `sioba.SecureSocketInterface` — `ssl://host:port` with optional `create_ssl_context`.
* `sioba.UDPInterface` — `udp://host:port` for UDP streams.
* `sioba.buffer_from_uri(uri, **kw)` / `sioba.register_buffer(*names)` / `sioba.list_buffer_schemes()` — buffer plugins.
* `sioba.errors` — `InterfaceNotStarted`, `InterfaceShutdown`, `TerminalClosedError`, etc.
* `sioba.Interface.filehandle()` — TTY-like stream (used by `rich.Console(file=...)`).

---

## CLI

> TODO: No CLI entry points found; add one if a command-line tool is intended.

---

## Security & Limits

* `tcp://`, `udp://`, and `ssl://` interfaces **open network connections**; user input is echoed locally and forwarded to the remote server.
* `SecureSocketInterface` accepts a custom SSL context; using an “unverified” context (as in tests) **disables certificate verification**—unsafe for production.
* `FunctionInterface` runs your function in a **separate thread** and can execute arbitrary code; there is no sandboxing.

---

## Compatibility & Requirements

* Python **≥ 3.10**.
* Tested interfaces/buffers use `asyncio`, `pyte`, `rich`, `loguru`, `janus`.
* Defaults: `convertEol=True` (outgoing `\n` → `\r\n`), encoding `utf-8`.

---

## Contributing

```bash
# clone
git clone https://github.com/amimoto/sioba
cd sioba

# (dev) install with uv
uv sync

# run tests
uv run pytest -q
# or, if not using uv:
pytest -q
```

---

## License

sioba is available under the MIT license. See the LICENSE file for more info.

---
