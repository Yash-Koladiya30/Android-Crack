# Android-Crack

> Android pen-test toolkit over ADB and Metasploit-Framework.
> Built for Kali Linux. Authorized testing only.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
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
- **Plugin system** — drop Python files in `~/.android-crack/plugins/`
- **REST API mode** — `android-crack serve` for automation
- **Free everywhere** — MIT, GitHub, PyPI, Homebrew, Docker (GHCR)

## Install

### Kali / Ubuntu / Debian

```bash
sudo apt update && sudo apt install -y adb metasploit-framework scrcpy nmap python3-pip
pipx install android-crack    # or: pip install --user android-crack
```

### macOS

```bash
brew install android-platform-tools nmap scrcpy
brew install --cask metasploit
pipx install android-crack
```

### Homebrew tap (planned)

```bash
brew tap Yash-Koladiya30/android-crack
brew install android-crack
```

### Docker

```bash
docker run --rm -it --network host ghcr.io/yash-koladiya30/android-crack:latest
```

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

MIT © Yash Koladiya
