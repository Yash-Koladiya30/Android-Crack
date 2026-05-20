"""Device power, lock, and reboot operations.

All built on public ADB primitives:
- `adb reboot [TARGET]`   — restart, recovery, bootloader, fastboot
- `adb shell reboot -p`   — power off
- `adb shell input keyevent 26`  — power button (lock / wake)
- `adb shell input swipe`         — swipe-up unlock gesture
- `adb shell input text`          — PIN / password entry
"""

from __future__ import annotations

import asyncio
from typing import Literal

from android_crack.core.adb_client import AdbClient, AdbResult

RebootTarget = Literal["system", "recovery", "bootloader", "fastboot"]


async def reboot(
    client: AdbClient,
    serial: str,
    target: RebootTarget = "system",
) -> AdbResult:
    if target == "system":
        return await client.run(["reboot"], serial=serial)
    return await client.run(["reboot", target], serial=serial)


async def power_off(client: AdbClient, serial: str) -> AdbResult:
    return await client.shell("reboot -p", serial=serial)


async def lock_device(client: AdbClient, serial: str) -> AdbResult:
    """Press the power button. If screen on → screen off (locks)."""
    return await client.shell("input keyevent 26", serial=serial)


async def unlock_device(
    client: AdbClient,
    serial: str,
    pin_or_password: str | None = None,
) -> tuple[AdbResult, ...]:
    """Power on → swipe-up → optional PIN/password → enter.

    Works on most stock launchers. PIN must be the device's actual PIN
    (this does not bypass authentication — operator must already know it).
    """
    results: list[AdbResult] = []
    # Wake screen (press power if asleep)
    results.append(await client.shell("input keyevent 26", serial=serial))
    await asyncio.sleep(0.2)
    # Swipe up to dismiss lock screen
    results.append(
        await client.shell("input swipe 500 1500 500 500 200", serial=serial)
    )
    await asyncio.sleep(0.2)
    if pin_or_password:
        safe = pin_or_password.replace("'", r"\'")
        results.append(
            await client.shell(f"input text '{safe}'", serial=serial)
        )
        await asyncio.sleep(0.1)
        results.append(await client.shell("input keyevent 66", serial=serial))
    return tuple(results)


_INTENT_TYPES = {
    "photo": "image/*",
    "audio": "audio/*",
    "video": "video/*",
}

MediaKind = Literal["photo", "audio", "video"]


async def push_and_open_media(
    client: AdbClient,
    serial: str,
    kind: MediaKind,
    local_path: str,
    remote_name: str | None = None,
) -> AdbResult:
    """Push a file under /sdcard/, then launch a VIEW intent for it."""
    mime = _INTENT_TYPES[kind]
    name = remote_name or local_path.rsplit("/", 1)[-1]
    remote = f"/sdcard/{name}"

    push = await client.push(local_path, remote, serial=serial)
    if not push.ok:
        return push

    return await client.shell(
        f'am start -a android.intent.action.VIEW -d "file://{remote}" -t "{mime}"',
        serial=serial,
    )
