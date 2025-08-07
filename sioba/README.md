# SIOba

*“Simple I/O Backend Abstractions” – a mouth‑filling phrase that we noodle‑ify into ****sioba****.* Think of it as a **virtual TTY**: a Python purebred that ferries bytes between **back‑ends** (functions, sockets, subprocesses, serial ports…) and **front‑ends** (NiceGUI + xterm.js, Rich TUI, tests) while keeping escape codes, cursor state, and scroll‑back impeccably civilised.

> **TL;DR** –– sioba gives any stream‑spewing gizmo a proper terminal wrapper, discoverable by URI schemes and swappable at run‑time.

---

## Contents

1. Why bother?
2. Architectural bird’s‑eye
3. Interfaces (I/O gatekeepers)
4. Buffers (scroll‑back archivists)
5. Inside the virtual TTY
6. Installation & Quick‑starts
7. InterfaceContext & configuration
8. Error handling & lifecycle
9. Extending sioba (plugins)
10. Testing & CI
11. Roadmap & contribution notes

---

## 1 · Why bother?

* **Unified API** – one `Interface`, many transports.
* **Entry‑point plugins** – new back‑ends or buffers appear after a simple `pip install mypkg‑sioba‑serial`.
* **Web‑ready** – born for `nicegui` + `xterm.js`, yet equally content in curses or `rich.console`.
* **Vanilla Python** – no C‑extensions; plays nicely on Windows, macOS, Linux, even Pyodide.
* **Portable tests** – mock terminals without spawning real PTYs; CI stays flake‑free.
* **Observability** – built‑in `loguru` hooks and a `SIOBA_DEBUG=*` env flag spray helpful breadcrumbs.

---

## 2 · Architectural bird’s‑eye

```text
┌────────────── Front‑end ───────────────┐
│  NiceGUI‑XTerm │ Rich Console │ pytest │
└────────────────────────────────────────┘
              ▲   ▲        ▲
              │   │ bytes  │ events (resize, focus)
              │   │        │
     send_to_frontend   receive_from_frontend
              │   │
        ┌─────┴───┴─────┐        «virtual‑tty boundary»
        │   Interface   │  ⇦ context, hooks, lifecycle
        └─────┬───┬─────┘
              │   └──► **Buffer** – keeps screen or lines tidy
              │         • TerminalBuffer (pyte)  
              │         • LineBuffer  
              │         • YourCustomBuffer
              │
              └────► **Backend** via concrete _Interface_
                       • Function threads           (function://)  
                       • TCP / TLS sockets          (tcp://, ssl://)  
                       • Echo for smoke‑tests       (echo://)  
                       • Soon: serial://, pty://, ws://, ssh://
```

Each `Interface` owns one `Buffer` plus zero‑or‑more UI clients.  Cursor position, rows, cols are negotiated to the **smallest** attached terminal (à la tmux) to avoid accidental truncation.

---

## 3 · Interfaces 🛂

Registered through the \`\` entry‑point group:

| **Scheme**       | **Class**               | **Purpose**                                  |
| ---------------- | ----------------------- | -------------------------------------------- |
| `echo://`        | `EchoInterface`         | Bytes go in ⇢ same bytes out (sanity checks) |
| `tcp://host:80`  | `SocketInterface`       | Raw TCP client, line endings normalised      |
| `ssl://host:443` | `SecureSocketInterface` | TCP + TLS with optional custom `SSLContext`  |
| *direct*         | `FunctionInterface`     | Spins a Python callable in its own thread    |

### Mini‑sample: FunctionInterface

```python
from sioba import FunctionInterface

async def handler():
    iface = await FunctionInterface(lambda i: i.print("🍜 Noodles!")).start()
    iface.on_send_to_frontend(lambda _, d: print(d.decode(), end=""))
```

### Rolling your own

```python
from sioba import Interface, register_scheme

@register_scheme("serial")
class SerialInterface(Interface):
    async def start_interface(self):
        import serial, asyncio
        self.ser = serial.Serial("/dev/ttyUSB0", 115200)
        asyncio.create_task(self._rx())
        return True

    async def _rx(self):
        while self.is_running():
            data = self.ser.read(self.ser.in_waiting or 1)
            await self.send_to_frontend(data)
```

Expose it:

```toml
[project.entry-points."sioba.interface"]
serial = "mypkg.serial:SerialInterface"
```

---

## 4 · Buffers 🗄

| **Scheme**    | **Class**        | **Highlights**                                   |
| ------------- | ---------------- | ------------------------------------------------ |
| `none://`     | `Buffer`         | No persistence; pure‑stream pass‑through         |
| `line://`     | `LineBuffer`     | FIFO of decoded lines; trims head when full      |
| `terminal://` | `TerminalBuffer` | Full VT100 emulation via **pyte** w/ scroll‑back |

