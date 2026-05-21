"""Plugin discovery and loading.

Two discovery channels:
1. **Entry points** under group `android_crack.plugins` — for packages
   that ship a `register(app, console)` function and declare it via their
   own pyproject.toml. Suitable for PyPI-distributed plugins.
2. **Directory scan** of `settings.plugins_dir` — for local `.py` files
   the user drops in `~/.config/android-crack/plugins/`. No install step.

A valid plugin module exposes a top-level callable:

    def register(app: typer.Typer, console: rich.console.Console) -> None:
        ...

`register` is called once at CLI startup. It may add Typer commands,
sub-apps, or invoke `app.callback` decorators. Loader catches and logs
exceptions so a broken plugin can never crash the host CLI.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    import typer
    from rich.console import Console

ENTRY_POINT_GROUP = "android_crack.plugins"
_logger = logging.getLogger("android_crack.plugins")


class _Registrar(Protocol):
    def __call__(self, app: typer.Typer, console: Console) -> None: ...


@dataclass(slots=True)
class LoadedPlugin:
    name: str
    source: str  # "entry_point:<name>" or "dir:<path>"
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _collect_entry_points() -> list[tuple[str, Callable[..., None]]]:
    # importlib.metadata.entry_points().select(...) is the canonical API
    # since Python 3.10; we require >=3.11 in pyproject, so no fallback.
    out: list[tuple[str, Callable[..., None]]] = []
    selected = entry_points().select(group=ENTRY_POINT_GROUP)
    for ep in selected:
        try:
            obj = ep.load()
        except Exception as exc:
            _logger.warning("Failed to load entry point %s: %s", ep.name, exc)
            continue
        if callable(obj):
            out.append((ep.name, cast(Callable[..., None], obj)))
    return out


def _load_dir_module(path: Path) -> Callable[..., None] | None:
    spec = importlib.util.spec_from_file_location(
        f"_android_crack_plugin_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        _logger.warning("Plugin %s failed to import: %s", path.name, exc)
        return None
    fn = getattr(module, "register", None)
    if not callable(fn):
        return None
    return fn  # type: ignore[no-any-return]


def discover_plugins(plugins_dir: Path) -> list[tuple[str, str, Callable[..., None]]]:
    """Return (name, source, register_fn) tuples without invoking them yet."""
    found: list[tuple[str, str, Callable[..., None]]] = []

    for name, fn in _collect_entry_points():
        found.append((name, f"entry_point:{name}", fn))

    if plugins_dir.is_dir():
        for file in sorted(plugins_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            register_fn = _load_dir_module(file)
            if register_fn is not None:
                found.append((file.stem, f"dir:{file}", register_fn))
    return found


def load_plugins(
    app: typer.Typer,
    console: Console,
    plugins_dir: Path,
) -> list[LoadedPlugin]:
    """Discover plugins, call each `register(app, console)`. Never raises."""
    results: list[LoadedPlugin] = []
    for name, source, fn in discover_plugins(plugins_dir):
        try:
            fn(app, console)
            results.append(LoadedPlugin(name=name, source=source))
        except Exception:
            tb = traceback.format_exc(limit=4)
            _logger.warning("Plugin %s register() raised:\n%s", name, tb)
            results.append(LoadedPlugin(name=name, source=source, error=tb))
    return results
