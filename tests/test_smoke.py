from typer.testing import CliRunner

from android_crack import __version__
from pathlib import Path

import pytest

from android_crack.capabilities import apps as cap_apps
from android_crack.capabilities import diagnostics as cap_diag
from android_crack.capabilities import exploit as cap_exploit
from android_crack.capabilities import exports as cap_exports
from android_crack.capabilities import files as cap_files
from android_crack.capabilities import network as cap_net
from android_crack.capabilities import wifi as cap_wifi
from android_crack.core.settings import Settings
from android_crack.core.tool_finder import locate_tools
from android_crack.ui.cli import app


def test_version() -> None:
    assert __version__


def test_settings_defaults() -> None:
    s = Settings()
    assert s.authorized is False
    assert s.default_lport == 4444


def test_locate_tools_runs() -> None:
    tools = locate_tools()
    assert hasattr(tools, "adb")
    assert hasattr(tools, "msfvenom")


def test_capabilities_modules_have_expected_symbols() -> None:
    assert callable(cap_apps.list_packages)
    assert callable(cap_apps.install_apk)
    assert callable(cap_apps.extract_apk)
    assert callable(cap_files.list_dir)
    assert callable(cap_files.pull_bucket)
    assert callable(cap_exports.dump_source)
    assert callable(cap_exports.save_logcat)


def test_cli_help_lists_phase2_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("apps", "files", "export", "record"):
        assert group in result.stdout


def test_cli_help_lists_phase3_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for group in ("network", "wifi", "diag"):
        assert group in result.stdout


def test_cli_help_lists_phase4_group() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "exploit" in result.stdout


def test_payload_config_validates_lhost() -> None:
    with pytest.raises(ValueError):
        cap_exploit.PayloadConfig(lhost="not-an-ip").validate()
    with pytest.raises(ValueError):
        cap_exploit.PayloadConfig(lhost="999.1.1.1").validate()


def test_payload_config_validates_lport() -> None:
    with pytest.raises(ValueError):
        cap_exploit.PayloadConfig(lhost="10.0.0.1", lport=0).validate()
    with pytest.raises(ValueError):
        cap_exploit.PayloadConfig(lhost="10.0.0.1", lport=70000).validate()


def test_payload_config_accepts_valid() -> None:
    cap_exploit.PayloadConfig(lhost="192.168.1.5", lport=4444).validate()


def test_exploit_capability_surface() -> None:
    assert callable(cap_exploit.generate_payload)
    assert callable(cap_exploit.install_payload)
    assert callable(cap_exploit.launch_payload)
    assert callable(cap_exploit.set_verifier)
    assert callable(cap_exploit.run_handler)
    assert cap_exploit.DEFAULT_PAYLOAD == "android/meterpreter/reverse_tcp"
    assert cap_exploit.DEFAULT_PACKAGE == "com.metasploit.stage"


def test_cli_help_lists_phase56_groups() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for entry in ("cluster", "audit", "tui", "serve"):
        assert entry in result.stdout


def test_audit_record_and_tail(tmp_path: Path) -> None:
    from android_crack.core.audit import AuditLog

    log = AuditLog(tmp_path / "audit.sqlite3")
    log.record(
        capability="test.cap",
        serial="SER123",
        args={"foo": 1, "bar": "baz"},
        exit_code=0,
        duration_ms=42.5,
        stdout="hello",
    )
    log.record(
        capability="test.fail",
        serial=None,
        args={},
        exit_code=2,
        duration_ms=10.0,
        error="boom",
    )
    rows = log.tail(10)
    assert len(rows) == 2
    assert rows[0]["capability"] == "test.fail"
    assert rows[0]["error"] == "boom"
    assert rows[1]["capability"] == "test.cap"
    assert rows[1]["args"] == {"foo": 1, "bar": "baz"}
    assert rows[1]["stdout_sha"] is not None
    assert log.clear() == 2
    assert log.tail(10) == []


async def test_audit_scope_records_success(tmp_path: Path) -> None:
    from android_crack.core.audit import AuditLog

    log = AuditLog(tmp_path / "audit.sqlite3")
    async with log.scope("ok.cap", "ser1", {"k": "v"}) as scope:
        scope.stdout = "result"
        scope.exit_code = 0
    rows = log.tail(1)
    assert rows[0]["capability"] == "ok.cap"
    assert rows[0]["exit_code"] == 0


async def test_audit_scope_records_failure(tmp_path: Path) -> None:
    from android_crack.core.audit import AuditLog

    log = AuditLog(tmp_path / "audit.sqlite3")
    with pytest.raises(RuntimeError):
        async with log.scope("fail.cap", None, {}):
            raise RuntimeError("nope")
    rows = log.tail(1)
    assert rows[0]["capability"] == "fail.cap"
    assert rows[0]["exit_code"] == 1
    assert "nope" in (rows[0]["error"] or "")


