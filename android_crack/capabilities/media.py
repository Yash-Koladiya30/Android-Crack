from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Literal

from android_crack.core.adb_client import AdbClient

AudioSource = Literal["mic", "device"]


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


def mirror(
    scrcpy_path: str,
    serial: str | None = None,
    *,
    max_size: int | None = None,
    bitrate_mbps: float | None = None,
    max_fps: int | None = None,
) -> int:
    """Launch scrcpy to mirror + control the device.

    Returns the scrcpy exit code. Blocks until the user closes scrcpy.
    Public scrcpy flags only (--serial, -m, -b, --max-fps).
    """
    cmd: list[str] = [scrcpy_path]
    if serial:
        cmd += ["--serial", serial]
    if max_size:
        cmd += ["-m", str(max_size)]
    if bitrate_mbps:
        cmd += ["-b", f"{bitrate_mbps}M"]
    if max_fps:
        cmd += [f"--max-fps={max_fps}"]
    return subprocess.call(cmd)


def stream_audio(scrcpy_path: str, source: AudioSource, serial: str | None = None) -> int:
    """Live audio stream over scrcpy (no video).

    Requires Android 11+. Blocks until user stops scrcpy.
    """
    cmd: list[str] = [scrcpy_path, "--no-video"]
    if serial:
        cmd += ["--serial", serial]
    if source == "mic":
        cmd.append("--audio-source=mic")
    return subprocess.call(cmd)


def record_audio(
    scrcpy_path: str,
    source: AudioSource,
    out_path: Path,
    serial: str | None = None,
    *,
    play_while_recording: bool = False,
) -> int:
    """Record audio to a file via scrcpy.

    play_while_recording=False adds --no-playback for headless capture.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [scrcpy_path, "--no-video", f"--record={out_path}"]
    if not play_while_recording:
        cmd.append("--no-playback")
    if serial:
        cmd += ["--serial", serial]
    if source == "mic":
        cmd.append("--audio-source=mic")
    return subprocess.call(cmd)


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
