from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

from android_crack import __version__

THEME = Theme(
    {
        "brand": "bold magenta",
        "accent": "bold cyan",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
        "muted": "grey50",
        "kbd": "bold black on white",
    }
)

console = Console(theme=THEME, highlight=False)


ASCII = r"""
   ___           __           _     __   ______                __
  / _ |  ___ _  / / _ _____  (_)___/ /  / ____/______ _  ___  / /__
 / __ | / _ `/ /_/_// __/ // / __  /  / /__  / __/ _ `/ / __/ /  '_/
/_/ |_| \_,_/   /_/ /_/  \_, /\_,_/   \____/_/  \_,_/ /__/ /_/\_\
                        /___/
"""


def show_banner() -> None:
    title = Text(ASCII, style="brand")
    sub = Text.assemble(
        ("Android-Crack ", "brand"),
        (f"v{__version__}", "accent"),
        ("  ·  ", "muted"),
        ("ADB + Metasploit toolkit", "accent"),
        ("  ·  ", "muted"),
        ("by Yash Koladiya", "ok"),
    )
    panel = Panel.fit(
        Text.assemble(title, "\n", sub),
        border_style="magenta",
        padding=(0, 2),
    )
    console.print(panel)


def show_disclaimer() -> None:
    body = Text.assemble(
        (
            "Authorized testing only. Use on devices you own or for "
            "engagements with written scope. You are responsible for "
            "compliance with all applicable laws.\n\n",
            "warn",
        ),
        ("Confirm with: ", "muted"),
        ("android-crack --i-have-authorization", "kbd"),
    )
    console.print(
        Panel(body, title="[warn]Disclaimer[/warn]", border_style="yellow", padding=(1, 2))
    )
