from __future__ import annotations

import asyncio
import subprocess

from android_crack.core.adb_client import AdbClient, AdbResult


async def run_command(client: AdbClient, serial: str, command: str) -> AdbResult:
    """Non-interactive shell exec. Captures stdout/stderr."""
    return await client.shell(command, serial=serial)


def interactive_shell(adb_path: str, serial: str) -> int:
    """Hand control to the user's terminal for a live `adb shell` session.

    Returns the adb exit code. Synchronous on purpose — we want the
    foreground TTY attached, not piped.
    """
    return subprocess.call([adb_path, "-s", serial, "shell"])


async def send_keycode(client: AdbClient, serial: str, keycode: int | str) -> AdbResult:
    """Send a single keyevent. Accepts numeric code or named (e.g. 'HOME')."""
    return await client.shell(f"input keyevent {keycode}", serial=serial)


async def send_text(client: AdbClient, serial: str, text: str) -> AdbResult:
    safe = text.replace("'", r"\'")
    return await client.shell(f"input text '{safe}'", serial=serial)
