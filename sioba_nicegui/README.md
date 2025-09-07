# sioba_nicegui — NiceGUI + XTerm.js terminal for sioba

**sioba_nicegui** is a thin, batteries-included bridge between
[XTerm.js] and [NiceGUI], wired to the **sioba** IO abstraction.
It lets you drop a web terminal into any NiceGUI app and connect it to any
`sioba.Interface` (echo, TCP/SSL sockets, Python functions, local shells, etc.).

- **XTerm.js UI**: vendored xterm with resize, cursor, theme & option controls
- **sioba backends**: use any `Interface` (e.g. `echo://`, `tcp://`, `ssl://`, `exec://`)
- **Auto screen sync**: pulls scrollback/cursor from the interface’s buffer
- **Multi-client aware**: resizes to the smallest connected client (tmux-like)
- **Plug-and-play**: `XTermInterface.from_uri("…")` → it starts and just works

> Want a web shell? Add the separate plugin **sioba_subprocess** and use `exec://`.

---

## Install

```bash
pip install sioba_nicegui sioba
# optional, for local shells via exec://
pip install sioba_subprocess
# or with uv:
uv pip install sioba_nicegui sioba sioba_subprocess
```

* Python **≥ 3.10**
* NiceGUI **≥ 2.23.0**

---

## TL;DR (three ways)

### 1) Echo demo (no backend needed)

```python
from nicegui import ui
from sioba_nicegui.xterm import XTermInterface

term = XTermInterface.from_uri('echo://').classes('w-full h-[70vh]')

ui.run(title='Echo', port=9000, host='0.0.0.0', show=True)
```

### 2) Function interface (prompt/print/input/getpass)

```python
from nicegui import ui
from sioba import FunctionInterface
from sioba_nicegui.xterm import XTermInterface
import time, datetime

def app(ui_if: FunctionInterface):
    ui_if.print('[blue]Hello![/blue]')
    name = ui_if.input("What's your name? ")
    ui_if.print(f'Hello, {name}!')
    secret = ui_if.getpass('Secret: ')
    ui_if.print(f'({len(secret)} chars)')
    while True:
        time.sleep(1)
        ui_if.print(f'It is {datetime.datetime.now()}')

term = XTermInterface(FunctionInterface(app)).classes('w-full h-[70vh]')
ui.run(title='Function Interface', port=9000, host='0.0.0.0', show=True)
```

### 3) Local shell (via **sioba\_subprocess**)

```python
from nicegui import ui
from sioba_nicegui.xterm import XTermInterface

# POSIX: bash; Windows: see notes below for full path
term = XTermInterface.from_uri('exec:///bin/bash').classes('w-full h-[70vh]')

ui.run(title='Web Shell', port=9000, host='0.0.0.0', show=True)
```

---

## Concepts & data flow

```
(Keystrokes in browser)
   └─► XTerm.js (NiceGUI component)
         └─► XTermInterface.on('data') → base64 decode
               └─► sioba.Interface.receive_from_frontend(bytes)
                     .. your transport (socket, subprocess, function, …) ..
               └─► sioba.Interface.send_to_frontend(bytes)
                     └─► Buffer feeds (terminal or line) → screen & cursor
                           └─► XTermInterface writes (base64) → XTerm.js
```

* **Screen & cursor** come from the sioba buffer (`terminal://` by default).
* **Resize** events pick the smallest rows/cols across connected clients and
  call `Interface.update_terminal_metadata(...)` (tmux-like behavior).
* **Lifecycle**: `XTermInterface` starts the interface on client connect and
  writes `[Interface Exited]` when it shuts down.

---

## API overview

### XTerm (standalone terminal widget)

```python
from sioba_nicegui.xterm import XTerm, TerminalContext, TerminalState

term = XTerm(
    value='',                              # initial text (optional)
    context=TerminalContext(               # XTerm.js options (subset)
        rows=24, cols=80, fontSize=14,
        cursorBlink=True,
        theme={'background': '#000000', 'foreground': '#FFFFFF'},
    ),
    on_close=lambda t: print('closed!'),
).classes('w-full h-[60vh]')

# write bytes to the terminal
term.write(b'Hello, world!\n')

# focus & cursor helpers
term.focus()
term.set_cursor_location(row=0, col=0)
```

Useful attributes/methods:

* `term.state` → `INITIALIZING | CONNECTED | DISCONNECTED | CLOSED`
* `term.context` → `TerminalContext` (see below)
* `term.write(bytes)` → append bytes to terminal
* `term.set_option(name, value)` and `term.sync_context()` to push options
* `term.on(event, handler)` → subscribe to frontend events (`data`, `resize`, `render`, …)

### XTermInterface (terminal + a sioba.Interface)

