"""Interactive menu interface - launches when you run with no arguments."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from office_net import config, connect, db, scanner

console = Console()


def _clear() -> None:
    """Print some blank lines to visually separate screens."""
    console.print()


def _prompt(label: str = ">") -> str:
    """Read input, handling Ctrl+C / EOF gracefully."""
    try:
        return input(f"{label} ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\nBye!")
        sys.exit(0)


def _pick(options: list[tuple[str, str]], title: str = "Choose an option") -> str | None:
    """Show a numbered menu from a list of (key, label) tuples.

    Returns the key of the chosen option, or None for back/invalid.
    """
    console.print(f"\n[bold]{title}[/bold]\n")
    for i, (key, label) in enumerate(options, 1):
        console.print(f"  [bold cyan]{i}[/bold cyan]  {label}")
    console.print(f"  [dim]0  Back[/dim]")
    console.print()

    choice = _prompt()
    if choice == "0" or choice == "":
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    except ValueError:
        # Maybe they typed the key directly
        for key, _ in options:
            if choice.lower() == key.lower():
                return key
    console.print("[red]Invalid choice.[/red]")
    return None


def _pick_machine(cfg: dict) -> str | None:
    """Let the user pick from scanned/known machines or type an IP. Returns IP or None."""
    nicknames = cfg.get("machines") or {}
    # Reverse lookup: ip -> nickname
    names_by_ip = {ip: name for name, ip in nicknames.items()}
    local_ip = config.detect_local_ip()

    # Build list from last scan + any known machines not in the scan
    dbp = config.db_path(cfg)
    last = db.get_latest_scan(dbp)
    seen_ips: set[str] = set()
    options: list[tuple[str, str]] = []

    if last:
        _, hosts = last
        for h in hosts:
            # Skip this PC
            if h.ip == local_ip:
                continue
            seen_ips.add(h.ip)
            nick = names_by_ip.get(h.ip)
            parts = []
            if nick:
                parts.append(f"[bold cyan]{nick}[/bold cyan]")
            parts.append(f"[green]{h.ip}[/green]")
            if h.hostname:
                parts.append(f"({h.hostname})")
            options.append((h.ip, "  ".join(parts)))

    # Add any nicknamed machines that weren't in the scan
    for name, ip in nicknames.items():
        if ip not in seen_ips and ip != local_ip:
            options.append((ip, f"[bold cyan]{name}[/bold cyan]  [green]{ip}[/green]  [dim](not in last scan)[/dim]"))

    if not options:
        console.print("\n[yellow]No machines found. Run a scan first.[/yellow]")
        _prompt("\nPress Enter to continue")
        return None

    options.append(("_manual", "Enter an IP address"))

    choice = _pick(options, title="Which machine?")
    if choice is None:
        return None
    if choice == "_manual":
        console.print("\nEnter IP address:")
        ip = _prompt()
        return ip if ip else None
    return choice


def _host_table(hosts: list[scanner.Host], cfg: dict, title: str = "Scan Results") -> Table:
    """Build a Rich table from a list of hosts."""
    names = {v: k for k, v in (cfg.get("machines") or {}).items()}
    local_ip = config.detect_local_ip()

    table = Table(title=title, show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="bold cyan", min_width=12)
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Hostname")

    for i, h in enumerate(hosts, 1):
        name = names.get(h.ip, "")
        if h.ip == local_ip:
            name = name or "(this PC)"
        table.add_row(str(i), name, h.ip, h.mac or "-", h.hostname or "-")
    return table


# ---------------------------------------------------------------------------
# Menu actions
# ---------------------------------------------------------------------------

def _do_scan(cfg: dict) -> None:
    subnet = cfg["subnet"]
    dbp = config.db_path(cfg)
    console.print(f"\nScanning [bold]{subnet}.0/24[/bold] ...")
    hosts = scanner.scan(subnet)
    console.print(f"Found [bold green]{len(hosts)}[/bold green] hosts.\n")
    db.save_scan(dbp, hosts)
    console.print(_host_table(hosts, cfg))
    _prompt("\nPress Enter to continue")


def _do_scan_diff(cfg: dict) -> None:
    subnet = cfg["subnet"]
    dbp = config.db_path(cfg)
    old_result = db.get_latest_scan(dbp)

    console.print(f"\nScanning [bold]{subnet}.0/24[/bold] ...")
    hosts = scanner.scan(subnet)
    console.print(f"Found [bold green]{len(hosts)}[/bold green] hosts.\n")
    db.save_scan(dbp, hosts)
    console.print(_host_table(hosts, cfg))

    if old_result:
        changes = db.diff_scans(old_result[1], hosts)
        if not any(changes.values()):
            console.print("\n[dim]No changes since last scan.[/dim]")
        else:
            console.print()
            if changes["added"]:
                console.print("[bold green]+ New hosts:[/bold green]")
                for h in changes["added"]:
                    console.print(f"  {h.ip}  {h.mac or ''}  {h.hostname or ''}")
            if changes["removed"]:
                console.print("[bold red]- Gone:[/bold red]")
                for h in changes["removed"]:
                    console.print(f"  {h.ip}  {h.mac or ''}  {h.hostname or ''}")
            if changes["changed"]:
                console.print("[bold yellow]~ Changed:[/bold yellow]")
                for old, new in changes["changed"]:
                    console.print(f"  {new.ip}: MAC {old.mac}->{new.mac}, host {old.hostname}->{new.hostname}")
    else:
        console.print("\n[dim]No previous scan to compare against.[/dim]")
    _prompt("\nPress Enter to continue")


def _do_list(cfg: dict) -> None:
    dbp = config.db_path(cfg)
    result = db.get_latest_scan(dbp)
    if result is None:
        console.print("\n[yellow]No scans yet. Run a scan first.[/yellow]")
    else:
        ts, hosts = result
        console.print(f"\nLast scan: [dim]{ts}[/dim]\n")
        console.print(_host_table(hosts, cfg, title="Last Scan"))
    _prompt("\nPress Enter to continue")


def _do_connect(cfg: dict) -> None:
    ip = _pick_machine(cfg)
    if ip is None:
        return

    action = _pick([
        ("rdp", "Remote Desktop (RDP)"),
        ("share", "Open shared folder"),
    ], title=f"Connect to {ip}")

    if action == "rdp":
        console.print(f"\nOpening RDP to [bold]{ip}[/bold] ...")
        connect.launch_rdp(ip)
    elif action == "share":
        console.print("\nFolder path (leave blank for root share):")
        path = _prompt()
        console.print(f"Opening [bold]\\\\{ip}\\{path}[/bold] ...")
        connect.open_share(ip, path)


def _do_ping(cfg: dict) -> None:
    nicknames = cfg.get("machines") or {}
    names_by_ip = {ip: name for name, ip in nicknames.items()}
    local_ip = config.detect_local_ip()
    dbp = config.db_path(cfg)
    last = db.get_latest_scan(dbp)

    options: list[tuple[str, str]] = [("all", "Ping all from last scan")]
    seen_ips: set[str] = set()

    if last:
        for h in last[1]:
            if h.ip == local_ip:
                continue
            seen_ips.add(h.ip)
            nick = names_by_ip.get(h.ip)
            parts = []
            if nick:
                parts.append(f"[bold cyan]{nick}[/bold cyan]")
            parts.append(f"[green]{h.ip}[/green]")
            if h.hostname:
                parts.append(f"({h.hostname})")
            options.append((h.ip, "  ".join(parts)))

    for name, ip in nicknames.items():
        if ip not in seen_ips and ip != local_ip:
            options.append((ip, f"[bold cyan]{name}[/bold cyan]  [green]{ip}[/green]  [dim](not in last scan)[/dim]"))

    options.append(("_manual", "Enter an IP address"))

    choice = _pick(options, title="Ping")
    if choice is None:
        return

    if choice == "_manual":
        console.print("\nEnter IP address:")
        choice = _prompt()
        if not choice:
            return

    if choice == "all":
        if not last:
            console.print("\n[yellow]No scan data yet. Run a scan first.[/yellow]")
            _prompt("\nPress Enter to continue")
            return
        table = Table(title="Ping All Hosts")
        table.add_column("Name", style="bold cyan")
        table.add_column("IP", style="green")
        table.add_column("Hostname")
        table.add_column("Status")
        for h in last[1]:
            if h.ip == local_ip:
                continue
            nick = names_by_ip.get(h.ip, "")
            alive = scanner.ping(h.ip)
            status = "[bold green]UP[/bold green]" if alive else "[bold red]DOWN[/bold red]"
            table.add_row(nick, h.ip, h.hostname or "-", status)
        console.print()
        console.print(table)
    else:
        console.print(f"\nPinging [bold]{choice}[/bold] ...\n")
        output = connect.ping_host(choice)
        console.print(output)
    _prompt("\nPress Enter to continue")


def _do_wake(cfg: dict) -> None:
    dbp = config.db_path(cfg)
    nicknames = cfg.get("machines") or {}
    names_by_ip = {ip: name for name, ip in nicknames.items()}
    local_ip = config.detect_local_ip()

    options: list[tuple[str, str]] = []
    last_scan = db.get_latest_scan(dbp)
    hosts_by_ip = {}

    if last_scan:
        hosts_by_ip = {h.ip: h for h in last_scan[1]}
        seen_ips: set[str] = set()
        for h in last_scan[1]:
            if h.ip == local_ip:
                continue
            seen_ips.add(h.ip)
            nick = names_by_ip.get(h.ip)
            parts = []
            if nick:
                parts.append(f"[bold cyan]{nick}[/bold cyan]")
            parts.append(f"[green]{h.ip}[/green]")
            if h.hostname:
                parts.append(f"({h.hostname})")
            if h.mac:
                parts.append(f"MAC: {h.mac}")
            else:
                parts.append("[dim]no MAC[/dim]")
            options.append((h.ip, "  ".join(parts)))

        for name, ip in nicknames.items():
            if ip not in seen_ips and ip != local_ip:
                options.append((ip, f"[bold cyan]{name}[/bold cyan]  [green]{ip}[/green]  [dim](not in last scan)[/dim]"))

    options.append(("_manual", "Enter a MAC address"))

    choice = _pick(options, title="Wake-on-LAN")
    if choice is None:
        return

    if choice == "_manual":
        console.print("\nEnter MAC address (e.g. aa-bb-cc-dd-ee-ff):")
        mac = _prompt()
        if not mac:
            return
    else:
        host = hosts_by_ip.get(choice)
        if not host or not host.mac:
            console.print(f"\n[red]No MAC address known for {choice}. Run a scan first.[/red]")
            _prompt("\nPress Enter to continue")
            return
        mac = host.mac

    connect.send_wol(mac)
    console.print(f"\n[green]Wake-on-LAN packet sent to {mac}[/green]")
    _prompt("\nPress Enter to continue")


def _do_settings(cfg: dict) -> None:
    while True:
        machines = cfg.get("machines") or {}

        console.print(f"\n[bold]This PC:[/bold]  {config.detect_local_ip() or 'unknown'}")
        console.print(f"[bold]Subnet:[/bold]  {cfg['subnet']}.0/24")
        console.print(f"[bold]DB path:[/bold] {config.db_path(cfg)}")

        if machines:
            console.print(f"\n[bold]Known machines ({len(machines)}):[/bold]")
            for name, ip in machines.items():
                console.print(f"  [cyan]{name}[/cyan] -> [green]{ip}[/green]")

        action = _pick([
            ("add", "Add / rename a machine"),
            ("remove", "Remove a machine"),
        ], title="Settings")

        if action is None:
            return

        if action == "add":
            console.print("\nFriendly name (e.g. dad-pc, front-desk):")
            name = _prompt()
            if not name:
                continue
            console.print("IP address:")
            ip = _prompt()
            if not ip:
                continue
            if cfg["machines"] is None:
                cfg["machines"] = {}
            cfg["machines"][name] = ip
            config.save(cfg)
            console.print(f"[green]Saved:[/green] {name} -> {ip}")

        elif action == "remove":
            if not machines:
                console.print("\n[yellow]No machines to remove.[/yellow]")
                continue
            options = [(n, f"{n} ({ip})") for n, ip in machines.items()]
            name = _pick(options, title="Remove which machine?")
            if name and name in cfg["machines"]:
                del cfg["machines"][name]
                config.save(cfg)
                console.print(f"[green]Removed:[/green] {name}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def _banner(cfg: dict) -> None:
    local_ip = config.detect_local_ip()
    subnet = cfg["subnet"]
    machines = cfg.get("machines") or {}

    lines = [
        f"[bold]This PC:[/bold]  {local_ip or 'unknown'}",
        f"[bold]Subnet:[/bold]  {subnet}.0/24",
    ]
    if machines:
        lines.append(f"[bold]Machines:[/bold] {', '.join(machines.keys())}")

    console.print(Panel(
        "\n".join(lines),
        title="[bold]Office Network Tool[/bold]",
        border_style="blue",
        padding=(1, 2),
    ))


MAIN_MENU = [
    ("scan", "Scan the network"),
    ("diff", "Scan + show changes"),
    ("list", "View last scan results"),
    ("connect", "Connect to a machine (RDP / shared folder)"),
    ("ping", "Ping"),
    ("wake", "Wake-on-LAN"),
    ("settings", "Settings (known machines)"),
    ("quit", "Exit"),
]


def run() -> None:
    """Main interactive loop."""
    cfg = config.load()
    _banner(cfg)

    while True:
        choice = _pick(MAIN_MENU, title="What would you like to do?")

        if choice is None or choice == "quit":
            console.print("\nBye!")
            break

        # Reload config each time in case settings changed
        cfg = config.load()

        if choice == "scan":
            _do_scan(cfg)
        elif choice == "diff":
            _do_scan_diff(cfg)
        elif choice == "list":
            _do_list(cfg)
        elif choice == "connect":
            _do_connect(cfg)
        elif choice == "ping":
            _do_ping(cfg)
        elif choice == "wake":
            _do_wake(cfg)
        elif choice == "settings":
            _do_settings(cfg)
