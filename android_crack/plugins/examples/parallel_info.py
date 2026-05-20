"""Example plugin: `android-crack fleet-info` — quick fleet status.

Demonstrates calling capabilities + DevicePool.gather() from a plugin.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from android_crack.capabilities import info as cap_info
from android_crack.core.adb_client import AdbClient
from android_crack.core.device_pool import DevicePool
from android_crack.core.tool_finder import locate_tools


def register(app: typer.Typer, console: Console) -> None:
    @app.command("fleet-info")
    def fleet_info_cmd() -> None:
        """Print one-line info for every ready device."""
        tools = locate_tools()
        if not tools.adb:
            console.print("[red]adb not on PATH[/red]")
            raise typer.Exit(code=2)
        pool = DevicePool(client=AdbClient(tools.adb))
        asyncio.run(pool.refresh())
        ready = [d.serial for d in pool.devices if d.ready]
        if not ready:
            console.print("[yellow]No ready devices.[/yellow]")
            return

        async def _one(serial: str) -> tuple[str, cap_info.DeviceInfo]:
            return serial, await cap_info.collect_info(pool.client, serial)

        rows = asyncio.run(pool.gather(lambda s: _one(s), serials=ready))
        table = Table(title=f"Fleet ({len(rows)})", header_style="bold cyan")
        table.add_column("Serial", style="magenta")
        table.add_column("Device", style="green")
        table.add_column("Android")
        for serial, info in rows:
            table.add_row(
                serial,
                f"{info.manufacturer} {info.model}".strip() or "—",
                info.android_version or "—",
            )
        console.print(table)
