# NiceTerminal: A NiceGUI xterm.js Control

This **WIP** project provides an xTerm.js based control to be added to your nicegui projects that should work in both Linux and Windows environments.

Simple auto-index page example:

```python
from nicegui import ui
from niceterminal.xterm import ShellXTerm

ShellXTerm().classes("w-full h-full")

ui.run()
```

Which yields:

![](niceterminal.png)

Just wanted a terminal element for NiceGUI to hook it to a CLI shell and this is just my efforts in exploring how it works. If you've stumbled upon this, have a look at the `main.py` in the src directory.

## Featurs

- Support for auto-index pages
- Concurrent access
- Cache screen state for reloads
- Works on Linux and Windows
- Works with a local shell terminal out of the box 
- Designed to handle terminal needs not just provide CLI access to local system

