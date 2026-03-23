# 🟠 LazyFlare

A terminal UI for managing Cloudflare resources, inspired by lazygit and LazyFire.

[![PyPI version](https://badge.fury.io/py/lazyflare.svg)](https://badge.fury.io/py/lazyflare)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features
- **Browse Cloudflare Resources:** Navigate Workers, DNS Zones, KV Namespaces, D1 Databases, and Pages seamlessly.
- **Fast Navigation:** Expandable tree view for nested data (like KV keys inside a namespace).
- **Real-time DNS Management:** Instantly toggle proxy status (🟠/⚪) on DNS records with a single keystroke.
- **Cache Purging:** One-key execution to purge the entire edge cache for a selected Zone.
- **Filter/Search:** Instantly filter across all panels to find specific records or workers.
- **Vim-style keybindings:** Navigate with familiar `h/j/k/l` bindings.
- **Copy Support:** Quickly copy record IDs, IP addresses, or JSON values directly to your system clipboard.
- **Customizable Layout:** Uses the Textual framework to dynamically expand focused panels in a sleek dark theme.

## Installation

### Python (pipx) - *Recommended*
```bash
pipx install lazyflare
```

### Homebrew (macOS/Linux)
```bash
brew tap akhil-krishna-02/tap
brew install lazyflare
```

### From Source
```bash
git clone https://github.com/akhil-krishna-02/lazyflare.git
cd lazyflare
pip install -e .
```

## Quick Start

You need a Cloudflare API Token to use this tool.
1. Go to the [Cloudflare API Tokens page](https://dash.cloudflare.com/profile/api-tokens).
2. Create a Custom Token with **Edit** permissions for `Zone DNS`, `Cache Purge`, `Workers Scripts`, etc.

Login by setting your environment variable or config file:
```bash
export CLOUDFLARE_API_TOKEN="your_token_here"
```

Run LazyFlare:
```bash
lazyflare
```

## Keybindings

| Key | Action |
|-----|--------|
| `h` / `←` | Go Back / Collapse |
| `l` / `→` | Drill Down / Expand |
| `j` / `↓` | Move down in list |
| `k` / `↑` | Move up in list |
| `Tab` | Switch focus between panels |
| `Enter` | Open resource / Fetch data |
| `Space` | Toggle DNS Proxy Status (Orange Cloud) |
| `p` | Purge Zone Cache |
| `d` | Delete Item (with confirmation) |
| `c` | Copy Item ID/Name to clipboard |
| `/` | Filter current panel |
| `Esc` | Back / Clear filter |
| `m` | Toggle Mock Mode (Offline testing) |
| `?` | Show Help menu |
| `q` | Quit |

## Configuration

LazyFlare natively supports configuration files for storing your token securely without cluttering your `.bashrc`.

Create `~/.config/lazyflare/config`:

```ini
CLOUDFLARE_API_TOKEN=your_super_secret_token_here
```

## Requirements
- Python 3.8+
- Terminal with true color support (recommended)
- A valid Cloudflare API Token

## Acknowledgments
- [lazygit](https://github.com/jesseduffield/lazygit) - For the original UI workflow inspiration.
- [LazyFire](https://github.com/marjoballabani/lazyfire) - For the visual styling, formatting, and structural inspiration.
- [Textual](https://github.com/Textualize/textual) - The incredible Python TUI framework powering the layout.

## License
MIT - see LICENSE
