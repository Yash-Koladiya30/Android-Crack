#!/usr/bin/env bash
# Android-Crack — dependency installer for Linux, macOS, and Termux.
# Detects the package manager and installs adb, scrcpy, nmap, and
# metasploit-framework where available. Python 3.11+ is required.

set -e

YES=0
COMPONENTS=""
INTERACTIVE=0

usage() {
    cat <<'USAGE'
Usage: install.sh [options]

  --yes              Skip per-component prompts (non-interactive)
  --interactive      Ask before each component
  --components LIST  Comma-separated subset: adb,metasploit,scrcpy,nmap,pip,python
  -h, --help         Show this help

Detected distros: Ubuntu / Debian / Mint / Kali / Parrot / Fedora /
                   Arch / Manjaro / Termux / macOS (Homebrew)
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) YES=1; shift ;;
        --interactive) INTERACTIVE=1; shift ;;
        --components) COMPONENTS="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 2 ;;
    esac
done

wants() {
    if [[ -z "$COMPONENTS" ]]; then return 0; fi
    [[ ",$COMPONENTS," == *",$1,"* ]]
}

confirm() {
    if [[ $YES -eq 1 ]]; then return 0; fi
    if [[ $INTERACTIVE -ne 1 ]]; then return 0; fi
    read -r -p "Install $1? [Y/n] " ans
    [[ -z "$ans" || "$ans" == "y" || "$ans" == "Y" ]]
}

detect_os() {
    if [[ -n "${TERMUX_VERSION:-}" ]] || command -v termux-info >/dev/null 2>&1; then
        echo "termux"; return
    fi
    case "$(uname -s)" in
        Darwin) echo "macos"; return ;;
    esac
    if [[ -r /etc/os-release ]]; then
        . /etc/os-release
        case "${ID_LIKE:-} ${ID:-}" in
            *debian*|*ubuntu*) echo "debian"; return ;;
            *fedora*|*rhel*)   echo "fedora"; return ;;
            *arch*)            echo "arch";   return ;;
        esac
        case "${ID:-}" in
            ubuntu|debian|kali|parrot|mint|linuxmint|raspbian|pop) echo "debian"; return ;;
            fedora|rhel|centos|rocky|almalinux) echo "fedora"; return ;;
            arch|manjaro|endeavouros|garuda) echo "arch"; return ;;
        esac
    fi
    echo "unknown"
}

OS="$(detect_os)"
echo "[android-crack] Detected: $OS"

case "$OS" in
    debian)
        SUDO="sudo"
        [[ $EUID -eq 0 ]] && SUDO=""
        $SUDO apt-get update
        if wants python && confirm "python3 + venv"; then
            $SUDO apt-get install -y python3 python3-venv python3-pip
        fi
        wants pip && confirm "pip"          && $SUDO apt-get install -y python3-pip
        wants adb && confirm "adb"          && $SUDO apt-get install -y adb
        wants scrcpy && confirm "scrcpy"    && $SUDO apt-get install -y scrcpy || true
        wants nmap && confirm "nmap"        && $SUDO apt-get install -y nmap
        if wants metasploit && confirm "metasploit-framework"; then
            $SUDO apt-get install -y metasploit-framework 2>/dev/null || \
                echo "[android-crack] metasploit-framework not in repo. See https://www.metasploit.com/download"
        fi
        ;;
    fedora)
        SUDO="sudo"; [[ $EUID -eq 0 ]] && SUDO=""
        wants python   && confirm "python3"        && $SUDO dnf install -y python3 python3-pip
        wants pip      && confirm "pip"            && $SUDO dnf install -y python3-pip
        wants adb      && confirm "android-tools"  && $SUDO dnf install -y android-tools
        wants scrcpy   && confirm "scrcpy"         && ($SUDO dnf install -y scrcpy || echo "scrcpy unavailable")
        wants nmap     && confirm "nmap"           && $SUDO dnf install -y nmap
        if wants metasploit && confirm "metasploit-framework"; then
            echo "[android-crack] metasploit-framework: follow https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html"
        fi
        ;;
    arch)
        SUDO="sudo"; [[ $EUID -eq 0 ]] && SUDO=""
        $SUDO pacman -Sy --noconfirm
        wants python  && confirm "python"       && $SUDO pacman -S --noconfirm python python-pip
        wants pip     && confirm "python-pip"   && $SUDO pacman -S --noconfirm python-pip
        wants adb     && confirm "android-tools"&& $SUDO pacman -S --noconfirm android-tools
        wants scrcpy  && confirm "scrcpy"       && $SUDO pacman -S --noconfirm scrcpy
        wants nmap    && confirm "nmap"         && $SUDO pacman -S --noconfirm nmap
        if wants metasploit && confirm "metasploit (AUR)"; then
            echo "[android-crack] metasploit lives in AUR — use yay/paru: yay -S metasploit"
        fi
        ;;
    termux)
        pkg update -y
        wants python  && confirm "python"        && pkg install -y python
        wants pip     && confirm "pip"           && python -m ensurepip --upgrade
        wants adb     && confirm "android-tools" && pkg install -y android-tools
        wants nmap    && confirm "nmap"          && pkg install -y nmap
        wants scrcpy  && confirm "scrcpy"        && pkg install -y scrcpy || \
            echo "[android-crack] scrcpy may not be available on Termux."
        if wants metasploit && confirm "metasploit"; then
            echo "[android-crack] Install Metasploit on Termux via:"
            echo "  pkg install unstable-repo && pkg install metasploit"
        fi
        ;;
    macos)
        if ! command -v brew >/dev/null 2>&1; then
            echo "[android-crack] Install Homebrew first: https://brew.sh"
            exit 2
        fi
        wants adb     && confirm "android-platform-tools" && brew install android-platform-tools
        wants scrcpy  && confirm "scrcpy"                 && brew install scrcpy
        wants nmap    && confirm "nmap"                   && brew install nmap
        if wants metasploit && confirm "metasploit (cask)"; then
            brew install --cask metasploit
        fi
        ;;
    unknown|*)
        cat <<'MSG'
[android-crack] Could not detect a supported package manager.
Install these manually:
  - python 3.11+
  - adb (Android platform-tools)
  - metasploit-framework
  - scrcpy
  - nmap
MSG
        exit 1
        ;;
esac

echo
echo "[android-crack] Dependencies installed. Next:"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -e ."
echo "  android-crack --i-have-authorization"
