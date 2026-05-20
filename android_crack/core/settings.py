from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field


def _is_windows() -> bool:
    return sys.platform == "win32" or os.name == "nt"


def _config_dir() -> Path:
    if _is_windows():
        # Windows: %APPDATA%\Android-Crack
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "Android-Crack"
        return Path.home() / "AppData" / "Roaming" / "Android-Crack"

    # Linux / macOS / Termux: XDG
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "android-crack"


def _data_dir() -> Path:
    if _is_windows():
        # Windows: %LOCALAPPDATA%\Android-Crack
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Android-Crack"
        return Path.home() / "AppData" / "Local" / "Android-Crack"

    # Linux / macOS / Termux: XDG
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "android-crack"


class Settings(BaseModel):
    authorized: bool = False
    captures_dir: Path = Field(default_factory=lambda: _data_dir() / "captures")
    downloads_dir: Path = Field(default_factory=lambda: _data_dir() / "downloads")
    audit_db: Path = Field(default_factory=lambda: _data_dir() / "audit.sqlite3")
    plugins_dir: Path = Field(default_factory=lambda: _config_dir() / "plugins")
    default_lhost: str | None = None
    default_lport: int = 4444
    theme: str = "cyber"

    @classmethod
    def config_file(cls) -> Path:
        return _config_dir() / "config.json"

    @classmethod
    def load(cls) -> Settings:
        path = cls.config_file()
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.model_validate(data)

    def save(self) -> None:
        path = self.config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def ensure_dirs(self) -> None:
        for d in (self.captures_dir, self.downloads_dir, self.plugins_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.audit_db.parent.mkdir(parents=True, exist_ok=True)
