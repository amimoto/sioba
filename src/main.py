from nicegui import ui, Client
from niceterminal import xterm

from niceterminal.utils.subprocess import InvokeProcess 

@ui.page('/')
async def index(client: Client):
    ui.page_title("Terminal")

    ui.add_head_html('''
    <style>
        .nicegui-content {
            padding: 0;
        }
    </style>
    ''')

    dark = ui.dark_mode()
    dark.enable()

    term = xterm.XTerm().classes("w-full h-screen m-0 p-0")

    def on_read(data):
        term.write(data.decode('utf-8'))
    process = InvokeProcess(
                        invoke_command="/bin/bash",
                        on_read=on_read,
                    )
    await process.start()

    async def on_render(e):
        process.set_size(
            await term.rows(),
            await term.cols()
        )
    term.on("render", on_render)

    async def on_resize(e):
        if rows := e.args.get("rows"):
            if cols := e.args.get("cols"):
                process.set_size(rows, cols)
    term.on("resize", on_resize)

    async def on_input(e):
        if isinstance(e.args, str):
            data = e.args
            await process.write(data)
    term.on("input", on_input)

    async def on_close(term):
        await process.shutdown()
    term.on_close(on_close)


# Run the NiceGUI app
ui.run()

