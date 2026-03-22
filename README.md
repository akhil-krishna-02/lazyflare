# 🟠 LazyCloudflare

A fast, keyboard-driven Terminal User Interface (TUI) for managing your Cloudflare stack. Built for developers who are tired of slow web dashboards.

Manage DNS, Workers, KV Storage, and R2 directly from your terminal.

![LazyCloudflare Demo](https://via.placeholder.com/800x400.png?text=LazyCloudflare+Terminal+UI)

## Why use LazyCloudflare?

The Cloudflare dashboard is powerful but can be slow for rapid tasks. `lazycloudflare` gives you Vim-style keybindings to perform complex actions instantly.

- **Speed:** Filter hundreds of DNS records or KV keys instantly as you type (`/`).
- **One-Key Actions:** Toggle Proxy (`Space`), Purge Cache (`p`), or enable Under Attack Mode (`u`) without loading a single webpage.
- **Unified View:** See your Workers, DNS, R2, and KV all in one place.

## Installation

### Method 1: Using pip (Recommended)
You can install `lazycloudflare` globally using pip:

```bash
pip install lazycloudflare
```

### Method 2: From Source
```bash
git clone https://github.com/yourusername/lazycloudflare.git
cd lazycloudflare
pip install -r requirements.txt
python src/app.py
```

## Setup

You need a Cloudflare API Token to use this tool.
1. Go to the [Cloudflare API Tokens page](https://dash.cloudflare.com/profile/api-tokens).
2. Create a Custom Token with the following **Edit** permissions:
   - `Workers Scripts`, `Workers KV Storage`, `Workers R2 Storage`, `Zone DNS`, `Zone Settings`.
3. Set the token in your environment:

```bash
export CLOUDFLARE_API_TOKEN="your_token_here"
```
*(You can also place this in a `.env` file in the directory where you run the tool).*

## Usage

Simply run:
```bash
lazycloudflare
```

### Global Keybindings
- `q` : Quit
- `r` : Refresh Data
- `/` : Search / Filter current view
- `Esc` : Go Back / Clear Search

### DNS Keybindings
- `Space` : Toggle Proxy (Orange Cloud / White Cloud)
- `p` : Purge Everything (Cache) for the selected Zone
- `u` : Toggle "Under Attack" Mode

### KV Keybindings
- `Enter` : Drill down into a Namespace to view its Keys.

## Built With
- [Textual](https://textual.textualize.io/) - The incredible Python TUI framework.
- [Cloudflare Python SDK](https://github.com/cloudflare/cloudflare-python)

## License
MIT
