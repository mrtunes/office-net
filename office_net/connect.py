"""Launch connections to other machines: RDP, shared folders, ping, Wake-on-LAN."""

from __future__ import annotations

import socket
import struct
import subprocess


def launch_rdp(ip: str) -> None:
    """Open Remote Desktop to the given IP."""
    subprocess.Popen(
        ["mstsc", f"/v:{ip}"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def open_share(ip: str, path: str = "") -> None:
    """Open a shared folder in Windows Explorer."""
    unc = f"\\\\{ip}"
    if path:
        unc = f"{unc}\\{path}"
    subprocess.Popen(["explorer", unc])


def ping_host(ip: str, count: int = 4) -> str:
    """Ping a host and return the raw output."""
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), ip],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return result.stdout
    except Exception as e:
        return f"Ping failed: {e}"


def open_web(ip: str) -> None:
    """Open the device's web admin page in the default browser."""
    subprocess.Popen(
        ["start", f"http://{ip}"],
        shell=True,
    )


def send_wol(mac: str) -> None:
    """Send a Wake-on-LAN magic packet.

    mac: MAC address in any common format (aa-bb-cc-dd-ee-ff or aa:bb:cc:dd:ee:ff).
    """
    # Normalise MAC to raw bytes
    mac_clean = mac.replace("-", "").replace(":", "").replace(".", "")
    if len(mac_clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    mac_bytes = bytes.fromhex(mac_clean)

    # Magic packet: 6 x 0xFF then 16 x MAC
    packet = b"\xff" * 6 + mac_bytes * 16

    # Send as UDP broadcast on port 9
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(packet, ("255.255.255.255", 9))
    sock.close()
