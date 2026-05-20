from __future__ import annotations

from datetime import datetime
from pathlib import Path

from android_crack.core.adb_client import AdbClient


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def screenshot(
    client: AdbClient,
    serial: str,
    out_dir: Path,
    *,
    anonymous: bool = False,
) -> Path:
    """Capture a PNG screenshot and pull it to `out_dir`.

    If anonymous=True, the remote file is removed after pull.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"screenshot-{serial.replace(':', '_')}-{_timestamp()}.png"
    remote = f"/sdcard/{name}"
    local = out_dir / name

    cap = await client.shell(f"screencap -p {remote}", serial=serial)
    if not cap.ok:
        raise RuntimeError(f"screencap failed: {cap.stderr or cap.stdout}")

    pull = await client.pull(remote, str(local), serial=serial)
    if not pull.ok:
        raise RuntimeError(f"adb pull failed: {pull.stderr or pull.stdout}")

    if anonymous:
        await client.shell(f"rm {remote}", serial=serial)

    return local


async def screen_record(
    client: AdbClient,
    serial: str,
    out_dir: Path,
    seconds: int,
    *,
    anonymous: bool = False,
) -> Path:
    if seconds < 1:
        raise ValueError("seconds must be >= 1")
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"screenrec-{serial.replace(':', '_')}-{_timestamp()}.mp4"
    remote = f"/sdcard/{name}"
    local = out_dir / name

    rec = await client.run(
        ["shell", "screenrecord", "--time-limit", str(seconds), remote],
        serial=serial,
        timeout=float(seconds + 15),
    )
    if not rec.ok:
        raise RuntimeError(f"screenrecord failed: {rec.stderr or rec.stdout}")

    pull = await client.pull(remote, str(local), serial=serial)
    if not pull.ok:
        raise RuntimeError(f"adb pull failed: {pull.stderr or pull.stdout}")

    if anonymous:
        await client.shell(f"rm {remote}", serial=serial)

    return local
