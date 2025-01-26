# NiceTerminal: A NiceGUI xterm.js Control

This **WIP** project provides an xTerm.js based control to be added to your [NiceGUI](https://nicegui.io/) projects that should work in both Linux and Windows environments.

This is is **not** an official [NiceGUI](https://nicegui.io/) project.

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

## Features

- Support for auto-index pages
- Concurrent access
- Cache screen state for reloads
- Works on Linux and Windows
- Works with a local shell terminal out of the box
- Designed to handle terminal needs not just provide CLI access to local system
- Commandline `niceterm` optional install that allows a multi-term web based local shell

## `niceterminal` Library

The primary architecture of niceterminal is:

- The element `niceterminal.xterm.XTerm` (using [xterm.js](https://xtermjs.org/))
- and an interface to a data source usually a subclass of `niceterminal.interface.Interface` which provides the abstract base class for IO to whatever data source we wish to interact with.

While unique `XTerm` instances are created for each terminal presented to a user be it on the same page, tab, browsers, `Interface` instances may be shared. In other words, this means that it's possible to create a single shell session that is shared amongst a number of `XTerms` similar to how `screen` or `tmux` work. This is also done so that `Interfaces` can be log lived and survive refreshes of the page without forcing a reconnection to whatever IO source is required.

### `Interface` Class

## `niceterm` Command Line Client

If `niceterminal` is installed with the `cli` option, a command `niceterm` becomes avaliable with the following switches.

```
NiceTerminal Web Interface

Usage:
    niceterm [options]
    niceterm -h | --help
    niceterm --version

Options:
  -h --help                    Show this help.
  --version                    Show version.
  --host=<host>                Host to bind web interface [default: 0.0.0.0].
  --port=<port>                Port for web interface [default: 8080].
  --app=<command>              Default application to start in new terminals [default: bash].
  --password=<pass>            Set authentication password
  --no-auth                    Disable authentication requirement. Incompatible with --password.
  --light-mode                 Use light mode.
  --log-level=<level>          Set log level [default: INFO].
  --isolation=<level>          At what level are terminals shared: [default: global]
                                    - global: everyone
                                    - user: brower
                                    - tab: only for tab

Examples:
  niceterminal --host 0.0.0.0 --port 9000
  niceterminal --app 'python3' --no-auth
  niceterminal --password secret123
```

When starting just from the command line without any arguments, the output will look something like the following:

```
2025-01-25 18:11:59.941 | INFO     | niceterminal.cli:main:179 - Generated password: 9ddfb7119b66ed07c28b633e9454d49d1a5f42ff72d0495babc2129aaaeef75b
NiceGUI ready to go on http://localhost:8080, http://172.17.0.1:8080, http://172.22.0.1:8080, and http://192.168.198.12:8080
```

Grab the password and use it at the authentication screen:

![](niceterminal-authentication.png)

Authentication will give access to the the terminal interface where new shells or applications can be started.

![](niceterminal-webterminal.png)

## Installation

For just the library

```bash
pip install niceterminal
```

To get the CLI as well. Just separated to ensure that a tool that can so easily be a security compromise becomes a conscious choice.

```bash
pip install niceterminal[cli]
```


