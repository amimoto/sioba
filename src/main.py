from nicegui import ui, app
from niceterminal import xterm

from niceterminal.utils.interface import PosixInterface, PersistentInterface

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
    interfaces = app.storage.user.setdefault("interfaces",{})
    if (
            ( interface_id := interfaces.get("bash") )
            and ( interface := PROCESSES.get(interface_id) )
        ):
        print("Pulling from cached!")
    else:
        primary_interface = PosixInterface("/bin/bash")
        interface = PersistentInterface(primary_interface)
        interface.start()
        interface_id = id(interface)
        interfaces["bash"] = interface_id
        PROCESSES[interface_id] = interface

    with ui.element("div").classes("w-full h-screen m-0 p-0"):
        with ui.column().classes("w-full h-full m-0 p-0"):
            xterm.XTerm(interface=interface).classes("w-full h-full m-0 p-0")
            ui.button("Close").on_click(lambda: interface.write("exit\n"))


ui.run(storage_secret="kjas;lkdjf;lasjdf;lijasd;fjaskdfa")

