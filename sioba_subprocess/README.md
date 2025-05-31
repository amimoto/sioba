# sioba_subprocess

**sioba_subprocess** is a Python module that provides a convenient way to integrate shell subprocess interaction into [NiceGUI](https://nicegui.io/) applications. It builds upon the `sioba_nicegui` library to offer a specialized `ShellXTerm` component that acts as a terminal emulator connected to a real shell process running on the server.

This module is designed to make it easy to add interactive command-line interfaces to your NiceGUI web applications.

## Features

*   **Easy Shell Integration:** Quickly embed a functional shell terminal in your NiceGUI projects.
*   **Cross-Platform Compatibility:** Works on both POSIX (Linux/macOS) and Windows systems.
    *   Automatically detects and uses appropriate shell commands (e.g., `/bin/bash` on POSIX, `cmd.exe` on Windows).
    *   Allows specifying a custom shell invocation command.
*   **Full Subprocess Management:** Handles the lifecycle of the shell subprocess, including starting, stopping, and communication.
*   **Interactive I/O:** Supports sending commands to the shell and displaying its output in real-time.
*   **Terminal Emulation Features:** Inherits terminal features from `sioba_nicegui.XTerm`, such as terminal resizing.

## Installation

You can install `sioba_subprocess` using pip:

```bash
pip install sioba_subprocess
```

Alternatively, if you are working with the `sioba` monorepo locally, you might use PDM for installation:

```bash
pdm install -G local
```

## Usage

Here's a basic example of how to use `ShellXTerm` in a NiceGUI application:

```python
from nicegui import ui
from sioba_subprocess import ShellXTerm # Corrected import path

# Create a ShellXTerm instance
# It will automatically start the default system shell.
term = ShellXTerm()

# Apply styling (e.g., make it fill the available space)
term.classes("w-full h-full")

# Run the NiceGUI application
ui.run()
```

The `ShellXTerm` component can be customized with several parameters:

*   `invoke_command (str)`: The command used to launch the shell (e.g., `/bin/zsh`, `powershell.exe`). Defaults to the system's standard shell.
*   `shutdown_command (str)`: An optional command to gracefully shut down the shell.
*   `cwd (str)`: The current working directory for the shell process.
*   `config (TerminalConfig)`: An optional `TerminalConfig` object from `sioba_nicegui.xterm` to customize terminal behavior (e.g., rows, cols).

## How it Works

Under the hood, `sioba_subprocess` uses platform-specific mechanisms to create and interact with subprocesses:

*   **On POSIX systems:** It utilizes pseudo-terminals (`pty`) to communicate with the shell process, providing a more authentic terminal experience.
*   **On Windows:** It uses the `pywinpty` library (if available for older versions, or direct API calls for newer ones) to manage subprocess communication.

The `ShellInterface` class within the module abstracts these differences, providing a consistent way for `ShellXTerm` to operate.

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request on the [GitHub repository](https://github.com/amimoto/sioba).

## License

`sioba_subprocess` is licensed under the MIT No Attribution (MIT-0) license. See the [LICENSE](../../LICENSE) file for more details.