```python
from sioba_nicegui.xterm import XTermInterface
from sioba import Interface, interface_from_uri

# Option A: create from URI (recommended)
term = XTermInterface.from_uri('tcp://example.com:80')

# Option B: pass an Interface instance
iface: Interface = interface_from_uri('ssl://example.com:443')
term = XTermInterface(iface)

# later (rare) – attach a different interface
# term.connect_interface(other_iface)
```

* `from_uri(uri, **callbacks)` resolves/constructs a `sioba.Interface`
  and returns an `XTermInterface`.
  (The return type is the **terminal element**, not a tuple.)
* On connect:

  * Starts the interface (`await interface.start()`).
  * `sync_with_frontend()` transfers current screen & cursor.
  * `sync_context()` applies terminal options to the JS side.
* On delete: reference count on the interface is decremented; if `auto_shutdown`
  is enabled, the interface will shut down when no views reference it.

### TerminalContext (selected XTerm.js options)

`TerminalContext` mirrors a practical subset of XTerm’s options. Common ones:

* `rows`, `cols`, `term_type`, `scrollback`, `encoding`, `convertEol`
* `cursorBlink`, `cursorStyle`, `fontFamily`, `fontSize`, `theme`, `windowsMode`, …

Use `XTerm(context=...)` or `XTermInterface(..., context=...)`.
Note: when you attach an interface, `XTermInterface` merges the interface’s
context (e.g., `rows/cols/encoding/convertEol`) into the terminal context.

---

## Recipes

### Custom theme & options

```python
from sioba_nicegui.xterm import XTermInterface, TerminalContext

ctx = TerminalContext(
    fontFamily='JetBrains Mono, monospace',
    fontSize=16,
    cursorBlink=True,
    theme={'background': '#0b1021', 'foreground': '#e0e2f4'},
    scrollback=2000,
)

term = XTermInterface.from_uri('echo://', context=ctx).classes('w-full h-[70vh]')
```

### TCP/SSL sockets

```python
from nicegui import ui
from sioba_nicegui.xterm import XTermInterface

term = XTermInterface.from_uri('tcp://example.com:80').classes('w-full h-[60vh]')
ui.run(port=9000, host='0.0.0.0', show=True)

# or TLS (with a custom SSL context inside sioba.SecureSocketInterface)
```

### Session-per-page (multiple users)

```python
from nicegui import ui, Client
from sioba_nicegui.xterm import XTermInterface

@ui.page('/')
async def index(client: Client):
    term = XTermInterface.from_uri('echo://').classes('w-full h-[60vh]')
    term.interface.on_receive_from_frontend(lambda i, d: print('RX:', d))

ui.run(port=9000, host='0.0.0.0', show=True)
```

### Your own transport

```python
from sioba import Interface, register_scheme
from sioba_nicegui.xterm import XTermInterface

@register_scheme('custom')
class CustomInterface(Interface):
    async def receive_from_frontend(self, data: bytes):
        await self.send_to_frontend(b'You sent: ' + data + b'\r\n')

term = XTermInterface.from_uri('custom://').classes('w-full h-[50vh]')
```

---

## Events (frontend → backend)

The JS component emits lots of XTerm events. The backend listens to a useful set:

* `data` → base64 keystrokes → `Interface.receive_from_frontend(bytes)`
* `resize` → `{rows, cols}` → `Interface.update_terminal_metadata(...)`
* `render`, `mount` → connection bookkeeping

You can subscribe yourself:

```python
term.on('resize', lambda e: print('new size', e.args))
term.on('data',   lambda e: print('keys (base64):', e.args[0]))
```

---

## Included examples

* `examples/echo-interface-auto-index-page.py`
* `examples/echo-interface-sessions.py`
* `examples/function-interface-auto-index-page.py`
* `examples/function-interface-sessions.py`
* `examples/socket-interface-auto-index-page.py`
* `examples/ssl-socket-interface-auto-index-page.py`
* `examples/custom-interface-auto-index-page.py`
* `examples/shell-interface-auto-index-page.py`  *(requires `sioba_subprocess`)*

Run them with `uv run <file>.py` or `python <file>.py`.

---

## Notes & limitations

* **Flow control**: not implemented on the JS side yet (see xterm flow-control guide).
* **Initial refresh**: `sync_with_frontend()` pushes the buffer & cursor to the JS terminal;
  subsequent updates flow live via callbacks.
* **Newlines & encoding**: governed by the interface’s context
  (`convertEol=True` by default; encoding `utf-8`).
* **Windows exec paths**: prefer absolute form
  `exec:///C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`.

---

## Contributing

PRs and issues welcome. Typical workflow:

```bash
uv sync
uv run pytest -q
```

---

## License

MIT — see `LICENSE`.

---

[XTerm.js]: https://xtermjs.org/
[NiceGUI]: https://nicegui.io/

