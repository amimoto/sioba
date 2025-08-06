# SIOba: Simple IO Backend Abstraction

**sioba** (Simple IO Backend Abstraction) is a Python library designed to provide a unified way to handle various input/output (I/O) backends and connect them to user interfaces, particularly terminal emulators. Its primary goal is to simplify the integration of interactive, text-based backends (like functions, sockets, or shell processes) with frontends.

The name "sioba" is both a mild pun on soba noodles (evoking the imagery of I/O pipes) and an acronym for Simple IO Backend Abstraction.

## Architecture

The core concept of `sioba` revolves around its `Interface` classes, which act as a bridge between a backend data source/sink and a frontend control mechanism.

-   **Backend**: This is where the actual I/O operations occur. It could be a Python function, a network socket, a subprocess, or any other stream-based source.
-   **Frontend/Control**: This is the user-facing component that displays output and sends input. While `sioba` is backend-agnostic, it is designed with terminal emulators like the `XTerm` component from `sioba_nicegui` in mind.

The `Interface` subclasses are responsible for managing the specifics of communication with their respective backends and relaying data to and from the connected frontend control.

## A Virtual TTY

`sioba` is more than a simple data pipe. It integrates the `pyte` library to maintain a virtual terminal screen. This allows it to process ANSI escape codes, manage cursor positions, and understand terminal screen state. This makes it a powerful tool for interacting with backend processes that expect a true terminal environment (e.g., command-line applications, remote shells via Telnet/SSH).

While it is a general-purpose library, it was created with the intent to be used with `sioba_nicegui` to connect these powerful backend interfaces to a web-based `xterm.js` frontend in [NiceGUI](https://nicegui.io/) applications.

## Interfaces

Interfaces are the core of `sioba`. They define how to communicate with a specific backend.

The base class for all interfaces is [`sioba.interface.base.Interface`](sioba/src/sioba/interface/base.py).

### Extensible Interfaces via Entry Points

`sioba` uses a plugin-based architecture for discovering `Interface` implementations. Other packages can provide new interfaces by declaring them in their `pyproject.toml` under the `sioba.interface` entry point group.

For example, the built-in `EchoInterface` is registered like this:

```toml
// filepath: sioba/pyproject.toml
// ...existing code...
[project.entry-points]
"sioba.interface".echo = "sioba.interface.echo:EchoInterface"
"sioba.interface".tcp  = "sioba.interface.socket:SocketInterface"
// ...existing code...
```

You can then instantiate interfaces using the [`sioba.interface_from_uri`](sioba/src/sioba/__init__.py) function, e.g., `interface_from_uri("echo://")`.

### Built-in Interfaces

-   [`FunctionInterface`](sioba/src/sioba/interface/function.py): Runs a Python function in a thread, redirecting `print()`, `input()`, and `getpass()` to the frontend.
-   [`EchoInterface`](sioba/src/sioba/interface/echo.py): A simple interface that echoes all received data back to the frontend.
-   [`SocketInterface`](sioba/src/sioba/interface/socket.py): Connects to a TCP socket, acting as a simple Telnet client.

## Buffers

Buffers can be used to process or hold data received from the frontend before it's sent to the backend. This is useful for line-editing, history, or other terminal features.

Like interfaces, buffers are discoverable via entry points under the `"sioba.buffer"` group.

```toml
// filepath: sioba/pyproject.toml
// ...existing code...
[project.entry-points]
// ...existing code...
"sioba.buffer".none = "sioba.buffer.base:Buffer"
"sioba.buffer".line = "sioba.buffer.line:LineBuffer"
"sioba.buffer".terminal = "sioba.buffer.terminal:TerminalBuffer"
// ...existing code...
```

You can instantiate a buffer using [`sioba.buffer_from_uri`](sioba/src/sioba/__init__.py).

## Installation

```bash
pip install sioba
```

## Basic Usage

Here is an example of using `FunctionInterface` to run an interactive Python function. In a real application, you would connect this interface to a frontend component like `sioba_nicegui.XTerm`.

```python
from sioba import FunctionInterface, Interface
import time

def my_interactive_function(interface: Interface):
    """
    An example interactive function that uses the interface's
    print and input methods.
    """
    interface.print("Welcome to the interactive function!")
    name = interface.input("What's your name? ")
    interface.print(f"Hello, {name}!")

    for i in range(5):
        interface.print(f"Counting: {i+1}/5")
        time.sleep(1)
    interface.print("Done!")

# Create the FunctionInterface with your function
func_interface = FunctionInterface(my_interactive_function)

# Define a handler for when the interface wants to send data
def handle_output(data: bytes):
    # In a real app, this would send data to the frontend UI
    print(data.decode(), end='')

func_interface.on_send_to_frontend = handle_output

# Start the interface (runs the function in a background thread)
func_interface.start()

# Simulate user input
# In a real app, this would come from the frontend UI
func_interface.receive_from_frontend(b"World\r\n")

# Wait for the interface to finish
func_interface.join()
```