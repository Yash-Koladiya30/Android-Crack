# Changelog

## 0.7.0 — Phase 7 (unreleased)

- `core/plugin_loader.py`: discover via `android_crack.plugins`
  entry points + directory scan of `~/.config/android-crack/plugins/`.
  Broken plugins are logged but never crash the host CLI.
- `app.py` bootstraps plugins before Typer handles argv.
- Example plugins shipped: `plugins/examples/uptime.py`,
  `plugins/examples/parallel_info.py`.
- Docs: `docs/architecture.md`, `docs/plugin-api.md`,
  `docs/authorization.md`.
- Tests: directory plugin loads + adds command, broken plugin isolated
  from good one, missing dir + underscore files skipped.

## 0.6.0 — Phase 5 + 6 (unreleased)

- `core/audit.py`: SQLite event store with operator + host stamps,
  duration, exit code, stdout sha256. Async `scope()` context manager
  used by REST handlers.
- `cluster` group: fan out `info`, `screenshot`, `shell -c CMD` across
  many devices in parallel via `DevicePool.gather`.
- `audit` group: `tail [-n]`, `path`, `clear -y`.
- `ui/tui.py`: Textual app with device table + Rich log pane; bindings
  `r` refresh, `i` info, `p` screenshot, `q` quit.
- `api/server.py`: FastAPI app behind `android-crack serve`. Endpoints
  for devices/info/battery/apps/screenshot/wifi-saved/root/exports/
  audit-tail. Lazy import + helpful message when `[api]` extra missing.
- Tests: audit record/tail/clear, async scope (success + failure),
  CLI registration of new groups.

## 0.4.0 — Phase 4 (unreleased)

- `exploit` group: `payload` (msfvenom build), `handler` (msfconsole
  multi/handler), `run` (full chain: build → install → launch → handler)
- `PayloadConfig` with strict IPv4 / port validation
- Opt-in `--disable-verifier` (always restored on exit via try/finally)
- Opt-in `--auto-accept` install-dialog keyevent helper (off by default)
- Built-in disclaimer panel before `exploit run` proceeds
- Tests: LHOST/LPORT validation, capability surface, CLI registration

## 0.3.0 — Phase 3 (unreleased)

- `network` group: `ip` snapshot (interfaces/routes/dns), `ping`, `scan`
  (LAN host discovery + ADB 5555/5554 nmap fingerprint), `reverse`,
  `forward {add,remove,clear,list}`
- `wifi` group: `status`, `ip`, `enable`, `disable` (confirms), `saved`
  (SSID-only, no passwords)
- `diag` group: `battery`, `locale`, `root` heuristics with scored verdict,
  `stayon`, `devsettings get|set`
- Capability modules: `network.py`, `wifi.py`, `diagnostics.py`
- SSID parser tested standalone; root scorer tested for stock + Magisk paths

## 0.2.0 — Phase 2 (unreleased)

- `apps` command group: list (all/third_party/system), install (`-r`/`-g`),
  install-multi (split APKs), uninstall, launch, force-stop, clear, restart,
  perm grant/revoke, extract APK to disk
- `files` command group: ls remote dir, pull, push, bucket pulls
  (whatsapp / camera / screenshots / downloads / music / movies)
- `export` command group: SMS, contacts, call log, logcat snippet
- `record` command: screen-record N seconds, pull MP4, optional anonymous
- Helper `_resolve_target` factors out repeated device-select boilerplate
- `AdbClient.pull/push` now accept `timeout`
- Tests: capability surface check + Typer help smoke

## 0.1.0 — Phase 1 MVP (unreleased)

- Project scaffold (pyproject, Typer CLI, Rich theme, Textual placeholder)
- Async `AdbClient` with timeout/retry primitives
- `DevicePool` with multi-device tracking + `gather` for parallel ops
- Capabilities: connect/pair/disconnect, shell (interactive + one-shot),
  device info, screenshot (regular + anonymous)
- `Settings` (pydantic) persisted under XDG config dir
- `--i-have-authorization` first-run gate
- Eye-catching ASCII banner + magenta/cyan theme
- Dockerfile (Kali base) + GitHub Actions CI
- MIT license, smoke tests
