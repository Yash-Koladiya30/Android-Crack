from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from android_crack.core.adb_client import AdbClient, AdbResult

PackageKind = Literal["all", "third_party", "system"]


@dataclass(slots=True)
class InstalledPackage:
    name: str
    source: str = ""


def _flag_for(kind: PackageKind) -> str:
    if kind == "third_party":
        return "-3"
    if kind == "system":
        return "-s"
    return ""


async def list_packages(
    client: AdbClient,
    serial: str,
    kind: PackageKind = "third_party",
) -> list[InstalledPackage]:
    flag = _flag_for(kind)
    cmd = "pm list packages" + (f" {flag}" if flag else "")
    result = await client.shell(cmd, serial=serial)
    out: list[InstalledPackage] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            out.append(InstalledPackage(name=line.removeprefix("package:")))
    return out


async def package_paths(client: AdbClient, serial: str, package: str) -> list[str]:
    result = await client.shell(f"pm path {package}", serial=serial)
    return [
        line.removeprefix("package:").strip()
        for line in result.stdout.splitlines()
        if line.startswith("package:")
    ]


async def install_apk(
    client: AdbClient,
    serial: str,
    apk: Path,
    *,
    replace: bool = True,
    grant_runtime_perms: bool = False,
) -> AdbResult:
    args = ["install"]
    if replace:
        args.append("-r")
    if grant_runtime_perms:
        args.append("-g")
    args.append(str(apk))
    return await client.run(args, serial=serial, timeout=180.0)


async def install_split_apks(
    client: AdbClient,
    serial: str,
    apks: list[Path],
    *,
    replace: bool = True,
) -> AdbResult:
    if not apks:
        raise ValueError("At least one APK path is required.")
    args = ["install-multiple"]
    if replace:
        args.append("-r")
    args += [str(p) for p in apks]
    return await client.run(args, serial=serial, timeout=300.0)


async def uninstall(
    client: AdbClient,
    serial: str,
    package: str,
    *,
    keep_data: bool = False,
) -> AdbResult:
    args = ["uninstall"]
    if keep_data:
        args.append("-k")
    args.append(package)
    return await client.run(args, serial=serial)


async def launch(client: AdbClient, serial: str, package: str) -> AdbResult:
    return await client.shell(
        f"monkey -p {package} -c android.intent.category.LAUNCHER 1",
        serial=serial,
    )


async def force_stop(client: AdbClient, serial: str, package: str) -> AdbResult:
    return await client.shell(f"am force-stop {package}", serial=serial)


async def clear_data(client: AdbClient, serial: str, package: str) -> AdbResult:
    return await client.shell(f"pm clear {package}", serial=serial)


async def restart_app(client: AdbClient, serial: str, package: str) -> AdbResult:
    await force_stop(client, serial, package)
    return await launch(client, serial, package)


async def grant_permission(
    client: AdbClient,
    serial: str,
    package: str,
    permission: str,
) -> AdbResult:
    return await client.shell(f"pm grant {package} {permission}", serial=serial)


async def revoke_permission(
    client: AdbClient,
    serial: str,
    package: str,
    permission: str,
) -> AdbResult:
    return await client.shell(f"pm revoke {package} {permission}", serial=serial)


async def extract_apk(
    client: AdbClient,
    serial: str,
    package: str,
    out_dir: Path,
) -> Path:
    """Pull the installed base APK for `package` into `out_dir`."""
    paths = await package_paths(client, serial, package)
    if not paths:
        raise RuntimeError(f"App not found on device: {package}")

    base = next((p for p in paths if p.endswith("base.apk") or "/base.apk" in p), paths[0])

    out_dir.mkdir(parents=True, exist_ok=True)
    safe = package.replace(".", "_")
    local = out_dir / f"{safe}.apk"

    pull = await client.pull(base, str(local), serial=serial)
    if not pull.ok:
        raise RuntimeError(f"adb pull failed: {pull.stderr or pull.stdout}")
    return local
