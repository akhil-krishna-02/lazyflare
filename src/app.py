import os
import asyncio
from dotenv import load_dotenv
from cloudflare import Cloudflare
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListItem, ListView, Label, DataTable, Input, RichLog, Button
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual import on, work, events

load_dotenv()

# --- MODALS ---

class ConfirmModal(ModalScreen[bool]):
    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(self.message, id="modal-msg")
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Proceed", variant="error", id="confirm")

    @on(Button.Pressed, "#confirm")
    def confirm(self): self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def cancel(self): self.dismiss(False)

class HelpScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Label("LAZY CLOUDFLARE COMMANDS", id="help-title")
            yield Static(
                " [yellow]Global[/]\n"
                " q      : Quit\n"
                " r      : Refresh View\n"
                " tab    : Switch Pane\n"
                " /      : Search/Filter\n"
                " d      : Delete Selected Item (with confirm)\n"
                " ?      : This Help Menu\n\n"
                " [yellow]DNS Actions[/]\n"
                " space  : Toggle Proxy (Orange/White Cloud)\n"
                " p      : Purge Everything (Cache for Zone)\n"
                " [yellow]Navigation[/]\n"
                " enter  : Drill down (View KV Keys, etc.)\n"
                " esc    : Go back to list",
                id="help-text"
            )
            yield Button("Close", id="close-help")

    @on(Button.Pressed, "#close-help")
    def close(self): self.dismiss()

class InfoModal(ModalScreen):
    def __init__(self, title: str, content: str):
        super().__init__()
        self.modal_title = title
        self.modal_content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="info-container"):
            yield Label(self.modal_title, id="info-title")
            yield Static(self.modal_content, id="info-content")
            yield Button("Close", id="close-info")

    @on(Button.Pressed, "#close-info")
    def close(self): self.dismiss()

# --- MAIN APP ---

class Pane(Vertical): pass

