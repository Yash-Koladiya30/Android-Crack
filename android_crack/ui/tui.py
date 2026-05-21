"""Textual TUI front-end.

Lightweight by design: table of connected devices, action shortcuts
(refresh / info / screenshot), and a scrolling log pane for output.
Heavier features stay in the CLI for now.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, RichLog

from android_crack.capabilities import info as cap_info
from android_crack.capabilities import media as cap_media
from android_crack.core.adb_client import AdbClient
from android_crack.core.device_pool import DevicePool
from android_crack.core.settings import Settings
from android_crack.core.tool_finder import locate_tools


class AndroidCrackTUI(App[None]):
    CSS = """
    Screen { background: $surface; }
    DataTable { height: 40%; }
    #log { height: 60%; border: heavy $primary; }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("i", "info", "Info"),
        Binding("p", "capture", "Screenshot"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, settings: Settings, adb_path: str) -> None:
        super().__init__()
        self.settings = settings
        self.client = AdbClient(adb_path)
        self.pool = DevicePool(client=self.client)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield DataTable(id="devices", cursor_type="row", zebra_stripes=True)
            yield RichLog(id="log", highlight=True, markup=True, wrap=True)
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#devices", DataTable)
        table.add_columns("Serial", "State", "Model", "Product")
        self.title = "Android-Crack"
        self.sub_title = "Authorized testing only"
        await self.action_refresh()

    def _selected_serial(self) -> str | None:
        table = self.query_one("#devices", DataTable)
        row = table.cursor_row
        if row is None or row < 0 or row >= len(self.pool.devices):
            return None
        return self.pool.devices[row].serial

    async def action_refresh(self) -> None:
        log = self.query_one("#log", RichLog)
        log.write("[dim]Refreshing devices…[/dim]")
        await self.pool.refresh()
        table = self.query_one("#devices", DataTable)
        table.clear()
        for device in self.pool.devices:
            table.add_row(
                device.serial,
                device.state,
                device.model or "—",
                device.product or "—",
            )
        log.write(f"[bold green]{len(self.pool.devices)} device(s)[/bold green]")

    async def action_info(self) -> None:
        log = self.query_one("#log", RichLog)
        serial = self._selected_serial()
        if not serial:
            log.write("[bold red]Select a device row first.[/bold red]")
            return
        info = await cap_info.collect_info(self.client, serial)
        log.write(
            f"[bold magenta]{info.serial}[/bold magenta]  "
            f"{info.manufacturer} {info.model}  "
            f"Android {info.android_version}  SDK {info.sdk}  "
            f"patch {info.security_patch or '—'}"
        )

    async def action_capture(self) -> None:
        log = self.query_one("#log", RichLog)
        serial = self._selected_serial()
        if not serial:
            log.write("[bold red]Select a device row first.[/bold red]")
            return
        self.settings.ensure_dirs()
        try:
            local = await cap_media.screenshot(
                self.client, serial, self.settings.captures_dir
            )
        except RuntimeError as e:
            log.write(f"[bold red]Screenshot failed:[/bold red] {e}")
            return
        log.write(f"[bold green]Saved:[/bold green] {local}")


def run_tui() -> None:
    settings = Settings.load()
    if not settings.authorized:
        raise SystemExit(
            "Run `android-crack --i-have-authorization` before launching the TUI."
        )
    tools = locate_tools()
    if not tools.adb:
        raise SystemExit("adb not found on PATH.")
    AndroidCrackTUI(settings, tools.adb).run()
