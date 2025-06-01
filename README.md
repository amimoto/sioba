# sioba: Simple IO Backend Abstraction

## Introduction

sioba (Simple IO Backend Abstraction) is a Python library designed to provide a unified way to handle various input/output (I/O) backends and connect them to user interfaces, particularly terminal emulators. Its primary goal is to simplify the integration of interactive, text-based backends (like functions, sockets, or shell processes) with frontends such as web-based terminal emulators.

The name "sioba" is both a mild pun on soba noodles (evoking the imagery of I/O pipes) and an acronym for Simple IO Backend Abstraction.

## Modules

The sioba ecosystem is organized into several key modules:

- **`sioba`**: This is the core library. It provides the fundamental `Interface` base classes (`Interface`, `BufferedInterface`, `PersistentInterface`) that define the contract for communication between backends and frontends. It also includes concrete interface implementations like:
    - `EchoInterface`: A simple interface that echoes input back.
    - `FunctionInterface`: An interface that runs a Python function as the backend, enabling interactive text-based applications.
    - `SocketInterface`: An interface that connects to a network socket, behaving like a basic Telnet client.

- **`sioba_nicegui`**: This module integrates `sioba` with the [NiceGUI](https://nicegui.io/) framework. It offers the `XTerm` component, which allows embedding an xterm.js-based terminal emulator directly into NiceGUI web user interfaces. This `XTerm` component can be connected to any `sioba` interface.

- **`sioba_subprocess`**: Building upon `sioba` and `sioba_nicegui`, this module provides `ShellXTerm`. `ShellXTerm` is a specialized component for running and interacting with live shell subprocesses (e.g., bash, sh, cmd.exe) directly within a NiceGUI web application.

- **`sioba_app`**: This module provides a command-line application called `niceterm`. `niceterm` leverages the `sioba` libraries to offer a multi-terminal web interface, allowing users to run and interact with various backends (like shell sessions or Python functions) from a web browser.

## Installation

The installation process depends on the components you intend to use:

```bash
# For the core sioba library and NiceGUI integration (XTerm component)
pip install sioba_nicegui

# To include support for shell subprocesses (ShellXTerm component)
pip install sioba_subprocess

# For the 'niceterm' command-line application
# The 'niceterm' CLI is typically included when you install sioba_nicegui.
# If you find it's not available, you might need to install sioba_app separately
# or check for an extra like: pip install sioba_nicegui[app]
# (Verify specific packaging if niceterm is missing after installing sioba_nicegui)
```
Generally, `pip install sioba_nicegui` is the main entry point for most library users and also provides the `niceterm` application. `sioba_subprocess` is an optional add-on for shell capabilities.

## Architecture

The core concept of `sioba` revolves around its `Interface` classes, which act as a bridge between a backend data source/sink and a frontend control mechanism.

- **Backend**: This is where the actual I/O operations occur. It could be:
    - A Python function that interacts with the user via `print` and `input`.
    - A live shell process (e.g., `/bin/bash`).
    - A network socket connection to a remote server.
    - Any other source/destination of byte streams or text.

- **Frontend/Control**: This is the user-facing component that displays output from the backend and sends user input to it. Typically, this is a terminal emulator, like the `XTerm` component provided by `sioba_nicegui`.

The `Interface` subclasses in `sioba` are responsible for managing the specifics of communication with their respective backends and relaying data to and from the connected frontend control. They use a system of callbacks (e.g., `on_send_to_control`, `on_shutdown`) to signal events to the frontend.

## Key Classes and Relationships

- **`sioba.base.Interface`**:
    - The abstract base class for all interfaces.
    - Defines the core contract:
        - Lifecycle methods: `start()`, `shutdown()`.
        - I/O methods: `send_to_control(data: bytes)` for sending data to the frontend, and `receive_from_control(data: bytes)` for receiving data from the frontend.
    - Manages callbacks for events: `on_send_to_control` (triggered when data should be sent to the frontend), `on_shutdown` (triggered when the interface is shutting down).

- **`sioba.base.BufferedInterface`**:
    - A subclass of `Interface`.
    - Adds a scrollback buffer, allowing it to store a history of output that has been sent to the control. This is useful for frontends that might connect after some output has already been generated or that need to redraw history.

- **`sioba.base.PersistentInterface`**:
    - A subclass of `Interface`.
    - Integrates with the `pyte` library for more sophisticated terminal emulation. It maintains a virtual terminal screen, processes ANSI escape codes, and keeps track of cursor position and screen content. This is ideal for backends that expect a true terminal environment (e.g., many command-line applications, Telnet/SSH sessions).

- **Concrete Interface Implementations**:
    - **`sioba.echo.EchoInterface(Interface)`**: A very basic interface that simply echoes any data it receives from the control back to the control. Useful for testing the frontend connection.
    - **`sioba.function.FunctionInterface(BufferedInterface)`**: Runs a target Python function in a separate thread as the backend. It provides `print()`, `input()`, and `getpass()` methods that are redirected to interact with the connected frontend control.
    - **`sioba.socket.SocketInterface(PersistentInterface)`**: Connects to a specified network host and port (TCP client), acting like a simple Telnet client. It uses `PersistentInterface` to handle terminal escape codes from the remote server.

- **`sioba_nicegui.xterm.XTerm`**:
    - A UI component for the NiceGUI web framework.
    - Renders an `xterm.js` terminal emulator in the web browser.
    - It can be used standalone (e.g., for client-side JavaScript interactions) or, more commonly, connected to a `sioba.base.Interface` instance.
    - When connected to an interface:
        - User input typed into the `XTerm` is sent to the interface's `receive_from_control` method.
        - Data sent by the interface via `send_to_control` (triggered by its `on_send_to_control` callback) is written to the `XTerm` display.

- **`sioba_subprocess.ShellXTerm`**:
    - Provided by the `sioba_subprocess` module (`from sioba_subprocess import ShellXTerm`).
    - A high-level component, often a subclass or composition involving `sioba_nicegui.XTerm` and a dedicated `sioba` interface for managing shell processes.
    - Specifically designed to run and interact with local shell processes (e.g., bash, PowerShell, cmd.exe).
    - Handles the complexities of Pseudo-Terminal (PTY) creation and management for robust shell interaction.

## High-Level Interaction Flow

Consider a `FunctionInterface` connected to an `XTerm` component in a NiceGUI application:

1.  **User Input**: The user types a command (e.g., "hello") into the `XTerm` component displayed in their web browser.
2.  **Frontend to Interface**: The `XTerm` component captures this input and calls the `receive_from_control(b"hello\r")` method of the connected `FunctionInterface` instance.
3.  **Interface Processing**: The `FunctionInterface` receives the data. If its backend Python function was waiting on an `input()` call, this data is provided to that call.
4.  **Backend Logic**: The Python function in the backend runs. For example, it might execute `name = input("Enter name: "); print(f"Hello, {name}")`.
5.  **Backend Output**: When the function calls `print("Hello, username")`, the `FunctionInterface` captures this output.
6.  **Interface to Frontend**: The `FunctionInterface` calls its `send_to_control(b"Hello, username\n")` method. This, in turn, triggers its `on_send_to_control` callback, which the `XTerm` component is listening to.
7.  **Display Output**: The `XTerm` component receives `b"Hello, username\n"` via the callback and displays "Hello, username" in the terminal emulator in the browser.

A similar flow applies to other interfaces like `SocketInterface` or the one used by `ShellXTerm`, with the interface managing communication with its specific backend (a socket or a shell process).

## Examples

Here are a couple of examples to illustrate common use cases:

**1. Quick Web Shell with `ShellXTerm` (from `sioba_subprocess`)**

This example demonstrates how easily you can embed a functional shell into a NiceGUI web page.

```python
# main.py (example usage)
from nicegui import ui
from sioba_subprocess import ShellXTerm

# By default, uses 'bash' on Linux/macOS and 'cmd.exe' on Windows
# ShellXTerm has arguments to customize the shell command, e.g., ShellXTerm(command=['powershell'])
shell_xterm = ShellXTerm()

ui.run()
```
When you run this NiceGUI application, you'll get a web page with a terminal that provides direct access to a shell on the server.

**2. Interactive Python Script with `FunctionInterface` and `XTerm`**

This example shows how to run an interactive Python function and connect it to a web terminal.

```python
# main.py (example usage)
from nicegui import ui
from sioba import FunctionInterface
from sioba_nicegui import XTerm
import time

def my_interactive_function(interface: FunctionInterface):
    """
    An example interactive function.
    Uses interface.print, interface.input, interface.getpass.
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

# Create the XTerm component and link it to the interface
terminal = XTerm().props('rows=20') # Make it a bit taller
terminal.link_interface(func_interface)

# Start the interface (runs the function in a thread)
func_interface.start()

ui.run()
```
This will display a terminal in the browser. The `my_interactive_function` will run on the server, and its `print` and `input` calls will be routed through the `XTerm`.

## Contributing

Contributions are welcome! If you have suggestions for improvements, new features, or bug fixes, please feel free to:
- Open an issue on the GitHub repository to discuss your ideas.
- Submit a pull request with your changes.

Please refer to the project's GitHub page for more details: [Link to GitHub Issues Page - To be updated]

*(Please replace `[Link to GitHub Issues Page - To be updated]` with the actual link to your project's issues page, e.g., `https://github.com/your-username/sioba/issues`)*

## License

This project is licensed under the **MIT-0 License**.

You can find the full license text in the `LICENSE` file in the repository.
*(Ensure a `LICENSE` file with the MIT-0 content exists at the root of your project.)*
