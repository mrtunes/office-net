# CLAUDE.md

## Project Overview

Office Network Tool — a portable Python CLI for scanning a small office LAN and connecting to machines. Targets 3-4 Windows PCs in a small office. Designed to be zero-config (auto-detects subnet from `ipconfig`) and portable (copy folder + `pip install`).

## Architecture

- **Single Python package** (`office_net/`) with a `__main__.py` entry point
- **Two modes**: Interactive menu (no args) and direct CLI commands (via `typer`)
- **No external network tools** — uses Windows `ping`, `arp -a`, and `socket.gethostbyaddr()`
- **SQLite** for scan history, **YAML** for config
- All network scanning uses `concurrent.futures.ThreadPoolExecutor` for parallelism

## Key Files

- `office_net/interactive.py` — Main user-facing menu interface
- `office_net/cli.py` — Typer CLI commands (used when args are passed)
- `office_net/scanner.py` — Ping sweep, ARP table parsing, hostname resolution
- `office_net/config.py` — YAML config loading + `ipconfig` auto-detection
- `office_net/db.py` — SQLite snapshot storage and diff logic
- `office_net/connect.py` — RDP launch, shared folder opener, ping, Wake-on-LAN

## Conventions

- Windows-specific: uses `ping -n`, `arp -a`, `mstsc`, `explorer`, `ipconfig`, `subprocess.CREATE_NO_WINDOW`
- Config auto-detection: if `subnet` is not in `config.yaml`, it's read from `ipconfig` output
- Machine resolution: all commands accept either a friendly name (from config) or a raw IP
- Interactive menus show hosts from the last scan, not just manually configured machines
- The `run.bat` launcher is meant for double-click on Windows desktops

## Running

```
python -m office_net          # Interactive menu
python -m office_net scan     # Direct CLI
```

## Dependencies

Only three: `typer`, `rich`, `pyyaml`. Listed in `requirements.txt`.
