from nicegui import ui, app, Client
from niceterminal import xterm
from niceterminal.utils import generate_id


class TerminalUI:

    # Reference to the nicegui tabs element we organize everything into
    tabs = None

    # Contains the references to each content displayed
    tab_references = None

    def __init__(self,
                 interfaces: "TerminalInterfaces",
                 controller: "TerminalController" = None,
                 client: Client = None,
                 parent=None):
        self.controller = controller
        self.interfaces = interfaces
        self.client = client
        self.parent = parent

        # The tab_references is a dictionary that stores the references to each tab
        # The tab_id is the same as the interface.id
        self.tab_references = {}

        self.id = generate_id()

    def is_deleted(self):
        """ Returns whether the UI has been deleted
        """
        return not self.client.id in Client.instances

    def new_terminal(self, interface: xterm.Interface = None):
        """ When the controller creates a new terminal, we need to add a new tab
            in each client UI
        """
        with self.add_new_tab(interface.id, interface.title).classes("p-0") as content:
            xterm.XTerm(interface=interface).classes("w-full h-full m-0 p-0")
        self.tabs.set_value(content)

    def add_new_tab(self, tab_id: str = None, tab_title: str = ""):
        if not tab_id:
            tab_id = generate_id()

        # Insert new tab before the "+" tab
        with self.tabs:
            tab_title = tab_title or f'Tab {self.controller.interfaces.start_count}'
            tab = ui.tab(
                        name=tab_id,
                        label="",
                    )
            panel_count = len(self.tab_references)
            tab.move(self.tabs, target_index=panel_count+1)

            # Store reference to relevant tab details
            tab_data = {
                "tab": tab,
                "label": None,
                "panel": None,
            }
            self.tab_references[tab_id] = tab_data

            # Add close button to tab
            with tab:
                with ui.row():
                    tab_data["label"] = ui.label(tab_title).classes("normal-case font-mono")
                    ui.badge('🗙', color='transparent')\
                        .props('floating')\
                        .on('click.stop',
                            lambda t=tab_id: self.request_close_tab(t))

        # Add corresponding tab panel
        with self.tab_panels:
            panel = ui.tab_panel(tab)
            panel.tab_id = tab_id
            tab_data["panel"] = panel
            return panel

        return self.tab_panels

    def close_tab(self, tab_id: str):
        if tab_data := self.tab_references.get(tab_id):

            # If we have a current tab, then let's go to the next available
            # tab
            next_tab_id = None
            if self.tabs.value == tab_id:
                tab_order = list(self.tab_references.keys())
                if len(tab_order) > 1:
                    current_tab_index = tab_order.index(tab_id)
                    try:
                        next_tab_id = tab_order[current_tab_index + 1]
                    except IndexError:
                        next_tab_id = tab_order[current_tab_index - 1]
                else:
                    next_tab_id = "home"

            self.tabs.remove(tab_data["tab"])
            self.tab_panels.remove(tab_data["panel"])
            del self.tab_references[tab_id]

            if next_tab_id:
                self.tabs.set_value(next_tab_id)

    def request_new_terminal(self):
        """ This is called when the user requests a new tab in the UI

            This allows us to bring the request to start a new terminal
            back to the server. Then we can send the request into the
            controller where it is then able to create a new terminal,
            then dispatch the new tab to all the connected clients
        """
        self.controller.new_terminal()

    def request_close_tab(self, tab_id: str):
        self.controller.close_interface(tab_id)

    async def on_set_terminal_title_handle(self, interface: xterm.Interface, title: str) -> None:
        if tab_data := self.tab_references.get(interface.id):
            tab_data["label"].set_text(f"{interface.creation_index}: {title}")

    def render(self):
        if not self.parent:
            self.parent = ui.element("div").classes("w-full h-screen m-0 p-0")

        # This establishes the basic terminal layout
        with self.parent:
            with ui.column().classes("w-full h-full m-0 p-0"):

                # Create the tabs
                self.tabs = ui.tabs()
                with self.tabs:
                    self.home_tab = ui.tab(name="home", label="", icon="home")
                    self.add_tab = ui.tab(
                                        name="_add_terminal",
                                        label="",
                                        icon="add_circle",
                                    )
                    self.add_tab.on("click.stop", self.request_new_terminal)

                # Basic Panel
                self.tab_panels = ui.tab_panels(self.tabs, value=self.home_tab)
                self.tab_panels.classes("w-full h-full m-0 p-0")
                with self.tab_panels:
                     with ui.tab_panel(self.home_tab).classes("p-5"):
                        ui.label("Welcome to the terminal")
                        ui.button("New Terminal").on("click", self.request_new_terminal)

        for interface in self.controller.interfaces:
            self.new_terminal(interface)

        return self
