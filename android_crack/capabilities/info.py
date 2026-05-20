from __future__ import annotations

import asyncio
from dataclasses import dataclass

from android_crack.core.adb_client import AdbClient


@dataclass(slots=True)
class DeviceInfo:
    serial: str
    model: str
    manufacturer: str
    board: str
    android_version: str
    sdk: str
    security_patch: str
    build_date: str
    encryption: str
    sim_operator: str
    wifi_interface: str


_PROPS = {
    "model": "ro.product.model",
    "manufacturer": "ro.product.manufacturer",
    "board": "ro.product.board",
    "android_version": "ro.build.version.release",
    "sdk": "ro.build.version.sdk",
    "security_patch": "ro.build.version.security_patch",
    "build_date": "ro.build.date",
    "encryption": "ro.crypto.state",
    "sim_operator": "gsm.sim.operator.alpha",
    "wifi_interface": "wifi.interface",
}


async def collect_info(client: AdbClient, serial: str) -> DeviceInfo:
    pairs = await asyncio.gather(
        *(client.getprop(prop, serial=serial) for prop in _PROPS.values())
    )
    values = dict(zip(_PROPS.keys(), pairs, strict=True))
    return DeviceInfo(serial=serial, **values)


async def battery(client: AdbClient, serial: str) -> dict[str, str]:
    result = await client.shell("dumpsys battery", serial=serial)
    out: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out
