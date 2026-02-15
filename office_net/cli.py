"""CLI entry point for office-net."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from office_net import config, connect, db, scanner

app = typer.Typer(
    name="office-net",
    help="Dad's Office Network Tool - scan the LAN and connect to machines.",
    add_completion=False,
)
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _host_table(hosts: list[scanner.Host], cfg: dict, title: str = "Scan Results") -> Table:
    """Build a Rich table from a list of hosts."""
    # Reverse lookup: ip -> name
    names = {v: k for k, v in (cfg.get("machines") or {}).items()}
    local_ip = config.detect_local_ip()

    table = Table(title=title, show_lines=False)
    table.add_column("Name", style="bold cyan", min_width=12)
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Hostname")

    for h in hosts:
        name = names.get(h.ip, "")
        if h.ip == local_ip:
            name = name or "(this PC)"
        table.add_row(name, h.ip, h.mac or "—", h.hostname or "—")
    return table


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

@app.command()
def scan(
    diff: bool = typer.Option(False, "--diff", help="Show changes since the last scan."),
) -> None:
    """Scan the LAN, display results, and save a snapshot."""
    cfg = config.load()
    subnet = cfg["subnet"]
    dbp = config.db_path(cfg)

    # If --diff, grab the current latest *before* we scan
    old_scan = None
    if diff:
        result = db.get_latest_scan(dbp)
        if result:
            old_scan = result[1]

    local_ip = config.detect_local_ip()
    console.print(f"This PC: [bold]{local_ip or 'unknown'}[/bold]")
    console.print(f"Scanning [bold]{subnet}.0/24[/bold] ...")
    hosts = scanner.scan(subnet)
    console.print(f"Found [bold green]{len(hosts)}[/bold green] hosts.\n")

    # Save
    db.save_scan(dbp, hosts)

    # Display
    console.print(_host_table(hosts, cfg))

    # Diff
    if diff and old_scan is not None:
        changes = db.diff_scans(old_scan, hosts)
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
    elif diff:
        console.print("\n[dim]No previous scan to compare against.[/dim]")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@app.command(name="list")
def list_cmd() -> None:
    """Show the most recent scan results (no new scan)."""
    cfg = config.load()
    dbp = config.db_path(cfg)
    result = db.get_latest_scan(dbp)
    if result is None:
        console.print("[yellow]No scans yet. Run:[/yellow] office-net scan")
        raise typer.Exit()
    ts, hosts = result
    console.print(f"Last scan: [dim]{ts}[/dim]\n")
    console.print(_host_table(hosts, cfg, title="Last Scan"))


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@app.command()
def history(
    ip: Optional[str] = typer.Argument(None, help="Filter to a specific IP."),
) -> None:
    """Show IP assignment history across scans."""
    cfg = config.load()
    dbp = config.db_path(cfg)
    resolved = config.resolve_name(ip, cfg) if ip else None
    rows = db.get_history(dbp, ip=resolved)
    if not rows:
        console.print("[yellow]No history found.[/yellow]")
        raise typer.Exit()

    table = Table(title="Scan History")
    table.add_column("Timestamp", style="dim")
    table.add_column("IP", style="green")
    table.add_column("MAC", style="yellow")
    table.add_column("Hostname")
    for r in rows:
        table.add_row(r["timestamp"], r["ip"], r["mac"] or "—", r["hostname"] or "—")
    console.print(table)


# ---------------------------------------------------------------------------
# rdp
# ---------------------------------------------------------------------------

@app.command()
def rdp(name_or_ip: str = typer.Argument(..., help="Machine name or IP.")) -> None:
    """Launch Remote Desktop to a machine."""
    cfg = config.load()
    ip = config.resolve_name(name_or_ip, cfg)
    console.print(f"Opening RDP to [bold]{ip}[/bold] ...")
    connect.launch_rdp(ip)


# ---------------------------------------------------------------------------
# share
# ---------------------------------------------------------------------------

@app.command()
def share(
    name_or_ip: str = typer.Argument(..., help="Machine name or IP."),
    path: str = typer.Argument("", help="Share/folder path (e.g. 'Users' or 'shared\\docs')."),
) -> None:
    """Open a shared folder on a machine in Explorer."""
    cfg = config.load()
    ip = config.resolve_name(name_or_ip, cfg)
    unc = f"\\\\{ip}\\{path}" if path else f"\\\\{ip}"
    console.print(f"Opening [bold]{unc}[/bold] ...", highlight=False)
    connect.open_share(ip, path)


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

@app.command(name="ping")
def ping_cmd(
    target: str = typer.Argument(..., help="Machine name, IP, or 'all'."),
) -> None:
    """Ping a machine (or 'all' known machines)."""
    cfg = config.load()

    if target.lower() == "all":
        machines = cfg.get("machines") or {}
        if not machines:
            console.print("[yellow]No known machines in config. Add some with:[/yellow] office-net config add <name> <ip>")
            raise typer.Exit()
        table = Table(title="Ping All Machines")
        table.add_column("Name", style="bold cyan")
        table.add_column("IP", style="green")
        table.add_column("Status")
        for name, ip in machines.items():
            alive = scanner.ping(ip)
            status = "[bold green]UP[/bold green]" if alive else "[bold red]DOWN[/bold red]"
            table.add_row(name, ip, status)
        console.print(table)
    else:
        ip = config.resolve_name(target, cfg)
        console.print(f"Pinging [bold]{ip}[/bold] ...\n")
        output = connect.ping_host(ip)
        console.print(output)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

config_app = typer.Typer(help="View and manage configuration.")
app.add_typer(config_app, name="config")


@config_app.callback(invoke_without_command=True)
def config_show(ctx: typer.Context) -> None:
    """Show current configuration."""
    if ctx.invoked_subcommand is not None:
        return
    cfg = config.load()
    local_ip = config.detect_local_ip()
    console.print(f"[bold]This PC:[/bold] {local_ip or 'unknown'}")
    console.print(f"[bold]Subnet:[/bold]  {cfg['subnet']}.0/24")
    console.print(f"[bold]DB path:[/bold] {config.db_path(cfg)}")
    machines = cfg.get("machines") or {}
    if machines:
        console.print("\n[bold]Known machines:[/bold]")
        table = Table(show_header=True)
        table.add_column("Name", style="cyan")
        table.add_column("IP", style="green")
        for name, ip in machines.items():
            table.add_row(name, ip)
        console.print(table)
    else:
        console.print("\n[dim]No known machines. Add with:[/dim] office-net config add <name> <ip>")


@config_app.command()
def add(
    name: str = typer.Argument(..., help="Friendly name for the machine."),
    ip: str = typer.Argument(..., help="IP address."),
) -> None:
    """Add or update a known machine nickname."""
    cfg = config.load()
    if cfg["machines"] is None:
        cfg["machines"] = {}
    cfg["machines"][name] = ip
    config.save(cfg)
    console.print(f"[green]Saved:[/green] {name} -> {ip}")


@config_app.command()
def remove(
    name: str = typer.Argument(..., help="Name of the machine to remove."),
) -> None:
    """Remove a known machine."""
    cfg = config.load()
    machines = cfg.get("machines") or {}
    if name not in machines:
        console.print(f"[red]Not found:[/red] {name}")
        raise typer.Exit(1)
    del cfg["machines"][name]
    config.save(cfg)
    console.print(f"[green]Removed:[/green] {name}")


# ---------------------------------------------------------------------------
# wake
# ---------------------------------------------------------------------------

@app.command()
def wake(name_or_ip: str = typer.Argument(..., help="Machine name or IP.")) -> None:
    """Send a Wake-on-LAN magic packet to a machine.

    The machine must have been seen in a previous scan (so we know its MAC),
    or you can pass a MAC address directly (aa-bb-cc-dd-ee-ff).
    """
    cfg = config.load()
    dbp = config.db_path(cfg)

    # Check if input looks like a MAC address
    clean = name_or_ip.replace("-", "").replace(":", "")
    if len(clean) == 12 and all(c in "0123456789abcdefABCDEF" for c in clean):
        mac = name_or_ip
    else:
        # Resolve to IP, then look up MAC from last scan
        ip = config.resolve_name(name_or_ip, cfg)
        result = db.get_latest_scan(dbp)
        if result is None:
            console.print("[red]No scan data. Run a scan first so we know the MAC address.[/red]")
            raise typer.Exit(1)
        _, hosts = result
        host = next((h for h in hosts if h.ip == ip), None)
        if host is None or host.mac is None:
            console.print(f"[red]No MAC address found for {ip}. Run a scan first.[/red]")
            raise typer.Exit(1)
        mac = host.mac
        console.print(f"Resolved [bold]{name_or_ip}[/bold] -> {ip} -> MAC {mac}")

    connect.send_wol(mac)
    console.print(f"[green]Wake-on-LAN packet sent to {mac}[/green]")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
