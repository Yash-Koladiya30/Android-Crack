from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from android_crack.core.adb_client import AdbClient

Source = Literal["sms", "contacts", "calls"]


_QUERIES: dict[Source, tuple[str, str]] = {
    "sms": ("content://sms/", "address:date:body:type"),
    "contacts": ("content://contacts/phones/", "display_name:number"),
    "calls": ("content://call_log/calls", "name:number:duration:date:type"),
}


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def dump_source(
    client: AdbClient,
    serial: str,
    source: Source,
    out_dir: Path,
) -> Path:
    uri, projection = _QUERIES[source]
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{source}-{serial.replace(':', '_')}-{_timestamp()}.txt"
    local = out_dir / name

    result = await client.shell(
        f'content query --uri {uri} --projection {projection}',
        serial=serial,
    )
    if not result.ok and not result.stdout:
        raise RuntimeError(f"content query failed: {result.stderr.strip()}")

    payload = result.stdout if result.stdout else f"# no rows\n# stderr: {result.stderr}"
    local.write_text(payload, encoding="utf-8", errors="replace")
    return local


async def save_logcat(
    client: AdbClient,
    serial: str,
    out_dir: Path,
    lines: int = 500,
    *,
    filter_spec: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"logcat-{serial.replace(':', '_')}-{_timestamp()}.txt"
    local = out_dir / name
    args = ["logcat", "-d", "-v", "time", "-t", str(lines)]
    if filter_spec:
        args.append(filter_spec)
    result = await client.run(args, serial=serial)
    local.write_text(result.stdout + result.stderr, encoding="utf-8", errors="replace")
    return local


def stream_logcat(adb_path: str, serial: str, *, filter_spec: str | None = None) -> int:
    """Stream `adb logcat -v time` to the operator TTY. Blocks until Ctrl+C.

    Returns the adb process exit code. Synchronous on purpose so the
    TTY is attached directly to the operator's terminal.
    """
    import subprocess

    cmd = [adb_path, "-s", serial, "logcat", "-v", "time"]
    if filter_spec:
        cmd.append(filter_spec)
    return subprocess.call(cmd)
