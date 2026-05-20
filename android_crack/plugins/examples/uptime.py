"""Example plugin: adds `android-crack uptime` showing device uptime.

Copy this file to `~/.config/android-crack/plugins/uptime.py` to enable
on your machine. The register() function is the only required hook.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from android_crack.core.adb_client import AdbClient
from android_crack.core.device_pool import DevicePool
from android_crack.core.tool_finder import locate_tools


def register(app: typer.Typer, console: Console) -> None:
    @app.command("uptime")
    def uptime_cmd(
        serial: str | None = typer.Option(None, "--serial", "-s"),
    ) -> None:
        """Show device uptime via `uptime` shell command."""
        tools = locate_tools()
        if not tools.adb:
            console.print("[red]adb not on PATH[/red]")
            raise typer.Exit(code=2)
        pool = DevicePool(client=AdbClient(tools.adb))
        asyncio.run(pool.refresh())
        if serial:
            pool.select(serial)
        target = pool.require_active()
        result = asyncio.run(pool.client.shell("uptime", serial=target))
        console.print(result.text or "[dim](no output)[/dim]")
