# Architecture

Android-Crack is layered so each surface (CLI, TUI, REST) shares the same
capability functions and the same audit trail.

```
┌─────────────────────────────────────────────────────────────────┐
│  surfaces                                                       │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐               │
│  │ Typer CLI  │  │ Textual TUI│  │ FastAPI REST │               │
│  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘               │
│        │               │                 │                       │
│        ▼               ▼                 ▼                       │
│  ┌──────────────────────────────────────────────────┐           │
│  │ capabilities/   (pure async functions)           │           │
│  │   apps · files · exports · media · network ·     │           │
│  │   wifi · diagnostics · exploit · connect · info  │           │
│  └────────┬──────────────────────────────┬──────────┘           │
│           │                              │                       │
│           ▼                              ▼                       │
│  ┌─────────────────┐         ┌────────────────────────┐         │
│  │ core/AdbClient  │         │ core/AuditLog (SQLite) │         │
│  │ core/DevicePool │         └────────────────────────┘         │
│  └────────┬────────┘                                             │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────┐            │
│  │ external tools: adb · msfvenom · msfconsole ·   │            │
│  │                  scrcpy · nmap                  │            │
│  └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## Design rules

1. **Capabilities are pure async functions.** Signature is
   `(client: AdbClient, serial: str, ...) -> Result`. No global state,
   no I/O assumptions, no UI awareness. Every surface uses them.

2. **DevicePool is the only place that knows about ANDROID_SERIAL.**
   `pool.refresh()` parses `adb devices -l`, `pool.select(serial)` picks
   one, `pool.gather(action, serials)` runs the same call across many.

3. **AdbClient runs adb as subprocess per call.** No daemon, no
   persistent connection. Async wrappers let many calls run concurrently
   while still keeping the binary itself stateless.

4. **Settings + audit live under XDG dirs.**
   - Config: `~/.config/android-crack/config.json`
   - Captures: `~/.local/share/android-crack/captures/`
   - Downloads: `~/.local/share/android-crack/downloads/`
   - Audit DB: `~/.local/share/android-crack/audit.sqlite3`
   - Plugins: `~/.config/android-crack/plugins/*.py`

5. **`--i-have-authorization` is a hard gate.** Until set once, every
   user-facing surface refuses to act and prints the disclaimer. Stored
   in the config JSON.

6. **Audit log captures every REST call.** CLI commands can opt into
   `AuditLog.scope(...)` as the project grows. Only `stdout_sha`
   (sha256) is stored, not raw output — provenance without bloat.

## Module map

| Path | Role |
|---|---|
| `android_crack/app.py` | Entry point; loads plugins; hands off to Typer |
| `android_crack/core/adb_client.py` | Async adb wrapper, `AdbResult` dataclass |
| `android_crack/core/device_pool.py` | Device tracking + parallel dispatch |
| `android_crack/core/settings.py` | Pydantic config persisted to XDG |
| `android_crack/core/tool_finder.py` | Locate adb / msf / scrcpy / nmap |
| `android_crack/core/audit.py` | SQLite audit log + async `scope()` |
| `android_crack/core/plugin_loader.py` | Entry-point + directory plugin discovery |
| `android_crack/capabilities/*.py` | Domain functions (one file per area) |
| `android_crack/ui/cli.py` | Typer command tree |
| `android_crack/ui/banner.py` | Rich theme + ASCII banner |
| `android_crack/ui/tui.py` | Textual app |
| `android_crack/api/server.py` | FastAPI factory + uvicorn launcher |
| `android_crack/plugins/examples/` | Reference plugins |

## Why async everywhere?

Multi-device fan-out is the most expensive operation in this tool:
screenshot 5 devices, dump SMS from 3, install an APK on 8. Sync
subprocess would serialize all of that. `asyncio.create_subprocess_exec`
plus `asyncio.gather` lets every adb invocation run in parallel,
bottlenecked only by the device count, not by Python.

The CLI layer still calls `asyncio.run(...)` per command — async is an
implementation detail, not a user-facing constraint.
