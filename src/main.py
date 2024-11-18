from nicegui import ui
from nicegui_terminal import xterm

from nicegui_terminal.utils.subprocess import InvokeProcess 

@ui.page('/')
async def index():
    ui.add_head_html('''
    <style>
        .nicegui-content {
            padding: 0;
        }
    </style>
    ''')

    dark = ui.dark_mode()
    dark.enable()

    term = xterm.XTermProcess("/bin/bash").classes("w-full h-screen m-0 p-0")
    await term.start()



# Run the NiceGUI app
ui.run()

