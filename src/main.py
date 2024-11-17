from nicegui import ui
from components import xterm

# Define your NiceGUI app
@ui.page('/')
async def index():
    ui.label("Hello.")
    xterm.XTermJS(value="echo 'Hello, world!'")

# Run the NiceGUI app
ui.run()

