# Android-Crack

> Android pen-test toolkit over ADB and Metasploit-Framework.
> Built for Kali Linux. Authorized testing only.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-GPL--3.0-blue)
![Status](https://img.shields.io/badge/status-alpha-orange)

Android-Crack wraps `adb`, `msfvenom`, `msfconsole`, `scrcpy`, and `nmap`
behind a modern CLI and TUI. Designed for security researchers and
penetration testers working on devices they own or are authorized to test.

## Highlights

- **Modern async ADB client** — no blocking subprocess spam
- **Multi-device parallel ops** — run actions across N targets at once
- **Wireless ADB pairing** — Android 11+ pair-code flow (`adb pair`)
- **Rich CLI + Textual TUI** — pick your interface
- **Audit log** — SQLite trail of every command you ran
- **Plugin system** — drop Python files under your config dir
- **REST API mode** — `android-crack serve` for automation
- **Free, GPL-3.0** — GitHub, PyPI, Homebrew tap, Docker (GHCR)

## Compatibility

Tested on:

| OS | Status |
|---|---|
| Kali Linux (rolling) | ✅ primary target |
| Ubuntu 22.04+ | ✅ |
| Linux Mint 21+ | ✅ |
| Debian 12+ | ✅ |
| Fedora 38+ | ✅ |
| Arch Linux / Manjaro / EndeavourOS | ✅ |
| Parrot Security OS | ✅ |
| Windows 11 (24H2) | ✅ (some scrcpy edge cases) |
| Termux (Android 11+) | ✅ (no Metasploit on standard repos) |
| macOS 13+ | ✅ (via Homebrew) |

Python ≥ **3.11** required everywhere.

## Install

### Automatic — Linux / macOS / Termux

```bash
git clone https://github.com/Yash-Koladiya30/Android-Crack.git
cd Android-Crack
chmod +x install.sh
./install.sh                                # installs adb, scrcpy, nmap, msf
# or pick a subset:
./install.sh --components adb,nmap,python   # skip msf/scrcpy
./install.sh --interactive                  # ask per component
```

### Automatic — Windows 11

```powershell
git clone https://github.com/Yash-Koladiya30/Android-Crack.git
cd Android-Crack
# Run PowerShell as Administrator
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
# or pick a subset:
.\install.ps1 -Components adb,nmap,python
.\install.ps1 -Interactive
```

### Manual — Kali / Ubuntu / Debian / Mint / Parrot

```bash
sudo apt update && sudo apt install -y adb metasploit-framework scrcpy nmap python3 python3-venv python3-pip
pipx install android-crack
```

### Manual — Fedora

```bash
sudo dnf install -y android-tools nmap scrcpy python3 python3-pip
# metasploit-framework: follow https://docs.metasploit.com/
pipx install android-crack
```

### Manual — Arch / Manjaro

```bash
sudo pacman -S android-tools scrcpy nmap python python-pip
# metasploit lives in AUR: yay -S metasploit
pipx install android-crack
```

### Manual — Termux (Android)

```bash
pkg update && pkg install -y python android-tools nmap
pip install --user android-crack
```

### Manual — macOS

```bash
brew install android-platform-tools nmap scrcpy
brew install --cask metasploit
pipx install android-crack
```

### Manual — Windows 11

```powershell
winget install Python.Python.3.12 Google.PlatformTools Genymobile.scrcpy Insecure.Nmap
# Metasploit: https://www.metasploit.com/download
pipx install android-crack
```

### Homebrew tap (planned)

```bash
brew tap Yash-Koladiya30/android-crack
brew install android-crack
```

### Docker (any OS with Docker)

```bash
docker run --rm -it --network host ghcr.io/yash-koladiya30/android-crack:latest
```

### From source (development)

```bash
git clone https://github.com/Yash-Koladiya30/Android-Crack.git
cd Android-Crack
python3 -m venv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,api]"
pytest -q
```

## Config / data directories

Per-OS XDG-compliant defaults (override with `XDG_CONFIG_HOME` / `XDG_DATA_HOME`):

| OS | Config | Captures / Audit DB / Downloads |
|---|---|---|
| Linux / Termux | `~/.config/android-crack/` | `~/.local/share/android-crack/` |
| macOS | `~/.config/android-crack/` | `~/.local/share/android-crack/` |
| Windows | `%APPDATA%\Android-Crack\` | `%LOCALAPPDATA%\Android-Crack\` |

Drop plugin `.py` files in the config dir under `plugins/` — see [docs/plugin-api.md](docs/plugin-api.md).

## Quick start

```bash
# First-run authorization gate (one time)
android-crack --i-have-authorization

# Pair wireless device (Android 11+)
android-crack connect pair 192.168.1.42:37123

# Connect via classic 5555
android-crack connect 192.168.1.42

# List devices
android-crack devices

# Take screenshot
android-crack screenshot

# Open interactive shell
android-crack shell

# Show device info
android-crack info

# Launch TUI
android-crack tui
```

## Authorization

This tool is for **authorized testing only**:

- Devices you own
- Engagements with written scope
- CTF / training labs
- Defensive security research

The `--i-have-authorization` flag must be confirmed before any
destructive or invasive action runs.

**Do not** use against devices you do not own or do not have explicit
written permission to test. You are responsible for compliance with all
applicable laws.

## License

GPL-3.0-or-later © 2026 Yash Koladiya. See [LICENSE](LICENSE).
