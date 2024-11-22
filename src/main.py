from nicegui import ui, app
from niceterminal import xterm

from niceterminal.utils.subprocess import InvokeProcess 

PROCESSES = {}

@ui.page('/')
async def index():
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

    # Let's start a process if it hasn't yet
    processes = app.storage.user.setdefault("processes",{})
    if (
            ( process_id := processes.get("bash") )
            and ( process := PROCESSES.get(process_id) )
        ):
        print("Pulling from cached!")
    else:
        process = InvokeProcess("/bin/bash")
        process.start()
        process_id = id(process)
        processes["bash"] = process_id
        PROCESSES[process_id] = process

    with ui.element("div").classes("w-full h-screen m-0 p-0"):
        with ui.column().classes("w-full h-full m-0 p-0"):
            xterm.XTerm(process=process).classes("w-full h-full m-0 p-0")
            ui.button("Close").on_click(lambda: process.write("exit\n"))


ui.run(storage_secret="kjas;lkdjf;lasjdf;lijasd;fjaskdfa")

