from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypeVar

from android_crack.core.adb_client import AdbClient, AdbResult


@dataclass(slots=True)
class Device:
    serial: str
    state: str = "unknown"
    transport: str = ""
    model: str = ""
    product: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "device"


T = TypeVar("T")


@dataclass
class DevicePool:
    """Track ADB devices and dispatch capability calls.

    `gather` runs the same capability against N devices concurrently
    and returns results in the same order.
    """

    client: AdbClient
    devices: list[Device] = field(default_factory=list)
    active: str | None = None

    async def refresh(self) -> list[Device]:
        result: AdbResult = await self.client.run(["devices", "-l"])
        items: list[Device] = []
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line and " " not in line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            kv = {k: v for token in parts[2:] if ":" in token for k, v in [token.split(":", 1)]}
            items.append(
                Device(
                    serial=serial,
                    state=state,
                    transport=kv.get("transport_id", ""),
                    model=kv.get("model", ""),
                    product=kv.get("product", ""),
                )
            )
        self.devices = items
        if self.active and not any(d.serial == self.active for d in items):
            self.active = None
        if not self.active:
            ready = [d for d in items if d.ready]
            if len(ready) == 1:
                self.active = ready[0].serial
        return items

    def select(self, serial: str) -> None:
        if not any(d.serial == serial for d in self.devices):
            raise ValueError(f"Unknown device serial: {serial}")
        self.active = serial

    def require_active(self) -> str:
        if not self.active:
            raise RuntimeError(
                "No active device. Run `android-crack devices` then select one with --serial."
            )
        return self.active

    async def gather(
        self,
        action: Callable[[str], Awaitable[T]],
        *,
        serials: list[str] | None = None,
    ) -> list[T]:
        targets = serials or [d.serial for d in self.devices if d.ready]
        return await asyncio.gather(*(action(s) for s in targets))
