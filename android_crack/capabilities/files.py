from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from android_crack.core.adb_client import AdbClient, AdbResult

Bucket = Literal["whatsapp", "camera", "screenshots", "downloads", "music", "movies"]


@dataclass(slots=True)
class RemoteEntry:
    name: str
    is_dir: bool


_BUCKET_CANDIDATES: dict[Bucket, list[str]] = {
    "whatsapp": [
        "/sdcard/Android/media/com.whatsapp/WhatsApp",
        "/sdcard/WhatsApp",
    ],
    "camera": ["/sdcard/DCIM/Camera"],
    "screenshots": [
        "/sdcard/Pictures/Screenshots",
        "/sdcard/DCIM/Screenshots",
        "/sdcard/Screenshots",
    ],
    "downloads": ["/sdcard/Download", "/sdcard/Downloads"],
    "music": ["/sdcard/Music"],
    "movies": ["/sdcard/Movies"],
}


async def exists(client: AdbClient, serial: str, remote: str) -> bool:
    quoted = remote.replace("'", r"\'")
    result = await client.shell(f"sh -c 'test -e \"{quoted}\" && echo Y || echo N'", serial=serial)
    return result.text.endswith("Y")


async def is_dir(client: AdbClient, serial: str, remote: str) -> bool:
    quoted = remote.replace("'", r"\'")
    result = await client.shell(f"sh -c 'test -d \"{quoted}\" && echo Y || echo N'", serial=serial)
    return result.text.endswith("Y")


async def list_dir(client: AdbClient, serial: str, remote: str = "/sdcard/") -> list[RemoteEntry]:
    quoted = remote.replace("'", r"\'")
    result = await client.shell(f"ls -aF '{quoted}'", serial=serial)
    entries: list[RemoteEntry] = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if not name or name in {".", "..", "./", "../"}:
            continue
        directory = name.endswith("/")
        clean = name.rstrip("/*@=|")
        entries.append(RemoteEntry(name=clean, is_dir=directory))
    return entries


async def pull_path(
    client: AdbClient,
    serial: str,
    remote: str,
    local_dir: Path,
) -> Path:
    if not await exists(client, serial, remote):
        raise FileNotFoundError(f"Remote path missing: {remote}")
    local_dir.mkdir(parents=True, exist_ok=True)
    result = await client.pull(remote, str(local_dir), serial=serial, timeout=600.0)
    if not result.ok:
        raise RuntimeError(f"adb pull failed: {result.stderr or result.stdout}")
    return local_dir / Path(remote).name


async def push_path(
    client: AdbClient,
    serial: str,
    local: Path,
    remote_dir: str = "/sdcard/",
) -> AdbResult:
    if not local.exists():
        raise FileNotFoundError(f"Local path missing: {local}")
    return await client.push(str(local), remote_dir, serial=serial, timeout=600.0)


async def resolve_bucket(
    client: AdbClient,
    serial: str,
    bucket: Bucket,
) -> str | None:
    """Pick the first matching remote path for a known bucket name."""
    for candidate in _BUCKET_CANDIDATES[bucket]:
        if await is_dir(client, serial, candidate):
            return candidate
    return None


async def pull_bucket(
    client: AdbClient,
    serial: str,
    bucket: Bucket,
    out_dir: Path,
) -> Path:
    remote = await resolve_bucket(client, serial, bucket)
    if remote is None:
        raise FileNotFoundError(f"{bucket} folder not found on device")
    return await pull_path(client, serial, remote, out_dir)
