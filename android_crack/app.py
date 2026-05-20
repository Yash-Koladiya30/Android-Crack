from __future__ import annotations

from android_crack.core.plugin_loader import load_plugins
from android_crack.core.settings import Settings
from android_crack.ui.banner import console
from android_crack.ui.cli import app


def _bootstrap_plugins() -> None:
    """Discover and register plugins before the CLI handles argv."""
    settings = Settings.load()
    settings.ensure_dirs()
    load_plugins(app, console, settings.plugins_dir)


def main() -> None:
    _bootstrap_plugins()
    app()


if __name__ == "__main__":
    main()