def test_plugin_loader_loads_directory_plugin(tmp_path: Path) -> None:
    import typer
    from rich.console import Console

    from android_crack.core.plugin_loader import load_plugins

    plugin_file = tmp_path / "ping.py"
    plugin_file.write_text(
        "import typer\n"
        "from rich.console import Console\n"
        "\n"
        "def register(app: typer.Typer, console: Console) -> None:\n"
        "    @app.command('plugin-ping')\n"
        "    def _ping() -> None:\n"
        "        console.print('pong')\n"
    )

    test_app = typer.Typer()
    results = load_plugins(test_app, Console(), tmp_path)
    assert any(r.name == "ping" and r.ok for r in results)

    runner = CliRunner()
    result = runner.invoke(test_app, ["plugin-ping"])
    assert result.exit_code == 0
    assert "pong" in result.stdout


def test_plugin_loader_isolates_broken_plugin(tmp_path: Path) -> None:
    import typer
    from rich.console import Console

    from android_crack.core.plugin_loader import load_plugins

    (tmp_path / "broken.py").write_text(
        "def register(app, console):\n"
        "    raise RuntimeError('intentional')\n"
    )
    (tmp_path / "good.py").write_text(
        "def register(app, console):\n"
        "    @app.command('good-cmd')\n"
        "    def _g() -> None:\n"
        "        console.print('ok')\n"
    )

    test_app = typer.Typer()
    results = load_plugins(test_app, Console(), tmp_path)
    by_name = {r.name: r for r in results}
    assert "broken" in by_name and not by_name["broken"].ok
    assert "good" in by_name and by_name["good"].ok


def test_plugin_loader_ignores_missing_dir(tmp_path: Path) -> None:
    import typer
    from rich.console import Console

    from android_crack.core.plugin_loader import load_plugins

    nonexistent = tmp_path / "nope"
    results = load_plugins(typer.Typer(), Console(), nonexistent)
    assert all(not r.source.startswith("dir:") for r in results)


def test_plugin_loader_skips_underscore_files(tmp_path: Path) -> None:
    import typer
    from rich.console import Console

    from android_crack.core.plugin_loader import load_plugins

    (tmp_path / "_helper.py").write_text(
        "def register(app, console):\n"
        "    raise RuntimeError('should not run')\n"
    )
    results = load_plugins(typer.Typer(), Console(), tmp_path)
    assert all(r.name != "_helper" for r in results)


def test_phase3_capability_surface() -> None:
    assert callable(cap_net.ip_snapshot)
    assert callable(cap_net.ping)
    assert callable(cap_net.forward_add)
    assert callable(cap_net.reverse_add)
    assert callable(cap_net.lan_scan)
    assert callable(cap_wifi.wifi_status)
    assert callable(cap_wifi.wifi_set)
    assert callable(cap_wifi.saved_networks)
    assert callable(cap_diag.collect_locale)
    assert callable(cap_diag.root_check)
    assert callable(cap_diag.developer_settings_read)
    assert callable(cap_diag.developer_settings_write)
    assert callable(cap_diag.screen_stay_on)


def test_wifi_ssid_parser_skips_junk() -> None:
    blob = (
        'Network Id 0  SSID "HomeNet"\n'
        'Network Id 1  SSID "Cafe-2.4"\n'
        'WifiConfiguration{ SSID="null" }\n'
        'unrelated junk line\n'
        'SSID: "Office Guest"\n'
    )
    ssids = cap_wifi.parse_ssids(blob)
    assert "HomeNet" in ssids
    assert "Cafe-2.4" in ssids
    assert "Office Guest" in ssids
    assert "null" not in ssids


def test_root_scoring_no_signals() -> None:
    report = cap_diag.RootReport()
    report.properties = {
        "ro.build.type": "user",
        "ro.build.tags": "release-keys",
        "ro.debuggable": "0",
        "ro.secure": "1",
        "service.adb.root": "0",
    }
    report.which_su = "su: not found"
    cap_diag._score_root(report)
    assert report.score == 0
    assert "no strong" in report.verdict


def test_root_scoring_magisk_signals() -> None:
    report = cap_diag.RootReport()
    report.properties = {"ro.build.type": "userdebug", "ro.build.tags": "test-keys"}
    report.which_su = "/system/bin/su"
    report.magisk_paths = "/data/adb/magisk/magisk"
    report.magisk_pkg = "package:/data/app/com.topjohnwu.magisk-1/base.apk"
    cap_diag._score_root(report)
    assert report.score >= 4
    assert "strong" in report.verdict
