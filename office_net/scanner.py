"""Network scanning: ping sweep, ARP table, hostname resolution."""

from __future__ import annotations

import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional


@dataclass
class Host:
    """A discovered host on the LAN."""
    ip: str
    mac: Optional[str] = None
    hostname: Optional[str] = None
    alive: bool = False


def ping(ip: str, timeout_ms: int = 500) -> bool:
    """Ping a single IP. Returns True if it responds."""
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), ip],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def ping_sweep(subnet: str, workers: int = 50) -> list[str]:
    """Ping all IPs in a /24 subnet. Returns list of responding IPs."""
    alive: list[str] = []

    def _check(ip: str) -> tuple[str, bool]:
        return ip, ping(ip)

    ips = [f"{subnet}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_check, ip): ip for ip in ips}
        for future in as_completed(futures):
            ip, is_alive = future.result()
            if is_alive:
                alive.append(ip)

    alive.sort(key=lambda ip: tuple(int(p) for p in ip.split(".")))
    return alive


def get_arp_table() -> dict[str, str]:
    """Parse the Windows ARP table. Returns {ip: mac}."""
    mapping: dict[str, str] = {}
    try:
        result = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Lines look like: "  192.168.1.1          aa-bb-cc-dd-ee-ff     dynamic"
        pattern = re.compile(
            r"^\s*([\d.]+)\s+([\da-fA-F]{2}(?:-[\da-fA-F]{2}){5})\s+",
            re.MULTILINE,
        )
        for match in pattern.finditer(result.stdout):
            ip, mac = match.group(1), match.group(2).lower()
            # Skip broadcast MACs
            if mac != "ff-ff-ff-ff-ff-ff":
                mapping[ip] = mac
    except Exception:
        pass
    return mapping


def resolve_hostname(ip: str) -> Optional[str]:
    """Try to resolve an IP to a hostname."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return None


def scan(subnet: str, workers: int = 50) -> list[Host]:
    """Full LAN scan: ping sweep + ARP + hostname resolution."""
    alive_ips = ping_sweep(subnet, workers=workers)

    # Grab ARP table (populated by the pings we just did)
    arp = get_arp_table()

    hosts: list[Host] = []
    # Resolve hostnames in parallel
    with ThreadPoolExecutor(max_workers=20) as pool:
        future_to_ip = {pool.submit(resolve_hostname, ip): ip for ip in alive_ips}
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            hostname = future.result()
            hosts.append(Host(
                ip=ip,
                mac=arp.get(ip),
                hostname=hostname,
                alive=True,
            ))

    hosts.sort(key=lambda h: tuple(int(p) for p in h.ip.split(".")))
    return hosts
