# sioba: A NiceGUI xterm.js Control

[![PyPI](https://img.shields.io/pypi/v/sioba.svg)](https://pypi.org/project/sioba/)
[![License](https://img.shields.io/badge/license-MIT--0-blue.svg)](#license)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

This **WIP** project provides an [xterm.js](https://xtermjs.org/) based terminal component for your [NiceGUI](https://nicegui.io/) apps, running on both Linux and Windows. It allows you to embed fully interactive terminals (local shells, serial connections, or anything else) within your NiceGUI UI.

> **Disclaimer**: This is **not** an official [NiceGUI](https://nicegui.io/) project. Use it at your own risk, especially when enabling shell or device access.

---

## Features

- **NiceGUI Integration**: Easily add a terminal component inside your NiceGUI UI.
- **Local Shell Support**: Provides a local shell out of the box on Linux and Windows (via `pywinpty` on Windows).
- **Custom IO Stream Support**: Extend the base `Interface` class to communicate with any data source, such as serial devices, remote servers, or custom processes.
- **Concurrent Access**: Multiple terminals or multiple users are supported.
- **Persistent State**: Caches screen data, so refreshing doesn’t necessarily lose session output.
- **Optional Authentication**: The `niceterm` CLI supports authentication or no-auth modes.
- **Isolation Levels**: Control whether terminals are shared globally, per user, or per browser tab.

---

## Installation

**Library only**:
```bash
pip install sioba
```

**Library + CLI** (installs the `niceterm` command):
```bash
pip install sioba[cli]
```

> **Note**: The CLI offers easy web-based shell access, which can be a security concern. Enable it only if you understand the risks.

---

## Quick Start

A minimal example to embed a shell terminal in a NiceGUI page:

```python
from nicegui import ui
from sioba.xterm import ShellXTerm

# Create a full-page terminal that opens your default shell.
ShellXTerm().classes("w-full h-full")

ui.run()
```

Open your app in the browser. You’ll see a page hosting an interactive shell.

---

## Library Overview

`sioba` is built around two key abstractions:

1. **XTerm** – A NiceGUI element based on xterm.js, rendering an interactive terminal in the browser.
2. **Interface** – An abstract base class specifying how terminal input/output is processed on the Python side.

### XTerm Class

```python
from sioba.xterm import XTerm
```

**Purpose**:
- Renders an xterm.js terminal in NiceGUI.
- Handles sending data to and receiving data from a backend (shell, serial port, custom service, etc.).

**Key Parameters / Methods**:
- **`__init__(self, config: TerminalConfig, interface:Interface=None, on_change: Callable, on_close: Callable, **kwargs)`**
  - `interface`: A subclass of `Interface` that manages I/O.
- **`write(self, data: bytes)`**
  - Called by the attached interface to send output to the terminal.
- **`set_cursor_location(self, row: int, col: int)`**
  - Manually position the cursor on the UI (not interface)


**Example**:
```python
from sioba.interface.base import Interface, INTERFACE_STATE_STARTED, INTERFACE_STATE_INITIALIZED
from loguru import logger

from nicegui import ui
from sioba.xterm import XTerm

class EchoInterface(Interface):
    async def receive(self, data: bytes):
        await self.send(data)

# Instantiate our custom interface for a specific echo device
echo_interface = EchoInterface()
echo_interface.start()

# Render in your NiceGUI app
ui.label("Echo Terminal")

# Create an XTerm bound to the echo interface
echo_terminal = XTerm(interface=echo_interface).classes("w-full h-full")

ui.run()
```
In this simplistic example, whatever the user types is immediately echoed back.

### ShellXTerm Subclass

```python
from sioba.xterm import ShellXTerm
```

**Purpose**:
- A convenience subclass that provides a local shell interface automatically (using `pty` on Linux or `pywinpty` on Windows).

**Key Usage**:
```python
ShellXTerm().classes("w-full h-full")
```
- Spawns `bash` on Linux or `cmd.exe` on Windows.
- If you need a different shell (e.g., `powershell`), you can pass arguments directly to the underlying interface.

### Interface Base Class

```python
from sioba.interface import Interface
```

**Purpose**:
- Defines the core contract for reading/writing data between the browser-based terminal and a Python-driven data source.

**Methods**:
- **`send(data: bytes) -> None`**
  - Sends data to to the web-based XTerm to be shown to the user
- **`receive(data: bytes) -> None`**
  - Invoked when data is received from the web-based XTerm
- **`close(self) -> None`**
  - Close/cleanup the underlying connection or process.

- **`is_running(self) -> bool`**
  - True when the interface is actively sending/receiving data
- **`is_shutdow(self) -> bool`**
  - True when the interface has closed and we don't expect more IO
- **`is_closed(self) -> bool`**
  - Return True if the backend is closed or invalid.

- **`on_send(on_send: Callable) -> None`**
- **`on_receive(on_send: Callable) -> None`**
- **`on_set_terminal_title_handle(on_send: Callable) -> None`**
- **`on_shutdown(on_send: Callable) -> None`**

- **`set_terminal_title(name: str) -> None`**
- **`set_terminal_size(rows: int, cols: int, xpix: int=0, ypix: int=0) -> None`**
- **`get_terminal_buffer() -> bytes`**
- **`get_terminal_cursor_position() -> tuple[int, int]|None`**

Extend `Interface` to suit your needs (local shell, remote connections, serial devices, etc.).

### BufferedInterface Base Class

### PersistantInterface Base Class

### FunctionInterface Class

This is probably one of the more useful classes. This can be used with basic function code to write text based interfaces that interact with a user over the web.

Basic example:

```python
#!/usr/bin/env python

from nicegui import ui
from sioba.interface.function import FunctionInterface
from sioba.xterm import XTerm

import time
import datetime

def terminal_code(interface: FunctionInterface):
    interface.print("Hello, World!")
    interface.print("This is a simple script.")

    name = interface.input("What's your name? ")
    interface.print(f"Hello, {name}!")

    hidden = interface.getpass("Enter your hidden word: ")
    interface.print(f"Your hidden word is: {hidden}")

    while True:
        time.sleep(2)
        interface.print(f"It is: {datetime.datetime.now()}")

xterm = XTerm(
            interface=FunctionInterface(terminal_code)
        ).classes("w-full")

# Make sure static files can be found
try:
    ui.run(
        title="sioba Function Example",
        port=9000,
        host="0.0.0.0",
        reload=False,
        show=True,
        favicon="📟"
    )
except KeyboardInterrupt:
    pass

```


---

## Custom Interface Example: Serial Port

Below is an example of using [pyserial](https://pyserial.readthedocs.io/en/latest/) to connect a serial port to the terminal.

1. **Install pyserial**:
   ```bash
   pip install pyserial
   ```
2. **Create a custom interface** that:
   - Opens the serial port.
   - Listens for incoming data (in a background thread).
   - Forwards terminal input back to the serial device.

```python
import threading
import serial
from sioba.interface.base import Interface, INTERFACE_STATE_STARTED, INTERFACE_STATE_INITIALIZED
from loguru import logger

from nicegui import ui
from sioba.xterm import XTerm

class SerialPortInterface(Interface):
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port = port
        self._closed = False
        self.baudrate = baudrate
        self.ser = None

    @logger.catch
    async def start_interface(self):
        """Starts the shell process asynchronously."""
        if self.state != INTERFACE_STATE_INITIALIZED:
            return
        self.state = INTERFACE_STATE_STARTED

        # Open the serial device
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0)

        # Start a background thread to read from the serial port
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def _read_loop(self):
        while not self._closed:
            data = self.ser.read(1024)  # Non-blocking read
            if data:
                # Send any received data to the terminal
                self.read(data)

    async def write(self, data: bytes):
        if not self.ser:
            return
        # When the user types in the terminal, send it to the serial device
        if not self._closed and self.ser.is_open:
            # Ensure we encode to bytes
            self.ser.write(data)

    def close(self):
        # Cleanup
        if not self.ser:
            return
        self._closed = True
        if self.ser.is_open:
            self.ser.close()

    def is_closed(self):
        return self._closed
```

3. **Integrate your `SerialPortInterface` with `XTerm`** in a NiceGUI app:

```python
from nicegui import ui
from sioba.xterm import XTerm

# Instantiate our custom interface for a specific serial device
serial_interface = SerialPortInterface(port="COM4", baudrate=115200)
if  __name__ == "__mp_main__":
    serial_interface.start()

# Render in your NiceGUI app
ui.label("Serial Port Terminal")

# Create an XTerm bound to the serial interface
serial_terminal = XTerm(interface=serial_interface).classes("w-full h-full")


ui.run()

```

Now anything typed in the terminal is sent to the specified serial port, and anything received from the device is displayed in the terminal.

---

## CLI Usage (`niceterm`)

Installing with `[cli]` provides the `niceterm` command, a convenient multi-terminal web interface:

```text
sioba Web Interface

Usage:
    niceterm [options]
    niceterm -h | --help
    niceterm --version

Options:
  -h --help                    Show this help.
  --version                    Show version.
  --host=<host>                Host to bind web interface [default: 0.0.0.0].
  --port=<port>                Port for web interface [default: 8080].
  --app=<command>              Default command to start in new terminals [default: bash].
  --password=<pass>            Set authentication password.
  --no-auth                    Disable authentication requirement (cannot combine with --password).
  --light-mode                 Use light mode theme.
  --log-level=<level>          Set log level [default: INFO].
  --isolation=<level>          At what level terminals are shared [default: global].
                               (global, user, or tab)
```

### Examples
```bash
# Start with default settings on port 8080:
niceterm

# Start on port 9000, with no authentication:
niceterm --port 9000 --no-auth

# Provide a specific password:
niceterm --password secret123

# Run Python in each new terminal and isolate them per tab:
niceterm --app "python3" --isolation tab
```

On startup, logs display the server address and an auto-generated password (if `--password` wasn’t specified).

---

## Screenshots

| Authentication Screen                        | Terminal Dashboard                          |
|---------------------------------------------|---------------------------------------------|
| ![](https://raw.githubusercontent.com/amimoto/sioba/refs/heads/main/sioba-authentication.png) | ![](https://raw.githubusercontent.com/amimoto/sioba/refs/heads/main/sioba-webterminal.png) |

**Simple auto-index page usage**:

```python
from nicegui import ui
from sioba.xterm import ShellXTerm

ShellXTerm().classes("w-full h-full")

ui.run()
```

Which yields:

![](https://raw.githubusercontent.com/amimoto/sioba/refs/heads/main/sioba.png)

---

## Security Considerations

1. **Open Shell/Device Access**: Running `niceterm` or embedding a shell/serial interface in a publicly exposed NiceGUI app is risky.
2. **Authentication**: Always protect your deployment with strong passwords or other authentication methods if it’s internet-accessible.
3. **TLS/SSL**: Consider using HTTPS or a secure reverse proxy for production. (or simply just... maybe not use this in production. This is an experimental library after all)
4. **Isolation Levels**: With `niceterm`, you can decide whether multiple users/tabs share the same terminal or have separate sessions.

---

## License

This project is released under the [MIT-0 License](https://github.com/amimoto/sioba/blob/main/LICENSE). You’re free to copy, modify, and distribute this software with no attribution required.

---

_If you have suggestions, bug reports, or feature requests, please open an [issue on GitHub](https://github.com/amimoto/sioba/issues)._