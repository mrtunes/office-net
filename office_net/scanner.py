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
    device_type: str = ""


# Well-known ports to check
DEFAULT_PORTS: dict[int, str] = {
    80: "HTTP",
    443: "HTTPS",
    3389: "RDP",
    445: "SMB",
    9100: "RAW print",
    631: "IPP",
}

# Hostname keywords that indicate a printer
_PRINTER_KEYWORDS = ("kyocera", "printer", "epson", "hp", "canon", "brother", "xerox")


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


def check_ports(
    ip: str,
    ports: Optional[dict[int, str]] = None,
    timeout: float = 0.5,
) -> list[tuple[int, str, bool]]:
    """Check which ports are open on *ip*.

    Returns a list of (port, service_name, is_open) tuples.
    """
    if ports is None:
        ports = DEFAULT_PORTS
    results: list[tuple[int, str, bool]] = []
    for port, name in sorted(ports.items()):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            is_open = sock.connect_ex((ip, port)) == 0
        except OSError:
            is_open = False
        finally:
            sock.close()
        results.append((port, name, is_open))
    return results


def detect_type(ip: str, hostname: Optional[str] = None) -> str:
    """Guess whether *ip* is a printer, PC, or unknown.

    Checks printer-specific ports (9100, 631) and hostname keywords.
    """
    # Hostname heuristic
    if hostname:
        lower = hostname.lower()
        for kw in _PRINTER_KEYWORDS:
            if kw in lower:
                return "Printer"

    # Port heuristic — printer ports
    sock_timeout = 0.3
    for port in (9100, 631):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(sock_timeout)
        try:
            if sock.connect_ex((ip, port)) == 0:
                return "Printer"
        except OSError:
            pass
        finally:
            sock.close()

    # If RDP is open it's likely a PC
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(sock_timeout)
    try:
        if sock.connect_ex((ip, 3389)) == 0:
            return "PC"
    except OSError:
        pass
    finally:
        sock.close()

    return ""


def resolve_hostname(ip: str) -> Optional[str]:
    """Try to resolve an IP to a hostname."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return None


def scan(subnet: str, workers: int = 50) -> list[Host]:
    """Full LAN scan: ping sweep + ARP + hostname resolution + type detection."""
    alive_ips = ping_sweep(subnet, workers=workers)

    # Grab ARP table (populated by the pings we just did)
    arp = get_arp_table()

    # Resolve hostnames in parallel
    hostnames: dict[str, Optional[str]] = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        future_to_ip = {pool.submit(resolve_hostname, ip): ip for ip in alive_ips}
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            hostnames[ip] = future.result()

    # Detect device types in parallel
    device_types: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=20) as pool:
        future_to_ip = {
            pool.submit(detect_type, ip, hostnames.get(ip)): ip
            for ip in alive_ips
        }
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            device_types[ip] = future.result()

    hosts: list[Host] = []
    for ip in alive_ips:
        hosts.append(Host(
            ip=ip,
            mac=arp.get(ip),
            hostname=hostnames.get(ip),
            alive=True,
            device_type=device_types.get(ip, ""),
        ))

    hosts.sort(key=lambda h: tuple(int(p) for p in h.ip.split(".")))
    return hosts
