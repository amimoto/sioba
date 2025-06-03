# `sioba` - Core I/O Interfaces

The `sioba` module provides a set of Python classes that define core I/O interfaces. These interfaces are designed to handle communication between a backend (like a shell, a Python function, or a network socket) and a frontend terminal emulator.

`sioba` is often used in conjunction with UI libraries that provide terminal components, such as [`sioba_nicegui`](../README.md), to create interactive web-based terminal applications. While `sioba_nicegui` offers a user-friendly way to embed terminals in [NiceGUI](https://nicegui.io/) projects, `sioba` itself focuses on the underlying data handling and control logic.

This document describes the main interface classes provided by the `sioba` module.

## `Interface`

The `Interface` class (from `sioba.base`) is the cornerstone of the `sioba` module. All other specialized interface classes inherit from it. It establishes the fundamental contract for managing the lifecycle and I/O operations of a terminal connection.

This interface also provides terminal emulation by integrating with the `pyte` library. This allows it to maintain a virtual screen, understand ANSI escape codes, and keep track of cursor position and screen content more accurately.

**Key Responsibilities:**

*   **Lifecycle Management:** Handles the initialization, startup, and shutdown of the interface.
    *   `__init__(...)`: Initializes the interface, setting up basic properties and callbacks.
    *   `start()`: Asynchronously starts the interface's main operations (e.g., connecting to a process, opening a socket). Subclasses implement `start_interface()` for custom startup logic.
    *   `shutdown()`: Asynchronously shuts down the interface, releasing resources. Subclasses implement `shutdown_interface()` for custom cleanup.
    *   `is_running()`: Returns `True` if the interface is currently active.
    *   `is_shutdown()`: Returns `True` if the interface has been shut down.
*   **I/O Handling:** Manages the flow of data between the connected backend and the terminal control.
    *   `send_to_control(data: bytes)`: Called by the interface's backend logic to send data (bytes) to the frontend terminal emulator for display.
    *   `receive_from_control(data: bytes)`: Called by the terminal emulator (or user interaction) to send data (bytes) from the frontend to the interface's backend.
*   **Event Callbacks:** Uses a callback system for various events:
    *   `on_send_to_control(callback)`: Registers a function to be called when data is ready to be sent to the terminal.
    *   `on_receive_from_control(callback)`: Registers a function to handle data coming from the terminal.
    *   `on_shutdown(callback)`: Registers a function to be called when the interface shuts down.
    *   `on_set_terminal_title(callback)`: Registers a function to handle terminal title changes.
*   **Terminal Properties:**
    *   `set_terminal_title(name: str)`: Sets the title of the terminal.
    *   `set_terminal_size(rows: int, cols: int, ...)`: Informs the interface about the terminal dimensions. (Actual resizing behavior depends on the subclass).
    *   `get_terminal_buffer() -> bytes`: Intended to return the current content of the terminal buffer (behavior varies by subclass).
    *   `get_terminal_cursor_position() -> tuple[int, int] | None`: Intended to return the cursor position (behavior varies by subclass).
*   **`pyte` Integration:** Uses a `pyte.Screen` and `pyte.Stream` internally.
    *   The `stream.feed()` method is used to process incoming data, allowing `pyte` to interpret terminal control sequences.
*   **Terminal Emulation:**
    *   `screen`: A `pyte.Screen` object representing the virtual terminal display.
    *   `set_terminal_size(rows: int, cols: int, ...)`: Resizes the `pyte.Screen` in addition to informing the interface.
    *   `get_terminal_buffer() -> bytes`: Dumps the current state of the `pyte.Screen` (including scrollback if handled by the `EventsScreen` subclass used) into a byte string, effectively serializing the visible terminal content with ANSI escape codes.
    *   `get_terminal_cursor_position() -> tuple[int, int] | None`: Returns the current cursor position (`(row, col)`) as tracked by the `pyte.Screen`.
*   **`EventsScreen`:** A subclass of `pyte.Screen` used by `Interface` to handle events like title changes and manage a scrollback buffer within `pyte` itself.
*   `scrollback_buffer_size` (constructor argument): Configures the size of the scrollback buffer managed by `EventsScreen`.

The `Interface` class itself is typically not instantiated directly but serves as a blueprint for concrete implementations like `FunctionInterface` or `SocketInterface`.

## `EchoInterface`

The `EchoInterface` class (from `sioba.echo`) is a very simple implementation of `Interface`.

**Key Features:**

*   **Inherits from `Interface`**.
*   **Echoes Input:** Its primary function is to echo back any data it receives via its `receive_from_control()` method.
    *   It typically converts carriage returns (`\r`) to carriage return + line feed (`\r\n`) before sending the data back to the control via `send_to_control()`.
*   **Configuration:** It has a default `InterfaceConfig` that sets `convertEol = True`.

**Use Case:**

`EchoInterface` is mainly useful for:

*   Testing basic connectivity with a terminal UI component.
*   Serving as a minimal example of how to implement a custom interface.

**Example:**

If a terminal UI is connected to an `EchoInterface`, anything the user types will be immediately displayed back on the terminal.

---

## `FunctionInterface`

The `FunctionInterface` class (from `sioba.function`) extends `Interface` and is one of the most versatile interfaces. It allows you to run a Python function as the backend logic for a terminal session, enabling interactive text-based applications.

**Key Features:**

*   **Inherits from `Interface`:** Retains scrollback buffer capabilities.
*   **Runs a Python Function:** The core idea is to pass a callable (your Python function) to its constructor. This function then drives the terminal interaction.
    *   The function receives a reference to the `FunctionInterface` instance as its first argument, allowing it to call methods like `print()`, `input()`, etc.
*   **Interactive I/O Methods:**
    *   `print(*args, **kwargs)`: Sends text to the terminal. It behaves like the built-in `print` function and automatically converts newlines (`\n`) to carriage return + line feed (`\r\n`).
    *   `input(prompt: str = "") -> str`: Displays a `prompt` on the terminal and waits for the user to type a line of text and press Enter. The entered text is returned as a string. Input is echoed to the terminal.
    *   `getpass(prompt: str = "") -> str`: Similar to `input()`, but user input is not echoed to the terminal, making it suitable for password entry.
*   **Capture Modes:** Internally manages different `CaptureMode` states (`DISCARD`, `ECHO`, `INPUT`, `GETPASS`) to control how user input from the control is handled (e.g., whether to echo it, collect it for `input()`/`getpass()`, or ignore it).
*   **Threaded Execution:** The provided function typically runs in a separate thread, allowing the main application (e.g., a NiceGUI app) to remain responsive.
*   **Ctrl-C Handling:** By default, receiving a Ctrl-C (`\x03`) from the terminal will trigger a shutdown of the interface.

**Use Case:**

`FunctionInterface` is ideal for creating simple command-line-like tools, interactive scripts, or any application where the interaction can be modeled as a sequence of print statements and user inputs within a Python function.

**Example:**

```python
from sioba import FunctionInterface
import time
import datetime

def my_terminal_app(interface: FunctionInterface):
    interface.print("Welcome to the FunctionInterface Demo!")
    name = interface.input("What's your name? ")
    interface.print(f"Hello, {name}!")

    secret = interface.getpass("Tell me a secret: ")
    interface.print(f"Your secret was {len(secret)} characters long. I won't tell!")

    interface.print("I will now print the time every 5 seconds.")
    try:
        while True:
            interface.print(f"Current time: {datetime.datetime.now()}")
            time.sleep(5)
    except InterfaceShutdown: # Or KeyboardInterrupt if not caught by interface
        interface.print("Timer stopped. Bye!")
    except Exception as e:
        interface.print(f"An error occurred: {e}")

# To use this with a terminal UI (e.g., sioba_nicegui.XTerm):
# term_ui = XTerm(interface=FunctionInterface(my_terminal_app))
# await term_ui.interface.start() # Start the interface
```
This example defines a function `my_terminal_app` that interacts with the user. When this function is passed to `FunctionInterface` and connected to a terminal UI, it will print messages, ask for input, and handle password-style input.

## `SocketInterface`

The `SocketInterface` class (from `sioba.socket`) extends `Interface` and is designed to connect a terminal UI to a network socket, effectively acting as a simple TCP client (like Telnet).

**Key Features:**

*   **Inherits from `Interface`:** Benefits from `pyte`-based terminal emulation, allowing it to correctly interpret ANSI escape codes and manage screen state for interactions with remote servers that expect a terminal client.
*   **TCP Client:** Connects to a specified host and port.
    *   `connection` (constructor argument): A `ConnectionConfig` typed dictionary (e.g., `{"host": "example.com", "port": 23}`) is required to specify the target server.
*   **Asynchronous I/O:**
    *   Uses `asyncio.open_connection()` to establish the socket connection.
    *   Runs an asynchronous receive loop (`_receive_loop`) to continuously read data from the socket and send it to the terminal control (`send_to_control()`).
    *   Data received from the terminal control (`receive_from_control()`) is written to the socket. It also echoes the input back to the local terminal by default (after CR -> CRLF conversion).
*   **Configuration:**
    *   Its default `InterfaceConfig` has `convertEol = True`, meaning carriage returns from the terminal UI are converted to CRLF before sending over the socket.

**Use Case:**

`SocketInterface` is used when you want to embed a terminal in your application that connects to a remote service via a raw TCP socket. This is common for:

*   Connecting to Telnet servers.
*   Interacting with other network services that use a simple, unencrypted, stream-based protocol.

**Conceptual Example:**

```python
from sioba import SocketInterface
from sioba.socket import ConnectionConfig

# Configuration for the remote server
target_server: ConnectionConfig = {"host": "telehack.com", "port": 23} # A public Telnet server

# Create the interface
socket_interface = SocketInterface(connection=target_server)

# To use this with a terminal UI (e.g., sioba_nicegui.XTerm):
# term_ui = XTerm(interface=socket_interface)
# await term_ui.interface.start() # Start the interface and connect to the socket

# User input in term_ui will be sent to telehack.com,
# and data from telehack.com will be displayed in term_ui.
```
This example sets up `SocketInterface` to connect to `telehack.com` on port 23. When integrated with a terminal UI, it would allow interaction with that Telnet server.

## Core Concepts

The `sioba` interfaces facilitate communication between a data source/sink (the "backend") and a terminal emulator (the "frontend" or "control"). Here's a simplified overview:

1.  **Instantiation & Configuration:**
    *   You create an instance of a specific interface class (e.g., `FunctionInterface(my_func)`).
    *   During `__init__`, basic properties, buffers (if any), and callback lists are set up.

2.  **Starting the Interface:**
    *   You call `await interface.start()`.
    *   This typically triggers the `start_interface()` method specific to the subclass.
        *   For `FunctionInterface`, this starts a new thread for your function.
        *   For `SocketInterface`, this initiates an `asyncio.open_connection()`.
        *   For shell interfaces (like in `sioba_nicegui`), this would spawn a PTY process.
    *   The interface state changes from `InterfaceState.INITIALIZED` to `InterfaceState.STARTED`.

3.  **Data Flow (Backend to Frontend):**
    *   When the backend has data to display (e.g., your function calls `interface.print("hello")`, or a socket receives data):
        *   The interface internally calls `await self.send_to_control(b"hello\r\n")`.
        *   `send_to_control` iterates through all registered `_on_send_from_xterm_callbacks`.
        *   A terminal UI component (like `sioba_nicegui.XTerm`) registers a callback here. This callback takes the data and updates the visual terminal display for the user.
        *   The data is also fed to its `pyte.Stream` to update the virtual screen state.

4.  **Data Flow (Frontend to Backend):**
    *   When the user types in the terminal UI:
        *   The UI component captures this input (e.g., `b"user input\r"`).
        *   It calls `await interface.receive_from_control(b"user input\r")` on its associated interface instance.
        *   `receive_from_control` then iterates through `_on_receive_from_control_callbacks`.
        *   The specific interface subclass implements the logic for this.
            *   `EchoInterface` simply calls `send_to_control` with the same data.
            *   `FunctionInterface` might store the data in its `input_buffer`, signal an event if `input()` or `getpass()` is waiting, and potentially echo the data back via `send_to_control` depending on the `CaptureMode`.
            *   `SocketInterface` writes the data to its connected socket and might echo it.
            *   A shell interface would write the data to the PTY of the shell process.

5.  **Shutdown:**
    *   When `await interface.shutdown()` is called (either explicitly, due to an error, or automatically if `auto_shutdown` is true and reference count drops):
        *   The `shutdown_interface()` method is called for subclass-specific cleanup (closing sockets, joining threads, killing processes).
        *   The state changes to `InterfaceState.SHUTDOWN`.
        *   Registered `_on_shutdown_callbacks` are invoked.

**Callbacks:**

The callback system (`on_send_to_control`, `on_receive_from_control`, etc.) is crucial. It decouples the `sioba` interfaces from any specific UI implementation. A UI component "subscribes" to these events to know when to update its display or when to forward user input.

## Interface Registry and Dynamic Discovery

`sioba` includes a flexible mechanism for registering and discovering interface handlers, allowing applications and plugins to define and use custom interfaces identified by URI schemes.

### Core Components:

*   **`sioba.registry.INTERFACE_REGISTRY`**: A dictionary mapping URI schemes (strings) to interface classes or factory functions.
*   **`@sioba.registry.register_interface(*schemes)` (decorator)**:
    This decorator allows you to manually associate an interface class with one or more URI schemes. When a class is decorated (e.g., `@register_interface("mycustomscheme")`), it gets added to the `INTERFACE_REGISTRY`.

    ```python
    from sioba.registry import register_interface
    from sioba.base import Interface

    @register_interface("custom")
    class MyCustomInterface(Interface):
        # ... implementation ...
        pass
    ```

*   **Entry Point Discovery (`sioba.interfaces` group)**:
    Beyond manual registration, `sioba` can discover interfaces provided by other installed Python packages through the `importlib.metadata.entry_points` mechanism. Packages can declare their interfaces under the group name `sioba.interfaces`.

    For example, a `pyproject.toml` of a plugin package might include:

    ```toml
    [project.entry-points."sioba.interfaces"]
    plugin-scheme = "my_plugin_package.module:PluginInterfaceClass"
    another-scheme = "my_plugin_package.module:AnotherInterface"
    ```
    When `sioba` needs to find an interface for a scheme like `"plugin-scheme"`, it will look for such entry points if the scheme isn't already in its internal `INTERFACE_REGISTRY`.

### `sioba.registry.init_interface(uri, ...)`

This is the primary factory function for creating interface instances. It takes a URI string (e.g., `"echo://"` or `"socket://host:port"`) and other optional parameters:

```python
from sioba.registry import init_interface
from sioba.structs import InterfaceConfig

# Example: Initialize a registered Echo interface
echo_config = InterfaceConfig(convertEol=True)
echo_instance = init_interface("echo://", interface_config=echo_config)

# Example: Initialize a Socket interface (assuming it's registered or discoverable)
# For SocketInterface, connection parameters are often part of the URI
# or passed via **kwargs if the specific interface class supports it.
# The exact kwargs will depend on the interface being initialized.
socket_instance = init_interface("socket://telehack.com:23")

# Example: Using a custom, discoverable interface
# If 'plugin-scheme' is defined in an entry point:
# custom_instance = init_interface("plugin-scheme://some_details")
```

**How `init_interface` works:**

1.  It parses the URI to extract the `scheme`.
2.  It first checks the internal `INTERFACE_REGISTRY` for a handler associated with this scheme.
3.  If not found, it queries `entry_points().select(group="sioba.interfaces")` to find a matching entry point by name.
    *   If a matching entry point is found, it loads the class/factory specified by the entry point.
    *   It verifies that the loaded handler is a subclass of `sioba.base.Interface`.
    *   The newly discovered handler is then cached in `INTERFACE_REGISTRY` for quicker access next time.
4.  If no handler can be found (neither in the registry nor via entry points), it raises a `ValueError`.
5.  Once the handler class/factory is identified, `init_interface` instantiates it, passing the `uri`, `interface_config`, standard callbacks (`on_send_to_control`, `on_receive_from_control`, `on_shutdown`, `on_set_terminal_title`), and any additional `**kwargs` provided to `init_interface`. These `**kwargs` are passed through to the constructor of the specific interface class.

This system allows for a highly extensible architecture where `sioba` itself doesn't need to know about all possible interfaces beforehand. As long as an interface is registered (either directly or via entry points), `init_interface` can be used to create an instance of it.

### `sioba.registry.list_interfaces()`

To get a list of available interface schemes that can be discovered via entry points, you can use:

```python
from sioba.registry import list_interfaces

available_schemes = list_interfaces()
print(f"Available interface schemes from entry points: {available_schemes}")
# Note: This list comes from entry points and might not include
# interfaces manually registered only via the @register_interface decorator
# or built-in interfaces if they are not also listed as entry points.
```
This function specifically queries the `sioba.interfaces` entry point group.

## Installation

The `sioba` module is a core component of the `sioba_nicegui` package. It is automatically installed when you install `sioba_nicegui`.

You typically do not need to install `sioba` directly. Please refer to the installation instructions in the main [`sioba_nicegui` README](../README.md#installation) for details on how to install the complete package.

If you are developing `sioba` itself or have a specific need to use it standalone (which is less common), you might work with it as part of a local development setup.

## Usage with `sioba_nicegui`

The interface classes described above form the backend for terminal emulators. A common use case is with the `sioba_nicegui` package, which provides an `XTerm` NiceGUI component.

You would typically instantiate one of these `sioba` interfaces and pass it to the `sioba_nicegui.XTerm` constructor.

**Example Snippet:**

```python
from nicegui import ui
from sioba import FunctionInterface # Or SocketInterface, EchoInterface, etc.
from sioba_nicegui.xterm import XTerm # Assuming sioba_nicegui is installed

# 1. Define your function if using FunctionInterface
def my_interactive_script(interface: FunctionInterface):
    name = interface.input("Enter your name: ")
    interface.print(f"Hello, {name}!")
    # ... more logic

# 2. Create an interface instance
# For FunctionInterface:
func_interface = FunctionInterface(my_interactive_script)
# For SocketInterface:
# from sioba.socket import ConnectionConfig
# conn_config: ConnectionConfig = {"host": "somehost.com", "port": 1234}
# socket_interface = SocketInterface(connection=conn_config)

# 3. Create the XTerm UI component with the chosen interface
terminal_view = XTerm(interface=func_interface) # Or pass socket_interface, etc.

# 4. Start the interface (important!)
# This is often done in an on_page_ready or similar event in NiceGUI
async def setup_terminal():
    await terminal_view.interface.start()

ui.on_page_ready(setup_terminal)

# ui.run() should be called elsewhere in your NiceGUI app
```

For more detailed examples and information on how to integrate these interfaces into a NiceGUI application, please refer to the main [`sioba_nicegui` README file](../README.md). That README covers `ShellXTerm` (which uses a specialized shell interface internally) and provides more context on building terminal UIs.

The `sioba.registry.init_interface` function is a powerful low-level tool for creating and configuring interfaces. UI libraries built on top of `sioba`, such as `sioba_nicegui`, may leverage this to provide even more convenient helper methods. For example, a UI component like `sioba_nicegui.XTerm` might offer a `from_uri(uri_string, ...)` class method that internally uses `sioba.registry.init_interface` to set up both the backend interface and the UI component in a single step. Refer to the documentation of the specific UI library (e.g., `sioba_nicegui`) for details on such high-level helper functions.
