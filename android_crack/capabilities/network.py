from __future__ import annotations

import socket
from dataclasses import dataclass, field

import nmap  # python-nmap

from android_crack.core.adb_client import AdbClient, AdbResult


@dataclass(slots=True)
class NetworkSnapshot:
    serial: str
    ip_addr: str
    routes: str
    dns1: str


@dataclass(slots=True)
class ScanHost:
    ip: str
    state: str
    adb_5555_open: bool = False
    adb_5554_open: bool = False
    fingerprint: str = ""


def local_lan_ip() -> str | None:
    """Best-effort local IPv4 used to derive a /24 for scanning."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


async def ip_snapshot(client: AdbClient, serial: str) -> NetworkSnapshot:
    addr = await client.shell("ip addr", serial=serial)
    if not addr.ok or not addr.stdout.strip():
        addr = await client.shell("ifconfig", serial=serial)
    routes = await client.shell("ip route", serial=serial)
    dns1 = await client.getprop("net.dns1", serial=serial)
    return NetworkSnapshot(
        serial=serial,
        ip_addr=addr.stdout.strip(),
        routes=routes.stdout.strip(),
        dns1=dns1,
    )


async def ping(client: AdbClient, serial: str, host: str, count: int = 4) -> str:
    result = await client.shell(f"ping -c {count} {host}", serial=serial)
    return result.stdout + (("\n" + result.stderr) if result.stderr else "")


async def forward_add(client: AdbClient, local_port: int, remote_port: int) -> AdbResult:
    return await client.run(["forward", f"tcp:{local_port}", f"tcp:{remote_port}"])


async def forward_remove(client: AdbClient, spec: str) -> AdbResult:
    return await client.run(["forward", "--remove", spec])


async def forward_remove_all(client: AdbClient) -> AdbResult:
    return await client.run(["forward", "--remove-all"])


async def forward_list(client: AdbClient) -> str:
    result = await client.run(["forward", "--list"])
    return result.stdout.strip()


async def reverse_add(client: AdbClient, remote_port: int, local_port: int) -> AdbResult:
    return await client.run(["reverse", f"tcp:{remote_port}", f"tcp:{local_port}"])


async def reverse_remove_all(client: AdbClient) -> AdbResult:
    return await client.run(["reverse", "--remove-all"])


def lan_scan(subnet: str, nmap_path: str | None = None) -> list[ScanHost]:
    """Discover live hosts and probe ADB-like ports.

    Heavy operation — synchronous. Run in a worker if calling from async.
    """
    scanner = nmap.PortScanner(nmap_search_path=(nmap_path,) if nmap_path else ())
    scanner.scan(hosts=subnet, arguments="-sn")
    live = [h for h in scanner.all_hosts() if scanner[h]["status"]["state"] == "up"]
    if not live:
        return []

    port_scan = nmap.PortScanner(nmap_search_path=(nmap_path,) if nmap_path else ())
    try:
        port_scan.scan(
            hosts=" ".join(live),
            arguments="-p 5555,5554 -sT -sV --version-intensity 1 -T4",
        )
    except nmap.PortScannerError:
        port_scan = None

    out: list[ScanHost] = []
    for host in sorted(live, key=_ip_sort_key):
        record = ScanHost(ip=host, state="up")
        if port_scan and host in port_scan.all_hosts():
            tcp = port_scan[host].get("tcp") or {}
            fp_bits: list[str] = []
            for port_no, attr in (("adb_5555_open", 5555), ("adb_5554_open", 5554)):
                info = tcp.get(attr)
                if info and info.get("state") == "open":
                    setattr(record, port_no, True)
                    product = info.get("product") or info.get("name") or ""
                    version = info.get("version") or ""
                    label = " ".join(s for s in (str(attr), product, version) if s).strip()
                    if label:
                        fp_bits.append(label)
            record.fingerprint = " · ".join(fp_bits)
        out.append(record)
    return out


def _ip_sort_key(addr: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in addr.split("."))
    except ValueError:
        return (0, 0, 0, 0)
