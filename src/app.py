import os
import asyncio
import pyperclip
from pathlib import Path
from dotenv import load_dotenv
from cloudflare import AsyncCloudflare
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListItem, ListView, Label, DataTable, Input, RichLog, Button
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual import on, work, events

# Load environment variables (from .env or config file)
load_dotenv()
config_path = Path.home() / ".config" / "lazyflare" / "config"
if config_path.exists():
    load_dotenv(config_path)

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
            yield Label("LAZYFLARE COMMANDS", id="help-title")
            yield Static(
                " [yellow]Global Navigation[/]\n"
                " j/k      : Move Up/Down\n"
                " h/l      : Go Back / Drill Down\n"
                " tab      : Switch Pane\n"
                " /        : Focus Filter / Command Bar\n"
                " ?        : This Help Menu\n\n"
                " [yellow]Commands & Actions[/]\n"
                " c        : Copy Item JSON/ID\n"
                " space    : Toggle Proxy (DNS)\n"
                " p        : Purge Cache (DNS view)\n"
                " d        : Delete Item\n"
                " enter    : Drill down / View Value\n"
                " esc      : Back / Clear\n\n"
                " [yellow]System[/]\n"
                " q, /quit : Quit\n"
                " r, /ref  : Refresh View\n"
                " m, /mock : Toggle Mock Mode",
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
    Screen { layout: vertical; background: #181825; } /* Catppuccin Mocha/Macchiato dark */
    
    #header { height: 3; dock: top; background: #11111b; border-bottom: solid #313244; padding: 0 1; }
    #header-content { layout: horizontal; align: left middle; }
    #app-title { text-style: bold; color: #f6821f; width: auto; margin-right: 4; } /* Cloudflare Orange */
    #acc-status { color: #cdd6f4; width: auto; margin-right: 4; }
    #mode-status { color: #a6e3a1; width: auto; }

    #main-content { layout: horizontal; height: 1fr; }
    
    #left-col { width: 25%; height: 100%; border-right: vkey #313244; }
    #right-col { width: 75%; height: 100%; }

    Pane { border: solid #313244; background: #1e1e2e; padding: 0 1; height: 1fr; }
    Pane:focus-within { border: double #f6821f; }
    
    Pane > .pane-title { color: #f6821f; text-style: bold; margin-bottom: 1; }

    #res-p { height: 100%; border: none; }
    #main-p { height: 75%; border: none; border-bottom: hkey #313244; }
    #log-p { height: 25%; border: none; }

    DataTable { height: 100%; background: #1e1e2e; color: #cdd6f4; }
    ListView { height: 100%; background: #1e1e2e; }
    ListItem { padding: 0 1; color: #cdd6f4; }
    ListItem:focus { background: #f6821f; color: #11111b; text-style: bold; }
    
    Input { border: none; background: #313244; margin-bottom: 1; color: #cdd6f4; }
    Input:focus { border: tall #f6821f; }

    /* Modals */
    #modal-container, #help-container, #info-container {
        width: 60; height: auto; background: #181825;
        border: thick #f6821f; padding: 1; align: center middle;
    }
    #modal-msg, #help-title, #info-title { text-align: center; margin: 1; text-style: bold; color: #f6821f; }
    #modal-buttons { align: center middle; height: 3; }
    #info-content { padding: 1; height: auto; max-height: 20; overflow-y: auto; color: #a6e3a1; }
    Button { margin: 0 1; background: #45475a; color: #cdd6f4; }
    Button:hover { background: #f6821f; color: #11111b; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("/", "focus_filter", "Filter/Cmd"),
        ("?", "show_help", "Help"),
        ("m", "toggle_mock", "Toggle Mock"),
        ("tab", "switch_focus", "Next Pane"),
        ("space", "toggle_proxy", "Toggle Proxy"),
        ("p", "purge_cache", "Purge Cache"),
        ("d", "delete_item", "Delete"),
        ("escape", "go_back", "Back"),
        ("h", "go_back", "Go Back"),
        ("l", "drill_down", "Expand"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("c", "copy_item", "Copy"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = AsyncCloudflare(api_token=os.getenv("CLOUDFLARE_API_TOKEN", "mock_token"))
        self.account_id = None
        self.current_view = "welcome"
        self.is_drilled_down = False
        self.is_mock_mode = False
        self.item_map = {}
        self.all_rows = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="header"):
            with Horizontal(id="header-content"):
                yield Static("🟠 LAZYFLARE", id="app-title")
                yield Static("Account: [yellow]Authenticating...[/]", id="acc-status")
                yield Static("Mode: [green]Real[/]", id="mode-status")

        with Horizontal(id="main-content"):
            # LEFT COLUMN: Resources
            with Vertical(id="left-col"):
                with Pane(id="res-p"):
                    yield Label("RESOURCES", classes="pane-title")
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

            # RIGHT COLUMN: Details & Commands
            with Vertical(id="right-col"):
                with Pane(id="main-p"):
                    yield Label("DETAILS", classes="pane-title")
                    yield Input(placeholder="Type to filter or /command...", id="filter")
                    yield DataTable(id="data-table", cursor_type="row")
                with Pane(id="log-p"):
                    yield Label("COMMANDS & LOGS", classes="pane-title")
                    yield RichLog(id="logs", highlight=True, markup=True)
        
        # Footer for quick key bindings
        yield Footer()

    def write_log(self, msg: str):
        self.query_one("#logs", RichLog).write(msg)

    async def get_acc(self):
        if self.is_mock_mode: return "mock_account_12345"
        if self.account_id: return self.account_id
        try:
            async for a in self.client.accounts.list():
                self.account_id = a.id
                return a.id
        except: return None

    async def on_mount(self):
        acc = await self.get_acc()
        self.query_one("#acc-status").update(f"Acc: [green]{acc[:8] if acc else 'ERR'}...[/]")
        self.write_log(f"[green]✔ Connected to Cloudflare ({acc})[/]" if acc else "[red]✖ Auth Failed[/]")
        self.query_one("#res-list").focus()

    def action_show_help(self): self.push_screen(HelpScreen())

    def action_toggle_mock(self):
        self.is_mock_mode = not self.is_mock_mode
        self.query_one("#mode-status").update(f"Mode: {'[bold orange]Mock[/]' if self.is_mock_mode else '[green]Real[/]'}")
        self.write_log(f"[bold cyan]Switching to {'Mock' if self.is_mock_mode else 'Real'} mode...[/]")
        self.reload_current_view()

    def reload_current_view(self):
        res_list = self.query_one("#res-list", ListView)
        if res_list.index is not None:
            view_id = res_list.children[res_list.index].id
            self.run_worker(self.load_view_data(view_id), exclusive=True)

    def action_switch_focus(self):
        focus_order = [self.query_one("#res-list"), self.query_one(DataTable), self.query_one("#filter")]
        try:
            idx = focus_order.index(self.focused)
            focus_order[(idx + 1) % len(focus_order)].focus()
        except: focus_order[0].focus()

    @on(Input.Submitted, "#filter")
    def handle_command(self, event: Input.Submitted):
        cmd = event.value.strip().lower()
        if not cmd.startswith("/"): return

        if cmd == "/help": self.action_show_help()
        elif cmd in ["/mock", "/m"]: self.action_toggle_mock()
        elif cmd in ["/quit", "/q"]: self.action_quit()
        elif cmd in ["/refresh", "/r"]: self.reload_current_view()
        elif cmd == "/purge": self.run_worker(self.action_purge_cache())
        elif cmd == "/delete": self.run_worker(self.action_delete_item())
        else: self.write_log(f"[red]✖ Unknown command: {cmd}[/]")
        event.input.value = ""

    @on(Input.Changed, "#filter")
    def filter_table(self, event):
        if event.value.startswith("/"): return
        table = self.query_one(DataTable)
        term = event.value.lower()
        table.clear(columns=False)
        for row in self.all_rows:
            if any(term in str(c).lower() for c in row): table.add_row(*row)

    @on(ListView.Selected, "#res-list")
    @work(exclusive=True)
    async def on_nav_select(self, event):
        await self.load_view_data(event.item.id)

    async def load_view_data(self, view_id):
        self.is_drilled_down = False
        self.current_view = view_id
        table, items, main = self.query_one(DataTable), self.query_one("#item-list"), self.query_one("#main-p")
        table.clear(columns=True); items.clear(); self.all_rows = []; self.item_map.clear()

        acc = await self.get_acc()
        if not acc: return

        if self.is_mock_mode:
            self.load_mock_data(table, items)
            return

        try:
            if self.current_view == "nav-workers":
                table.add_columns("ID", "Modified")
                async for w in self.client.workers.scripts.list(account_id=acc):
                    row = (w.id, getattr(w, 'modified_on', 'N/A'))
                    rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(w.id)))
                    self.item_map[str(rk)] = {"type": "worker", "id": w.id}

            elif self.current_view == "nav-dns":
                table.add_columns("Type", "Name", "Content", "Proxy", "ZoneID")
                async for z in self.client.zones.list():
                    items.append(ListItem(Label(z.name)))
                    async for r in self.client.dns.records.list(zone_id=z.id):
                        row = (r.type, r.name, r.content, "🟠" if r.proxied else "⚪", z.id)
                        rk = table.add_row(*row); self.all_rows.append(row)
                        self.item_map[str(rk)] = {
                            "id": r.id, "zone": z.id, "proxied": r.proxied, 
                            "type": "dns", "record_type": r.type, 
                            "name": r.name, "content": r.content
                        }

            elif self.current_view == "nav-kv":
                table.add_columns("Namespace ID", "Title")
                async for ns in self.client.kv.namespaces.list(account_id=acc):
                    row = (ns.id, ns.title)
                    rk = table.add_row(*row); self.all_rows.append(row); items.append(ListItem(Label(ns.title)))
                    self.item_map[str(rk)] = {"type": "kv_ns", "id": ns.id, "title": ns.title}

            elif self.current_view == "nav-d1":
                table.add_columns("DB Name", "UUID", "Version")
                async for db in self.client.d1.database.list(account_id=acc):
                    row = (db.name, db.uuid, str(db.version))
                    rk = table.add_row(*row); self.all_rows.append(row)
                    self.item_map[str(rk)] = {"type": "d1", "id": db.uuid}

            elif self.current_view == "nav-pages":
                table.add_columns("Project", "URL", "Created")
                async for p in self.client.pages.projects.list(account_id=acc):
                    row = (p.name, getattr(p, 'subdomain', 'N/A'), str(getattr(p, 'created_on', 'N/A'))[:10])
                    table.add_row(*row); self.all_rows.append(row)

            elif self.current_view == "nav-tunnels":
                table.add_columns("Tunnel Name", "ID", "Status")
                async for t in self.client.zero_trust.tunnels.list(account_id=acc):
                    row = (t.name, t.id, t.status)
                    table.add_row(*row); self.all_rows.append(row)

            self.write_log(f"[green]✔ Loaded {len(self.all_rows)} items.[/]")
        except Exception as e:
            self.write_log(f"[red]✖ API Error: {str(e)}[/]")

    def load_mock_data(self, table, items):
        if self.current_view == "nav-workers":
            table.add_columns("ID", "Modified")
            for i in range(5):
                row = (f"worker-service-{i}", "2026-03-22")
                rk = table.add_row(*row); self.all_rows.append(row)
                self.item_map[str(rk)] = {"type": "worker", "id": row[0]}
        elif self.current_view == "nav-dns":
            table.add_columns("Type", "Name", "Content", "Proxy", "ZoneID")
            for i in range(8):
                row = ("A", f"site-{i}.com", f"1.1.1.{i}", "🟠" if i%2==0 else "⚪", "zone_123")
                rk = table.add_row(*row); self.all_rows.append(row)
                self.item_map[str(rk)] = {"type": "dns", "id": f"rec_{i}", "zone": "zone_123", "proxied": i%2==0, "record_type": "A", "name": f"site-{i}.com", "content": f"1.1.1.{i}"}
        self.write_log(f"[bold orange]✔ (MOCK) Loaded {self.current_view[4:]} data.[/]")

    @on(DataTable.RowSelected)
    @work(exclusive=True)
    async def handle_drilldown(self, event):
        table = self.query_one(DataTable)
        data = self.item_map.get(str(event.row_key))
        if not data: return

        if data["type"] == "kv_ns":
            self.is_drilled_down = True
            table.clear(columns=True)
            self.all_rows = []; self.item_map.clear()
            table.add_columns("Key Name", "Expiration")
            if self.is_mock_mode:
                for i in range(5):
                    row = (f"user_session_{i*100}", "Never")
                    rk = table.add_row(*row); self.all_rows.append(row)
                    self.item_map[str(rk)] = {"type": "kv_key", "name": row[0]}
            else:
                acc = await self.get_acc()
                try:
                    async for k in self.client.kv.namespaces.keys.list(account_id=acc, namespace_id=data["id"]):
                        row = (k.name, "None"); rk = table.add_row(*row); self.all_rows.append(row)
                        self.item_map[str(rk)] = {"type": "kv_key", "name": k.name, "ns_id": data["id"]}
                except Exception as e:
                    self.write_log(f"[red]✖ API Error: {str(e)}[/]")

        elif data["type"] == "kv_key":
            val = "{ 'id': 123 }" if self.is_mock_mode else "Real Value..."
            self.push_screen(InfoModal(f"Value: {data['name']}", val))

    @work(exclusive=True)
    async def action_toggle_proxy(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        data = self.item_map.get(str(list(table.rows.keys())[table.cursor_row]))
        if not data or data.get("type") != "dns": return

        if self.is_mock_mode:
            self.write_log(f"[bold orange]✔ (MOCK) Toggled proxy for {data['name']}[/]")
            return

        try:
            self.write_log(f"Toggling proxy for {data['name']}...")
            await self.client.dns.records.edit(
                zone_id=data["zone"],
                dns_record_id=data["id"],
                proxied=not data["proxied"],
                type=data["record_type"],
                name=data["name"],
                content=data["content"]
            )
            self.write_log(f"[green]✔ Proxy toggled for {data['name']}[/]")
            self.reload_current_view()
        except Exception as e:
            self.write_log(f"[red]✖ Toggle failed: {str(e)}[/]")

    @work(exclusive=True)
    async def action_delete_item(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        data = self.item_map.get(str(list(table.rows.keys())[table.cursor_row]))
        if not data: return

        if await self.push_screen_wait(ConfirmModal(f"DELETE {data.get('type')}?")):
            if self.is_mock_mode:
                table.remove_row(list(table.rows.keys())[table.cursor_row])
                self.write_log("[green]✔ (MOCK) Item deleted.[/]")
                return

            try:
                if data["type"] == "dns":
                    await self.client.dns.records.delete(dns_record_id=data["id"], zone_id=data["zone"])
                elif data["type"] == "kv_ns":
                    acc = await self.get_acc()
                    await self.client.kv.namespaces.delete(namespace_id=data["id"], account_id=acc)
                
                table.remove_row(list(table.rows.keys())[table.cursor_row])
                self.write_log("[green]✔ Item deleted via API.[/]")
            except Exception as e:
                self.write_log(f"[red]✖ Delete failed: {str(e)}[/]")

    @work(exclusive=True)
    async def action_purge_cache(self):
        if self.current_view != "nav-dns": return
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        data = self.item_map.get(str(list(table.rows.keys())[table.cursor_row]))
        if not data or "zone" not in data: return

        if await self.push_screen_wait(ConfirmModal("Purge Everything for this zone?")):
            if self.is_mock_mode:
                self.write_log("[green]✔ (MOCK) Cache Purged![/]")
                return
            try:
                await self.client.cache.purge(zone_id=data["zone"], purge_everything=True)
                self.write_log("[green]✔ Cache Purged via API![/]")
            except Exception as e:
                self.write_log(f"[red]✖ Purge failed: {str(e)}[/]")

    def action_go_back(self):
        self.query_one("#filter").value = ""
        if self.is_drilled_down: self.reload_current_view()

    def action_drill_down(self):
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            table.action_select_cursor()

    def action_copy_item(self):
        table = self.query_one(DataTable)
        if table.cursor_row is None: return
        data = self.item_map.get(str(list(table.rows.keys())[table.cursor_row]))
        if not data: return
        
        copy_text = str(data.get("name", data.get("id", "Unknown")))
        try:
            pyperclip.copy(copy_text)
            self.write_log(f"[green]✔ Copied to clipboard: {copy_text}[/]")
        except Exception as e:
            self.write_log(f"[red]✖ Copy failed: {str(e)}[/]")

def main(): LazyCloudflare().run()
if __name__ == "__main__": main()
