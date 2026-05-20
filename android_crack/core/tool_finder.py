from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class ExternalTools:
    adb: str | None
    msfvenom: str | None
    msfconsole: str | None
    scrcpy: str | None
    nmap: str | None

    @property
    def metasploit_ready(self) -> bool:
        return bool(self.msfvenom and self.msfconsole)

    def missing(self) -> list[str]:
        gaps: list[str] = []
        if not self.adb:
            gaps.append("adb")
        if not self.msfvenom or not self.msfconsole:
            gaps.append("metasploit-framework")
        if not self.scrcpy:
            gaps.append("scrcpy")
        if not self.nmap:
            gaps.append("nmap")
        return gaps


def locate_tools() -> ExternalTools:
    return ExternalTools(
        adb=shutil.which("adb"),
        msfvenom=shutil.which("msfvenom"),
        msfconsole=shutil.which("msfconsole"),
        scrcpy=shutil.which("scrcpy"),
        nmap=shutil.which("nmap"),
    )