Create your own (Markdown prettifier, perhaps?):

```python
@register_buffer("markdown")
class MarkdownBuffer(Buffer):
    async def feed(self, data: bytes):
        html = markdown2.markdown(data.decode())
        self.rendered = html.encode()
```

---

## 5 · Inside the virtual TTY

* **pyte** interprets escape sequences, updates a `Screen` buffer, and tracks cursor.
* `EventsCursor` subclasses `pyte.Cursor` so row/col live‑update `InterfaceContext`.
* Scroll‑back capped by `scrollback_buffer_size` (default: 10 k lines + current rows).
* `VirtualIO` wraps `Interface.send_to_frontend` to masquerade as a colour‑capable file handle, allowing **Rich**, **prompt‑toolkit**, or `print()` to write without caring about async.

### Performance note

For hefty data (e.g., `tail -f` on a 1 MB/s log), throughput tops 15 MB/s on CPython 3.12; adjust `pyte` `Screen.dirty` pruning to trade memory for speed.

---

## 6 · Installation & Quick‑starts

### Stable release

```bash
pip install sioba              # pulls dependencies: pyte, nicegui, loguru, janus, rich
```

### Bleeding edge (editable)

```bash
git clone https://github.com/amimoto/sioba.git
cd sioba && pdm install -G :all
```

### One‑liner echo demo

```python
import asyncio, sioba
asyncio.run(
    sioba.interface_from_uri("echo://").start()
)
```

### NiceGUI integration (complete)

See `examples/nicegui_xterm.py` for a 40‑line web terminal server.

---

## 7 · InterfaceContext & friends

`InterfaceContext` is a dataclass that captures URI parts **plus** terminal metadata:

```python
ctx = InterfaceContext.from_uri(
    "tcp://chat.openai.com:443?rows=40&cols=120&extra_param=42",
    auto_shutdown=False,
)
print(ctx.cols)        # 120
print(ctx.extra_params)  # {"extra_param": "42"}
```

Fields worth tweaking:

* `rows`, `cols` – initial geometry.
* `convertEol` – auto‑transmute `\n` ⇢ `\r\n` on output.
* `auto_shutdown` – if no UI references remain, the Interface commits seppuku.
* `scrollback_buffer_uri` & `_size` – choose buffer strategy per Interface.

---

## 8 · Error handling & lifecycle

| Exception             | When it triggers                    | Typical fix                        |
| --------------------- | ----------------------------------- | ---------------------------------- |
| `InterfaceNotStarted` | `send_to_frontend` before `start()` | Await `iface.start()` first        |
| `InterfaceShutdown`   | Any I/O after `shutdown()` complete | Re‑connect or create new Interface |
| `TerminalClosedError` | Front‑end vanished mid‑write        | Check client connection state      |

Lifecycle states live in `InterfaceState { INITIALIZED, STARTED, SHUTDOWN }`.  A graceful shutdown:

```python
await iface.shutdown()  # sends Ctrl‑C to task queue, drains, closes
```

---

## 9 · Extending sioba (plugins)

1. Subclass `Interface` **or** `Buffer`.
2. Decorate with `@register_scheme()` or `@register_buffer()`.
3. Export via `pyproject.toml` entry‑point.
4. Publish to PyPI – sequestered environments pick it up at import time (thanks, `importlib.metadata`).

> **Note**: Plugins load lazily; importing `sioba` never imports all extras unless requested.

---

## 10 · Testing & Continuous Integration

* Suite lives under `tests/` and covers interfaces, buffers, context parsing, and pyte quirks.
* Run locally: `pytest -q`.
* GitHub Actions matrix: 3.9 → 3.13.

Need coverage reports? `pytest --cov sioba -q` already wired.

---

## 11 · Roadmap & contributions

* **SerialInterface** and **WebSocketInterface** prototypes.
* **PTY spawn** (`/bin/bash` in NiceGUI) using `ptyprocess` fallback on Windows (WinPTY).
* **Binary buffers** (no UTF‑8 assumption).
* **Typed events**: resize, focus, clipboard, drag‑drop.

Pull requests are ramen‑welcome – please:

1. Fork → feature branch.
2. Run `pdm run lint && pytest`.
3. Add yourself to AUTHORS if more than five lines changed.

Licensed under **MIT‑0** (zero‑clause).  Issues? Wag them at [https://github.com/amimoto/sioba](https://github.com/amimoto/sioba).