class LazyCloudflare(App):
    CSS = """
    Screen { layout: horizontal; background: #000000; }
    #left-col { width: 30%; height: 100%; }
    #right-col { width: 70%; height: 100%; }

    Pane { border: round #555555; background: #000000; height: 1fr; padding: 0 1; }
    Pane:focus-within { border: round #f6821f; }
    #status-p { height: 12%; }
    #res-p { height: 48%; }
    #item-p { height: 40%; }
    #main-p { height: 75%; }
    #log-p { height: 25%; }

    DataTable { height: 100%; background: #000000; }
    ListView { height: 100%; background: #000000; }
    Input { border: none; background: #111111; margin-bottom: 1; }

    /* Modals */
    #modal-container, #help-container, #info-container {
        width: 60; height: auto; background: #1e1e1e;
        border: thick #f6821f; padding: 1; align: center middle;
    }
    #modal-msg, #help-title, #info-title { text-align: center; margin: 1; text-style: bold; color: #f6821f; }
    #modal-buttons { align: center middle; height: 3; }
    #info-content { padding: 1; height: auto; max-height: 20; overflow-y: auto; }
    Button { margin: 0 1; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("/", "focus_filter", "Filter"),
        ("?", "show_help", "Help"),
        ("tab", "switch_focus", "Next Pane"),
        ("space", "toggle_proxy", "Toggle Proxy"),
        ("p", "purge_cache", "Purge Cache"),
        ("d", "delete_item", "Delete"),
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = Cloudflare(api_token=os.getenv("CLOUDFLARE_API_TOKEN"))
        self.account_id = None
        self.current_view = "welcome"
        self.is_drilled_down = False
        self.active_namespace = None
        self.item_map = {} # Maps row key to full dict of item data
        self.all_rows = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="left-col"):
                with Pane(id="status-p") as p:
                    p.border_title = "Status"
                    yield Static("Account: [bold yellow]Auth...[/]", id="acc-status")
                with Pane(id="res-p") as p:
                    p.border_title = "Resources"
                    yield ListView(
                        ListItem(Label("Workers"), id="nav-workers"),
                        ListItem(Label("DNS Zones"), id="nav-dns"),
                        ListItem(Label("KV Store"), id="nav-kv"),
                        ListItem(Label("D1 Databases"), id="nav-d1"),
                        ListItem(Label("R2 Storage"), id="nav-r2"),
                        ListItem(Label("Pages Projects"), id="nav-pages"),
                        ListItem(Label("Zero Trust Tunnels"), id="nav-tunnels"),
                        id="res-list"
                    )
                with Pane(id="item-p") as p:
                    p.border_title = "Context"
                    yield ListView(id="item-list")

            with Vertical(id="right-col"):
                with Pane(id="main-p") as p:
                    p.border_title = "Main Console"
                    yield Input(placeholder="Type to filter...", id="filter")
                    yield DataTable(id="data-table", cursor_type="row")
                with Pane(id="log-p") as p:
                    p.border_title = "Action Logs"
                    yield RichLog(id="logs", highlight=True, markup=True)
        yield Footer()

    def log(self, msg: str): self.query_one("#logs", RichLog).write(msg)

    async def get_acc(self):
        if self.account_id: return self.account_id
        try:
            for a in self.client.accounts.list():
                self.account_id = a.id
                return a.id
        except: return None

    async def on_mount(self):
        acc = await self.get_acc()
        self.query_one("#acc-status").update(f"Acc: [green]{acc[:8] if acc else 'ERR'}...[/]")
        self.log(f"[green]✔ Connected to Cloudflare ({acc})[/]" if acc else "[red]✖ Auth Failed[/]")
        self.query_one("#res-list").focus()

    def action_show_help(self): self.push_screen(HelpScreen())

    def action_switch_focus(self):
        focus_order = [self.query_one("#res-list"), self.query_one(DataTable), self.query_one("#filter")]
        try:
            idx = focus_order.index(self.focused)
            focus_order[(idx + 1) % len(focus_order)].focus()
        except: focus_order[0].focus()

    @on(Input.Changed, "#filter")
    def filter_table(self, event):
        table = self.query_one(DataTable)
        term = event.value.lower()
        table.clear(columns=False)
        for row in self.all_rows:
            if any(term in str(c).lower() for c in row): table.add_row(*row)

    @on(ListView.Selected, "#res-list")
    @work(exclusive=True)
    async def nav_change(self, event):
        self.is_drilled_down = False
        self.active_namespace = None
        self.current_view = event.item.id
        table, items, main = self.query_one(DataTable), self.query_one("#item-list"), self.query_one("#main-p")
        main.border_title = f"View: {event.item.children[0].renderable}"
        table.clear(columns=True); items.clear(); self.all_rows = []; self.item_map.clear()
        
        acc = await self.get_acc()
        if not acc: return

        try:
            if self.current_view == "nav-workers":
                table.add_columns("ID", "Modified")
                for w in self.client.workers.scripts.list(account_id=acc):
                    row = (w.id, getattr(w, 'modified_on', 'N/A'))
                    rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(w.id)))
                    self.item_map[str(rk)] = {"type": "worker", "id": w.id}
            
            elif self.current_view == "nav-dns":
                table.add_columns("Type", "Name", "Content", "Proxy", "ZoneID")
                for z in self.client.zones.list():
                    items.append(ListItem(Label(z.name)))
                    for r in self.client.dns.records.list(zone_id=z.id):
                        row = (r.type, r.name, r.content, "🟠" if r.proxied else "⚪", z.id)
                        rk = table.add_row(*row); self.all_rows.append(row)
                        self.item_map[str(rk)] = {"type": "dns", "id": r.id, "zone": z.id, "proxied": r.proxied}

            elif self.current_view == "nav-kv":
                table.add_columns("Namespace ID", "Title")
                for ns in self.client.kv.namespaces.list(account_id=acc):
                    row = (ns.id, ns.title)
                    rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(ns.title)))
                    self.item_map[str(rk)] = {"type": "kv_ns", "id": ns.id, "title": ns.title}

            elif self.current_view == "nav-d1":
                table.add_columns("DB Name", "UUID", "Version")
                try:
                    for db in self.client.d1.database.list(account_id=acc):
                        row = (db.name, db.uuid, str(db.version))
                        rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(db.name)))
                        self.item_map[str(rk)] = {"type": "d1", "id": db.uuid}
                except AttributeError: self.log("[red]D1 API not fully accessible with this token/SDK.[/]")

            elif self.current_view == "nav-pages":
                table.add_columns("Project Name", "Subdomain", "Created")
                for p in self.client.pages.projects.list(account_id=acc):
                    row = (p.name, getattr(p, 'subdomain', 'N/A'), str(getattr(p, 'created_on', 'N/A'))[:10])
                    rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(p.name)))
                    self.item_map[str(rk)] = {"type": "pages", "name": p.name}
                    
            elif self.current_view == "nav-tunnels":
                table.add_columns("Tunnel Name", "ID", "Status")
                try:
                    for t in self.client.zero_trust.tunnels.list(account_id=acc):
                        row = (t.name, t.id, t.status)
                        rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(t.name)))
                        self.item_map[str(rk)] = {"type": "tunnel", "id": t.id}
                except Exception as e: self.log("[red]Tunnels API requires Zero Trust permissions.[/]")

            self.log(f"[green]✔ Loaded {len(self.all_rows)} items.[/]")
            table.focus()
        except Exception as e: self.log(f"[red]✖ API Error: {str(e)}[/]")

    @on(DataTable.RowSelected)
    @work(exclusive=True)
    async def handle_drilldown(self, event):
        table = self.query_one(DataTable)
        row_key = str(event.row_key)
        data = self.item_map.get(row_key)
        if not data: return

        acc = await self.get_acc()

        if data["type"] == "kv_ns":
            # Drill into KV Keys
            self.is_drilled_down = True
            self.active_namespace = data["id"]
            table.clear(columns=True)
            self.all_rows = []; self.item_map.clear()
            self.log(f"[yellow]Fetching keys for KV {data['title']}...[/]")
            
            try:
                table.add_columns("Key Name", "Expiration")
                for k in self.client.kv.namespaces.keys.list(account_id=acc, namespace_id=data["id"]):
                    row = (k.name, str(getattr(k, 'expiration', 'None')))
                    rk = table.add_row(*row); self.all_rows.append(row)
                    self.item_map[str(rk)] = {"type": "kv_key", "name": k.name, "ns_id": data["id"]}
                self.log(f"[green]✔ Loaded {len(self.all_rows)} keys.[/]")
            except Exception as e: self.log(f"[red]✖ Error fetching keys: {e}[/]")

        elif data["type"] == "kv_key":
            # View KV Value
            self.log(f"[yellow]Fetching value for key {data['name']}...[/]")
            try:
                # SDK might return bytes or string depending on version, generic catch
                val = self.client.kv.namespaces.values.get(
                    account_id=acc, namespace_id=data["ns_id"], key_name=data["name"]
                )
                self.push_screen(InfoModal(f"Key: {data['name']}", str(val)))
            except Exception as e: self.log(f"[red]✖ Error fetching value: {e}[/]")

    async def action_delete_item(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        
        row_key = list(table.rows.keys())[table.cursor_row]
        data = self.item_map.get(str(row_key))
        if not data: return

        if await self.push_screen_wait(ConfirmModal("Are you sure you want to DELETE this item?")):
            acc = await self.get_acc()
            try:
                if data["type"] == "dns":
                    self.client.dns.records.delete(dns_record_id=data["id"], zone_id=data["zone"])
                elif data["type"] == "worker":
                    self.client.workers.scripts.delete(script_name=data["id"], account_id=acc)
                elif data["type"] == "kv_ns":
                    self.client.kv.namespaces.delete(namespace_id=data["id"], account_id=acc)
                elif data["type"] == "kv_key":
                    self.client.kv.namespaces.values.delete(
                        account_id=acc, namespace_id=data["ns_id"], key_name=data["name"]
                    )
                self.log("[green]✔ Item deleted successfully.[/]")
                table.remove_row(row_key)
            except Exception as e:
                self.log(f"[red]✖ Delete failed: {e}[/]")

    async def action_purge_cache(self):
        if self.current_view != "nav-dns": return
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        
        row_key = list(table.rows.keys())[table.cursor_row]
        zone_id = self.item_map.get(str(row_key))["zone"]
        
        if await self.push_screen_wait(ConfirmModal("Purge Everything for this Zone?")):
            try:
                self.client.zones.purge_cache(zone_id=zone_id, purge_everything=True)
                self.log("[green]✔ Cache Purged![/]")
            except Exception as e: self.log(f"[red]✖ Failed: {e}[/]")

    async def action_toggle_proxy(self):
        if self.current_view != "nav-dns": return
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        
        row_key = list(table.rows.keys())[table.cursor_row]
        data = self.item_map.get(str(row_key))
        
        new_state = not data["proxied"]
        try:
            self.client.dns.records.update(
                dns_record_id=data["id"], zone_id=data["zone"], proxied=new_state
            )
            data["proxied"] = new_state
            table.update_cell(row_key, "Proxy", "🟠" if new_state else "⚪")
            self.log(f"[green]✔ Proxy toggled to {new_state}.[/]")
        except Exception as e: self.log(f"[red]✖ Toggle failed: {e}[/]")

    def action_go_back(self):
        self.query_one("#filter").value = ""
        if self.is_drilled_down:
            # Reload KV namespaces
            sidebar_list = self.query_one("#res-list", ListView)
            self.post_message(ListView.Selected(sidebar_list, sidebar_list.children[2]))
        else:
            self.log("[cyan]↻ Filter cleared.[/cyan]")

def main(): LazyCloudflare().run()
if __name__ == "__main__": main()
