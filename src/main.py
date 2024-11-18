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


    term = xterm.XTerm().classes("w-full h-screen m-0 p-0")

    # We launch a long running process if it hasn't been started yet
    def on_read(data):
        term.write(data.decode('utf-8'))
    shell = InvokeProcess('/bin/bash', None, on_read=on_read)

    await shell.start()

    async def on_render(e):
        shell.set_size(await term.rows(), await term.cols())
    term.on("render", on_render)

    async def on_resize(e):
        if rows := e.args.get("rows"):
            if cols := e.args.get("cols"):
                shell.set_size(rows, cols)
    term.on("resize", on_resize)

    async def on_input(e):
        if isinstance(e.args, str):
            data = e.args
            await shell.write(data)
            #term.write(data)
    term.on("input", on_input)

# Run the NiceGUI app
ui.run()

