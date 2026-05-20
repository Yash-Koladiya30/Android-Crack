# Plugin API

Android-Crack discovers plugins from two sources at startup:

1. **Entry points** in the `android_crack.plugins` group (PyPI packages).
2. **Directory scan** of `~/.config/android-crack/plugins/*.py` (no
   install step).

Either way, a plugin is a Python module exposing one function:

```python
def register(app: typer.Typer, console: rich.console.Console) -> None:
    ...
```

The loader calls this once at CLI startup. It is your hook to add
commands. Exceptions inside `register` are caught and logged — a bad
plugin can never crash the host CLI.

## Minimal example

Save as `~/.config/android-crack/plugins/hello.py`:

```python
import typer
from rich.console import Console


def register(app: typer.Typer, console: Console) -> None:
    @app.command("hello")
    def hello(name: str = "world") -> None:
        console.print(f"[bold cyan]hello, {name}![/bold cyan]")
```

Then:

```bash
android-crack hello --name yash
```

## Add a subcommand group

```python
import typer
from rich.console import Console


def register(app: typer.Typer, console: Console) -> None:
    group = typer.Typer(help="My custom commands")
    app.add_typer(group, name="custom")

    @group.command("ping")
    def ping_cmd() -> None:
        console.print("pong")

    @group.command("echo")
    def echo_cmd(text: str) -> None:
        console.print(text)
```

Use:

```bash
android-crack custom ping
android-crack custom echo "hi"
```

## Use a capability + DevicePool

See `android_crack/plugins/examples/parallel_info.py` for a reference
implementation that calls `cap_info.collect_info` across every ready
device via `DevicePool.gather`.

```python
import asyncio
import typer
from rich.console import Console

from android_crack.capabilities import info as cap_info
from android_crack.core.adb_client import AdbClient
from android_crack.core.device_pool import DevicePool
from android_crack.core.tool_finder import locate_tools


def register(app: typer.Typer, console: Console) -> None:
    @app.command("count-apps")
    def count_apps_cmd(serial: str | None = None) -> None:
        from android_crack.capabilities import apps as cap_apps
        tools = locate_tools()
        if not tools.adb:
            raise typer.Exit(code=2)
        pool = DevicePool(client=AdbClient(tools.adb))
        asyncio.run(pool.refresh())
        if serial:
            pool.select(serial)
        target = pool.require_active()
        packages = asyncio.run(cap_apps.list_packages(pool.client, target))
        console.print(f"[bold]{len(packages)}[/bold] third-party packages")
```

## Distributing on PyPI

In your plugin package's `pyproject.toml`:

```toml
[project.entry-points."android_crack.plugins"]
mything = "my_pkg.plugin:register"
```

Once installed (`pip install my-android-crack-plugin`), the loader picks
it up automatically — no copying files.

## What plugins can do

- Add new `@app.command(...)` entries
- Add new sub-apps with `app.add_typer(...)`
- Wrap existing capabilities with new flags or output formats
- Read `core.settings.Settings.load()` for user config
- Open an SQLite audit scope with `core.audit.AuditLog.scope(...)`

## What plugins should not do

- Mutate other plugins' commands
- Patch `core/*` modules at import time
- Run network calls during `register` itself (defer to command body)
- Print before `register` returns (delays startup)

## Authorization gate

Plugins inherit the same `--i-have-authorization` gate as built-in
commands. If your plugin performs anything destructive or device-side,
call `Settings.load().authorized` and bail with a clear message if
False.
