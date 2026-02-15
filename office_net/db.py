"""SQLite storage for scan snapshots and history."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from office_net.scanner import Host


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open (and initialise if needed) the database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id  INTEGER NOT NULL REFERENCES scans(id),
            ip       TEXT NOT NULL,
            mac      TEXT,
            hostname TEXT,
            alive    INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.commit()
    return conn


def save_scan(db_path: Path, hosts: list[Host]) -> int:
    """Save a list of discovered hosts as a new scan snapshot. Returns scan id."""
    conn = _connect(db_path)
    ts = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute("INSERT INTO scans (timestamp) VALUES (?)", (ts,))
    scan_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO hosts (scan_id, ip, mac, hostname, alive) VALUES (?, ?, ?, ?, ?)",
        [(scan_id, h.ip, h.mac, h.hostname, int(h.alive)) for h in hosts],
    )
    conn.commit()
    conn.close()
    return scan_id


def get_latest_scan(db_path: Path) -> Optional[tuple[str, list[Host]]]:
    """Return (timestamp, hosts) for the most recent scan, or None."""
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT id, timestamp FROM scans ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        conn.close()
        return None
    scan_id, ts = row
    rows = conn.execute(
        "SELECT ip, mac, hostname, alive FROM hosts WHERE scan_id = ?", (scan_id,)
    ).fetchall()
    conn.close()
    hosts = [
        Host(ip=r[0], mac=r[1], hostname=r[2], alive=bool(r[3])) for r in rows
    ]
    hosts.sort(key=lambda h: tuple(int(p) for p in h.ip.split(".")))
    return ts, hosts


def get_previous_scan(db_path: Path) -> Optional[tuple[str, list[Host]]]:
    """Return the second-most-recent scan (for diffing)."""
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT id, timestamp FROM scans ORDER BY id DESC LIMIT 2"
    ).fetchall()
    if len(rows) < 2:
        conn.close()
        return None
    scan_id, ts = rows[1]
    host_rows = conn.execute(
        "SELECT ip, mac, hostname, alive FROM hosts WHERE scan_id = ?", (scan_id,)
    ).fetchall()
    conn.close()
    hosts = [
        Host(ip=r[0], mac=r[1], hostname=r[2], alive=bool(r[3])) for r in host_rows
    ]
    hosts.sort(key=lambda h: tuple(int(p) for p in h.ip.split(".")))
    return ts, hosts


def diff_scans(
    old_hosts: list[Host], new_hosts: list[Host]
) -> dict[str, list]:
    """Compare two scan results. Returns {added: [], removed: [], changed: []}."""
    old_by_ip = {h.ip: h for h in old_hosts}
    new_by_ip = {h.ip: h for h in new_hosts}

    added = [h for ip, h in new_by_ip.items() if ip not in old_by_ip]
    removed = [h for ip, h in old_by_ip.items() if ip not in new_by_ip]

    changed = []
    for ip in set(old_by_ip) & set(new_by_ip):
        o, n = old_by_ip[ip], new_by_ip[ip]
        if o.mac != n.mac or o.hostname != n.hostname:
            changed.append((o, n))

    return {"added": added, "removed": removed, "changed": changed}


def get_history(db_path: Path, ip: Optional[str] = None) -> list[dict]:
    """Return scan history. If ip is given, filter to that IP."""
    conn = _connect(db_path)
    if ip:
        rows = conn.execute("""
            SELECT s.timestamp, h.ip, h.mac, h.hostname
            FROM hosts h JOIN scans s ON h.scan_id = s.id
            WHERE h.ip = ?
            ORDER BY s.id DESC
        """, (ip,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT s.timestamp, h.ip, h.mac, h.hostname
            FROM hosts h JOIN scans s ON h.scan_id = s.id
            ORDER BY s.id DESC, h.ip
        """).fetchall()
    conn.close()
    return [
        {"timestamp": r[0], "ip": r[1], "mac": r[2], "hostname": r[3]}
        for r in rows
    ]
