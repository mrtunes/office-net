# Office Network Tool

A portable Python CLI tool for small office LANs. Scan and snapshot what devices are on the network, then quickly connect to them (RDP, shared folders, ping, Wake-on-LAN).

Designed to be copied to any Windows machine in the office via USB or shared folder — no installation beyond `pip install -r requirements.txt`.

## Quick Start

```
pip install -r requirements.txt
python -m office_net
```

Or double-click `run.bat`.

The tool auto-detects your IP and subnet from `ipconfig` — no config editing needed to get started.

## Interactive Mode

Run with no arguments to get a menu:

```
+--- Office Network Tool ---+
|  This PC:  10.0.0.20      |
|  Subnet:  10.0.0.0/24     |
+----------------------------+

  1  Scan the network
  2  Scan + show changes
  3  View last scan results
  4  Connect to a machine (RDP / shared folder)
  5  Ping
  6  Wake-on-LAN
  7  Settings (known machines)
  8  Exit
```

## CLI Commands

Direct commands also work for scripting or quick one-offs:

```
office-net scan              # Scan the LAN, show results, save snapshot
office-net scan --diff       # Scan and show what changed since last snapshot
office-net list              # Show last scan results (no new scan)
office-net history           # Show IP assignment history for all devices
office-net rdp <name-or-ip>  # Launch RDP to a machine
office-net share <name-or-ip> [path]  # Open shared folder in Explorer
office-net ping <name-or-ip> # Quick ping check
office-net ping all          # Ping all known machines, show status table
office-net wake <name-or-ip> # Send Wake-on-LAN magic packet
office-net config            # Show current config
office-net config add <name> <ip>     # Nickname a machine
office-net config remove <name>       # Remove a nickname
```

## How It Works

- **Scanning**: Parallel ping sweep (`ping -n 1 -w 500` via `concurrent.futures`), then parses the Windows ARP table (`arp -a`) for MAC addresses, and `socket.gethostbyaddr()` for hostnames. No nmap required.
- **Storage**: SQLite database stores scan snapshots over time. Can live on a shared network folder so all machines see the same history.
- **Config**: `config.yaml` for subnet override, machine nicknames, DB path. Subnet is auto-detected if not set.
- **Connect**: Launches `mstsc` for RDP, `explorer` for shared folders. Wake-on-LAN sends UDP magic packets.

## Project Structure

```
office-net/
  config.yaml           # Subnet, known machines, DB path
  requirements.txt      # typer, rich, pyyaml
  run.bat               # Double-click launcher
  office_net/
    __init__.py
    __main__.py          # Entry point routing (interactive vs CLI)
    cli.py               # Typer CLI commands
    interactive.py       # Interactive menu interface
    config.py            # YAML config + subnet auto-detection
    scanner.py           # Ping sweep, ARP parsing, hostname resolution
    connect.py           # RDP, shared folders, ping, Wake-on-LAN
    db.py                # SQLite snapshot storage + diff logic
```

## Dependencies

- `typer` — CLI framework
- `rich` — Pretty tables and colored terminal output
- `pyyaml` — Config file parsing

No external network tools required. Uses only Windows built-in `ping` and `arp` commands.

## Shared Setup

To share across office machines:

1. Copy the `office-net` folder to a shared drive or USB
2. Run `pip install -r requirements.txt` on each machine
3. Optionally set `db_path` in `config.yaml` to a UNC path (e.g. `\\server\shared\office-net.db`) so all machines share scan history

## Future Ideas

- **`tracert <machine>`** — Trace the route to a machine when something's flaky. Wraps Windows `tracert`.
- **`open <name-or-ip>`** — Open a machine's web admin page in the browser (`http://<ip>`). Useful for routers, printers, NAS.
- **`export`** — Dump last scan or full history to CSV for documentation.
- **`label/note <name> <text>`** — Attach free-text notes to machines ("printer in hallway", "do not restart"). Display in scan results.
- **`status` (dashboard)** — One-shot overview: ping all known machines, show up/down with last-seen time from history. Quick "is everything alive" check.
- **`ports <name-or-ip>`** — Quick port check on common ports (RDP 3389, SMB 445, HTTP 80/443, printer 9100/631). Answers "is file sharing on?" or "is that a printer?" without nmap.
- **Backup monitoring** — Deferred to a later phase.
