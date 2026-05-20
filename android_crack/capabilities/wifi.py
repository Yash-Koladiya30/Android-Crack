from __future__ import annotations

import re
from collections import OrderedDict

from android_crack.core.adb_client import AdbClient, AdbResult


# Patterns derived from the public AOSP `cmd wifi list-networks` /
# `dumpsys wifi` output formats. SSID-only — no password material extracted.
_SSID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'Network\s+Id\s+\d+\s+SSID\s+"([^"]+)"', re.I),
    re.compile(r'WifiConfiguration\{[^}]*?SSID\s*=\s*"([^"]+)"', re.I),
    re.compile(r'(?:^|\s)SSID:\s*"([^"]+)"', re.M),
    re.compile(r'mWifiSSID\s*=\s*"([^"]+)"', re.I),
)

_STATUS_KEYS = (
    "ssid",
    "bssid",
    "ip address",
    "ipaddress",
    "rssi",
    "link speed",
    "frequency",
    "state:",
)

_JUNK = {"null", "unknown", "any", "<unknown ssid>", "0x", "wifi", "wlan"}


def _is_plausible(ssid: str) -> bool:
    s = ssid.strip()
    if not 1 <= len(s) <= 128:
        return False
    if s.lower() in _JUNK:
        return False
    if re.match(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$", s):
        return False
    return True


def _ordered_unique(items: list[str]) -> list[str]:
    seen: OrderedDict[str, None] = OrderedDict()
    for item in items:
        clean = item.strip()
        if clean and _is_plausible(clean):
            seen[clean] = None
    return list(seen.keys())


def parse_ssids(blob: str) -> list[str]:
    found: list[str] = []
    for pattern in _SSID_PATTERNS:
        for match in pattern.finditer(blob):
            found.append(match.group(1))
    return _ordered_unique(found)


async def wifi_status(client: AdbClient, serial: str) -> list[str]:
    """Return filtered `dumpsys wifi` lines (no passwords)."""
    result = await client.shell("dumpsys wifi", serial=serial)
    out: list[str] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        low = line.lower()
        if any(key in low for key in _STATUS_KEYS):
            out.append(line)
    return out[:120]


async def wlan_ip(client: AdbClient, serial: str) -> str:
    """Show IPv4/v6 on wlan0; fall back to all interfaces."""
    result = await client.shell("ip addr show wlan0", serial=serial)
    text = result.stdout.strip()
    if not text or "does not exist" in text.lower():
        result = await client.shell("ip addr", serial=serial)
        text = result.stdout.strip()
    return text


async def wifi_set(client: AdbClient, serial: str, enable: bool) -> AdbResult:
    action = "enable" if enable else "disable"
    return await client.shell(f"svc wifi {action}", serial=serial)


async def saved_networks(client: AdbClient, serial: str) -> list[str]:
    """SSIDs only. Tries `cmd wifi list-networks` then `dumpsys wifi`.

    Will not extract passwords; many ROMs don't expose them at all without
    root. SSIDs alone are useful for inventory / matching.
    """
    primary = await client.shell("cmd wifi list-networks", serial=serial)
    body = primary.stdout
    if "Unknown command" not in body and "Invalid argument" not in body:
        parsed = parse_ssids(body)
        if parsed:
            return parsed

    secondary = await client.shell("cmd -w wifi list-networks", serial=serial)
    parsed = parse_ssids(secondary.stdout)
    if parsed:
        return parsed

    dump = await client.shell("dumpsys wifi", serial=serial)
    return parse_ssids(dump.stdout)
