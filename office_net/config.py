"""Load and save office-net configuration from config.yaml."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

import yaml

# Config file lives next to the package (in the repo root)
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _config_path() -> Path:
    """Return the config file path, respecting OFFICE_NET_CONFIG env var."""
    env = os.environ.get("OFFICE_NET_CONFIG")
    if env:
        return Path(env)
    return _DEFAULT_CONFIG_PATH


def detect_local_ip() -> Optional[str]:
    """Run ipconfig and return this machine's local IPv4 address, or None."""
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Find all IPv4 addresses, skip loopback/APIPA
        for match in re.finditer(r"IPv4 Address[.\s]*:\s*([\d.]+)", result.stdout):
            ip = match.group(1)
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass
    return None


def detect_subnet() -> Optional[str]:
    """Auto-detect the LAN subnet (first 3 octets) from ipconfig."""
    ip = detect_local_ip()
    if ip:
        parts = ip.split(".")
        return ".".join(parts[:3])
    return None


def load() -> dict:
    """Load config from YAML. Returns defaults if file is missing."""
    path = _config_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Ensure required keys exist with sensible defaults
    # Auto-detect subnet from ipconfig if not set in config
    if "subnet" not in data:
        data["subnet"] = detect_subnet() or "192.168.1"
    data.setdefault("machines", {})
    data.setdefault("db_path", "office-net.db")

    # Normalise machines to a plain dict (handle None from empty YAML mapping)
    if data["machines"] is None:
        data["machines"] = {}

    return data


def save(data: dict) -> None:
    """Write config back to YAML."""
    path = _config_path()
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def resolve_name(name_or_ip: str, cfg: Optional[dict] = None) -> str:
    """Resolve a friendly name to an IP, or return the input if it's already an IP."""
    if cfg is None:
        cfg = load()
    machines = cfg.get("machines", {}) or {}
    # Direct name lookup
    if name_or_ip in machines:
        return machines[name_or_ip]
    # Already an IP
    return name_or_ip


def db_path(cfg: Optional[dict] = None) -> Path:
    """Return the resolved database file path."""
    if cfg is None:
        cfg = load()
    raw = cfg.get("db_path", "office-net.db")
    p = Path(raw)
    if not p.is_absolute():
        # Relative to the config file's directory
        p = _config_path().parent / p
    return p
