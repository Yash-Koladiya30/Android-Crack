from __future__ import annotations

import asyncio
from dataclasses import dataclass


class AdbUnavailable(RuntimeError):
    """Raised when adb binary cannot be located on PATH."""


@dataclass(slots=True)
class AdbResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return self.stdout.strip()


class AdbClient:
    """Async wrapper around the adb binary.

    Construct once per process with the resolved adb path. Every call runs
    a fresh subprocess — no daemon, no persistent connection.
    """

    def __init__(self, adb_path: str, default_timeout: float = 30.0) -> None:
        self._adb = adb_path
        self._timeout = default_timeout

    async def run(
        self,
        args: list[str],
        *,
        serial: str | None = None,
        timeout: float | None = None,
    ) -> AdbResult:
        full = [self._adb]
        if serial:
            full += ["-s", serial]
        full += args

        proc = await asyncio.create_subprocess_exec(
            *full,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout or self._timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise

        return AdbResult(
            returncode=proc.returncode if proc.returncode is not None else -1,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    async def shell(self, command: str, *, serial: str | None = None) -> AdbResult:
        return await self.run(["shell", command], serial=serial)

    async def getprop(self, key: str, *, serial: str | None = None) -> str:
        result = await self.shell(f"getprop {key}", serial=serial)
        return result.text

    async def push(
        self,
        local: str,
        remote: str,
        *,
        serial: str | None = None,
        timeout: float | None = None,
    ) -> AdbResult:
        return await self.run(["push", local, remote], serial=serial, timeout=timeout)

    async def pull(
        self,
        remote: str,
        local: str,
        *,
        serial: str | None = None,
        timeout: float | None = None,
    ) -> AdbResult:
        return await self.run(["pull", remote, local], serial=serial, timeout=timeout)
