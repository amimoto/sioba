# sioba_subprocess — subprocess/PTY interface for sioba

**sioba_subprocess** adds an `exec://` interface to [sioba](https://github.com/amimoto/sioba) so you can drive a local shell or program as an interactive terminal session behind the same async `Interface` API (screen buffer, cursor, callbacks, etc.).

- **POSIX**: forks a child attached to a PTY (via `pty`, `subprocess`, `termios`) and mirrors stdout/stderr to the sioba buffer; window size changes are propagated with `ioctl(TIOCSWINSZ)` + `SIGWINCH`.
- **Windows**: uses **pywinpty** to spawn and attach to a console app (e.g., `cmd.exe` or PowerShell), forwarding I/O to sioba’s buffer.

> The package is discovered by sioba via entry point:  
> `"sioba.interface".exec = "sioba_subprocess.interface:ShellInterface"`

---

## Installation

```bash
# sioba core + this plugin
pip install sioba sioba_subprocess
# or with uv
uv pip install sioba sioba_subprocess
```

* Python **≥ 3.10**
* Windows: `pywinpty` installs automatically via extras.

---

## Quickstart

### Start your default shell

```
import asyncio
from sioba import interface_from_uri

async def main():
    # POSIX default: /bin/bash; Windows default: cmd.exe
    sh = await interface_from_uri("exec://").start()

    # capture everything the program prints
    screen = []
    sh.on_send_to_frontend(lambda _i, data: screen.append(data))

    # run a command
    await sh.receive_from_frontend(b"echo hello from sioba\r\n")
    await asyncio.sleep(0.2)  # give the subprocess a moment

    print(b"".join(screen).decode("utf-8", errors="replace"))
    await sh.shutdown()

asyncio.run(main())
```

### Launch a specific program (absolute path)

```python
import asyncio, sys, pathlib
from sioba import interface_from_uri

async def main():
# Start an interactive Python REPL
    py = pathlib.Path(sys.executable)
    iface = await interface_from_uri(f"exec:///{py}").start()

    await iface.receive_from_frontend(b"import hashlib\n")
    await iface.receive_from_frontend(b'hashlib.md5(b\"hello world\").hexdigest()\n')
    await asyncio.sleep(0.5)

    print(iface.get_terminal_buffer().decode("utf-8", "replace"))
    await iface.receive_from_frontend(b"exit()\n")
    await asyncio.sleep(0.2)

asyncio.run(main())
```

### Pass arguments & working directory

You can pass arguments either **as kwargs** or via **query params**:

```python
# kwargs (recommended)
sh = await interface_from_uri(
    "exec:///bin/bash",
    invoke_args=["-lc", "echo $PWD && ls -1"],
    invoke_cwd="/tmp",
).start()

# or query params (repeatable ?arg=…; values are strings)
sh = await interface_from_uri("exec:///bin/bash?arg=-lc&arg=echo%20hello").start()
```

### Resizing the terminal & reading the screen

```python
# tell the interface (and the PTY/console) about UI size changes
sh.update_terminal_metadata({"rows": 40, "cols": 120})

# snapshot of what the user would see
buf = sh.get_terminal_buffer()
print(buf.decode("utf-8", "replace"))
```

---

## What you get

* **Interface**: `ShellInterface` (scheme `exec://`) — inherits sioba’s `Interface`
* **Context**: `ShellContext` (extends `InterfaceContext`)

  * `invoke_args: list[str]` — CLI args for the child process
  * `invoke_cwd: Optional[str]` — working directory for the child
* **Discovery**: installed as a sioba plugin via entry point; after installation:

```python
from sioba import list_schemes
assert "exec" in list_schemes()
```

---

## URI reference

```
exec:///<ABSOLUTE_PATH>?arg=<value>&arg=<value>&invoke_cwd=<path>
```

* **Path**: absolute path to the program. If omitted, defaults to:

  * POSIX: `/bin/bash`
  * Windows: `cmd.exe`
* **Query params**

  * `arg`: repeatable; each occurrence becomes the next CLI argument.
  * `invoke_cwd`: working directory string.
* **General sioba params** (handled by `InterfaceContext.from_uri`):

  * `rows`, `cols`, `encoding`, `convertEol`, `auto_shutdown`,
  * `scrollback_buffer_uri` (`terminal://` by default), `scrollback_buffer_size`, etc.

> **Windows path tip:** prefer `exec:///C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`
> (leading slash is stripped automatically; forward slashes are OK).

---

## Lifecycle & behavior

* `await iface.start()` spawns the child attached to a PTY/console and begins reader threads.
* **I/O**

  * `await iface.receive_from_frontend(b"...\n")` → writes to the child stdin/console.
  * Child output → `await iface.send_to_frontend(...)` → **Buffer** (ANSI aware if `terminal://`) → your callbacks.
  * End-of-line normalization honors `convertEol` (enabled by default).
* **Resize**: `update_terminal_metadata({"rows": R, "cols": C})` adjusts PTY/console size.
* **Shutdown**

  * POSIX tries `SIGTERM` on the process group, then escalates to `SIGKILL` if needed.
  * Windows terminates via pywinpty.
  * If the child exits by itself, the interface transitions to `InterfaceState.SHUTDOWN` automatically and runs `on_shutdown` hooks.

---

## Examples

### Drop into PowerShell (Windows)

```python
sh = await interface_from_uri(
    "exec:///C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
).start()
```

### Minimal echo of everything printed

```python
out = []
sh.on_send_to_frontend(lambda _i, data: out.append(data))
```

---

## Troubleshooting

* **No output?** Make sure you send a newline (`\n`) so the shell executes a line. On Windows, `convertEol=True` will handle `\r\n` vs `\n`.
* **Windows path parsing:** Use `exec:///C:/path/to/app.exe` (triple slash + absolute path with drive letter). The implementation strips the leading `/` on Windows.
* **Separate stdout/stderr?** Not currently split — both are merged into the PTY stream (see tests).
  *TODO:* consider optional channels for stderr.

---

## Security

Launching `exec://` runs arbitrary local programs. Do **not** feed untrusted URIs or user input to `interface_from_uri` without validation.

---

## Developing & testing

```bash
# in this repo
uv sync
uv run pytest -q
# (or) pytest -q
```

The test suite demonstrates:

* Spawning `exec:///python` and evaluating expressions interactively
* Clean shutdown when the child exits or on request
* Passing CLI args via `?arg=` and handling error exit codes

---

## License

MIT — see `LICENSE`.
