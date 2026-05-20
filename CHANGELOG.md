# Changelog

## 0.9.0 — Phase 8b (feature gap-fill) (unreleased)

Closes the functional gaps flagged in the v0.7.0 self-review.

- `cap_media.mirror` / `media mirror` — scrcpy screen mirroring with
  `-m`, `-b`, `--max-fps`, `--serial` passthrough.
- `cap_media.stream_audio` / `media audio stream mic|device` — live
  audio over scrcpy (Android 11+).
- `cap_media.record_audio` / `media audio record mic|device` — record
  to `.opus`; `--play` to monitor live while recording.
- `capabilities/comms.py` + `comms` group:
  - `comms sms NUMBER MESSAGE` — `service call isms 5` parcel.
    BETA, varies per Android version.
  - `comms open URL` — `am start -a android.intent.action.VIEW`.
    Scheme allow-list: http/https/tel/mailto/geo/intent.
- `keycodes` — interactive REPL with 19 named keycodes from public
  Android KeyEvent constants; `t TEXT` to type, `k CODE` for arbitrary
  keycodes, `q` to quit.
- Tests: phone/URL validators, send_sms / open_link bad-input rejection,
  media surface presence, phase-8b CLI registration.

## 0.8.0 — Phase 8a (license + cross-OS) (unreleased)

- **License:** MIT → GPL-3.0-or-later. LICENSE stub now ships a
  copyright header + SPDX identifier; release maintainer must populate
  full GPL-3.0 text from FSF:
  `curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE`
- `core/settings.py`: Windows-aware config + data dirs
  (`%APPDATA%\Android-Crack\`, `%LOCALAPPDATA%\Android-Crack\`).
  Linux / macOS / Termux keep XDG paths.
- `install.sh`: auto-detects Ubuntu / Debian / Mint / Kali / Parrot /
  Fedora / Arch / Manjaro / Termux / macOS and installs adb, scrcpy,
  nmap, metasploit-framework, Python via the native package manager.
  Subset selection via `--components` and `--interactive`.
- `install.ps1`: Windows 11 winget-first (choco fallback) installer.
  Requires elevated PowerShell. Same `-Components` / `-Interactive`.
- README rewritten with compatibility table, per-OS install steps,
  Docker, source dev workflow, and config-dir cheatsheet.

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
