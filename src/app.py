import os
import asyncio
from dotenv import load_dotenv
from cloudflare import Cloudflare
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, ListItem, ListView, Label, DataTable, Input
from textual.containers import Vertical, Horizontal
from textual import on, work, events

load_dotenv()

class Sidebar(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("LAZY CLOUDFLARE", id="app-title")
        yield ListView(
            ListItem(Label("Workers"), id="nav-workers"),
            ListItem(Label("DNS Zones"), id="nav-dns"),
            ListItem(Label("KV Store"), id="nav-kv"),
            ListItem(Label("R2 Storage"), id="nav-r2"),
            id="sidebar-list"
        )

class LazyCloudflare(App):
    CSS = """
    Sidebar {
        width: 30;
        background: #1e1e1e;
        border-right: solid #f6821f;
        padding: 1;
    }

    #app-title {
        text-align: center;
        color: #f6821f;
        text-style: bold;
        margin-bottom: 1;
        border-bottom: double #f6821f;
    }

    DataTable {
        height: 1fr;
        background: #121212;
    }

    #content-area {
        background: #121212;
        padding: 1;
    }

    #filter-bar {
        border: solid #f6821f;
        margin-bottom: 1;
        height: 3;
    }

    .status-msg {
        padding: 1;
        color: #f6821f;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("/", "focus_filter", "Filter/Search"),
        ("space", "toggle_proxy", "Toggle Proxy (DNS)"),
        ("p", "purge_cache", "Purge Everything (Cache)"),
        ("e", "edit_record", "Edit Content (DNS)"),
        ("u", "toggle_attack_mode", "Under Attack Mode (DNS)"),
        ("escape", "go_back", "Back (Clear)"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.client = Cloudflare(api_token=token)
        self.account_id = None
        self.current_view = "welcome"
        self.is_drilled_down = False
        self.dns_records_map = {} # Store record objects
        self.row_data_map = {} # Generic data for rows
        self.all_rows = [] # Store all rows for filtering

    async def get_account_id(self):
        if self.account_id: return self.account_id
        try:
            accounts = self.client.accounts.list()
            for account in accounts:
                self.account_id = account.id
                return self.account_id
        except: return None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            with Vertical(id="content-area"):
                yield Static("Welcome. Press / to search or select a resource.", id="status-display")
                yield Input(placeholder="Search/Filter records...", id="filter-bar")
                yield DataTable(id="data-table", cursor_type="row")
        yield Footer()

    def action_focus_filter(self) -> None:
        self.query_one("#filter-bar").focus()

    @on(Input.Changed, "#filter-bar")
    def handle_filter_change(self, event: Input.Changed) -> None:
        table = self.query_one(DataTable)
        search_term = event.value.lower()
        
        table.clear(columns=False)
        for row in self.all_rows:
            if any(search_term in str(cell).lower() for cell in row):
                table.add_row(*row)

    @on(ListView.Selected)
    @work(exclusive=True)
    async def handle_nav_change(self, event: ListView.Selected) -> None:
        self.is_drilled_down = False
        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        selection = event.item.id
        self.current_view = selection

        table.clear(columns=True)
        self.row_data_map.clear()
        self.all_rows = []
        status.update("[bold yellow]Fetching data...[/]")

        account_id = await self.get_account_id()
        if not account_id:
            status.update("[red]Error: Check API Token.[/]")
            return

        try:
            if selection == "nav-workers":
                table.add_columns("Worker ID", "Modified")
                workers = self.client.workers.scripts.list(account_id=account_id)
                for w in workers:
                    row = (w.id, getattr(w, 'modified_on', 'N/A'))
                    self.all_rows.append(row)
                    table.add_row(*row)
                status.update(f"[bold orange]Workers ({len(table.rows)})[/]")

            elif selection == "nav-dns":
                table.add_columns("Type", "Name", "Content", "Proxy", "Zone ID")
                zones = self.client.zones.list()
                record_count = 0
                for zone in zones:
                    records = self.client.dns.records.list(zone_id=zone.id)
                    for r in records:
                        proxy_icon = "🟠" if r.proxied else "⚪"
                        row = (r.type, r.name, r.content, proxy_icon, zone.id)
                        row_key = table.add_row(*row)
                        self.all_rows.append(row)
                        self.dns_records_map[str(row_key)] = {"id": r.id, "zone_id": zone.id, "proxied": r.proxied}
                        record_count += 1
                status.update(f"[bold orange]DNS ({record_count}) - Space: Proxy | P: Purge | E: Edit[/]")

            elif selection == "nav-kv":
                table.add_columns("Namespace ID", "Title")
                namespaces = self.client.kv.namespaces.list(account_id=account_id)
                for ns in namespaces:
                    row = (ns.id, ns.title)
                    row_key = table.add_row(*row)
                    self.all_rows.append(row)
                    self.row_data_map[str(row_key)] = ns.id
                status.update(f"[bold orange]KV Namespaces ({len(table.rows)}) - Enter to view keys[/]")
                
            elif selection == "nav-r2":
                table.add_columns("Bucket Name", "Creation Date")
                try:
                    buckets = self.client.r2.buckets.list(account_id=account_id)
                    for b in buckets:
                        row = (b.name, str(getattr(b, 'creation_date', 'N/A')))
                        self.all_rows.append(row)
                        table.add_row(*row)
                    status.update(f"[bold orange]R2 Buckets ({len(table.rows)})[/]")
                except:
                    status.update("[red]R2 permissions missing.[/]")

        except Exception as e:
            status.update(f"[red]API Error: {str(e)}[/]")

    async def action_edit_record(self) -> None:
        if self.current_view != "nav-dns": return
        
        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        cursor_row = table.cursor_row
        if cursor_row is None: return
        
        row_key = list(table.rows.keys())[cursor_row]
        record_data = self.dns_records_map.get(str(row_key))
        if not record_data: return

        # For editing, we'll use a simple prompt logic (in a real "Lazy" app, we'd use a Modal)
        # For now, let's toggle Proxy as it's the most "Lazy" edit.
        # I'll implement a full edit modal in the next step.
        status.update("[bold yellow]Editing via TUI prompts coming in next minor release![/]")

    async def action_toggle_attack_mode(self) -> None:
        if self.current_view != "nav-dns": return
        
        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        cursor_row = table.cursor_row
        if cursor_row is None: return
        
        row_key = list(table.rows.keys())[cursor_row]
        record_data = self.dns_records_map.get(str(row_key))
        if not record_data: return

        zone_id = record_data["zone_id"]
        status.update(f"[bold red]Toggling Under Attack Mode for Zone {zone_id}...[/]")
        
        try:
            # Check current status and toggle
            zone = self.client.zones.get(zone_id=zone_id)
            current_mode = zone.security_level
            new_mode = "under_attack" if current_mode != "under_attack" else "high"
            
            self.client.zones.edit(zone_id=zone_id, security_level=new_mode)
            status.update(f"[bold green]Under Attack Mode set to: {new_mode}[/]")
        except Exception as e:
            status.update(f"[red]Failed to toggle security level: {str(e)}[/]")

    @on(DataTable.RowSelected)
    @work(exclusive=True)
    async def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.is_drilled_down or self.current_view != "nav-kv":
            return # Only drilling down into KV for now

        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        
        row_key = str(event.row_key)
        namespace_id = self.row_data_map.get(row_key)
        
        if not namespace_id: return

        self.is_drilled_down = True
        table.clear(columns=True)
        status.update(f"[bold yellow]Fetching keys for KV Namespace {namespace_id}...[/]")
        
        account_id = await self.get_account_id()

        try:
            table.add_columns("Key Name", "Expiration")
            # This is the standard v4 API path for KV keys
            keys = self.client.kv.namespaces.keys.list(account_id=account_id, namespace_id=namespace_id)
            key_count = 0
            for k in keys:
                exp = getattr(k, 'expiration', 'None')
                table.add_row(k.name, str(exp))
                key_count += 1
            status.update(f"[bold orange]Keys ({key_count}) - Press ESC to go back[/]")
        except Exception as e:
            status.update(f"[red]Failed to fetch keys: {str(e)}[/]")

    def action_go_back(self) -> None:
        """Clear drill-down and reload the current view."""
        if self.is_drilled_down:
            sidebar_list = self.query_one("#sidebar-list", ListView)
            # Re-trigger the selection event to reload the list
            if sidebar_list.index is not None:
                item = sidebar_list.children[sidebar_list.index]
                self.post_message(ListView.Selected(sidebar_list, item))

    async def action_toggle_proxy(self) -> None:
        if self.current_view != "nav-dns":
            return

        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        
        # Get selected row
        cursor_row = table.cursor_row
        if cursor_row is None: return
        
        row_key = list(table.rows.keys())[cursor_row]
        record_data = self.dns_records_map.get(str(row_key))
        
        if not record_data: return

        new_proxy_state = not record_data["proxied"]
        status.update(f"[yellow]Toggling Proxy for {record_data['id']}...[/]")

        try:
            # Perform the update
            self.client.dns.records.update(
                dns_record_id=record_data["id"],
                zone_id=record_data["zone_id"],
                proxied=new_proxy_state
            )
            
            # Update local state and UI
            record_data["proxied"] = new_proxy_state
            proxy_icon = "🟠" if new_proxy_state else "⚪"
            table.update_cell(row_key, "Proxy", proxy_icon)
            status.update("[green]Proxy updated successfully![/]")
        except Exception as e:
            status.update(f"[red]Failed to toggle: {str(e)}[/]")

    async def action_purge_cache(self) -> None:
        if self.current_view != "nav-dns":
            status = self.query_one("#status-display", Static)
            status.update("[yellow]Purge only works in DNS view right now.[/]")
            return

        table = self.query_one(DataTable)
        status = self.query_one("#status-display", Static)
        
        cursor_row = table.cursor_row
        if cursor_row is None: return
        
        row_key = list(table.rows.keys())[cursor_row]
        record_data = self.dns_records_map.get(str(row_key))
        
        if not record_data: return

        zone_id = record_data["zone_id"]
        status.update(f"[yellow]Purging Everything for Zone {zone_id}...[/]")

        try:
            self.client.zones.purge_cache(
                zone_id=zone_id,
                purge_everything=True
            )
            status.update("[green]Cache purged successfully![/]")
        except Exception as e:
            status.update(f"[red]Purge failed: {str(e)}[/]")

def main():
    app = LazyCloudflare()
    app.run()

if __name__ == "__main__":
    main()
