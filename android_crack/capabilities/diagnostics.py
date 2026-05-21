from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal

from android_crack.core.adb_client import AdbClient, AdbResult

StayOn = Literal["usb", "on", "off"]


@dataclass(slots=True)
class Locale:
    system_locales: str
    persist_sys: str
    ro_product: str


@dataclass(slots=True)
class RootReport:
    properties: dict[str, str] = field(default_factory=dict)
    shell_id: str = ""
    which_su: str = ""
    su_paths: str = ""
    magisk_paths: str = ""
    magisk_pkg: str = ""
    score: int = 0
    verdict: str = ""
    reasons: list[str] = field(default_factory=list)


_ROOT_PROPS = (
    "ro.build.type",
    "ro.build.tags",
    "ro.debuggable",
    "ro.secure",
    "service.adb.root",
    "ro.boot.flash.locked",
    "ro.boot.verifiedbootstate",
)


_DEV_KEYS = (
    "animator_duration_scale",
    "transition_animation_scale",
    "window_animation_scale",
    "adb_enabled",
    "stay_on_while_plugged_in",
)


async def collect_locale(client: AdbClient, serial: str) -> Locale:
    system, persist, product = await asyncio.gather(
        client.shell("settings get system system_locales", serial=serial),
        client.getprop("persist.sys.locale", serial=serial),
        client.getprop("ro.product.locale", serial=serial),
    )
    return Locale(
        system_locales=system.text or "—",
        persist_sys=persist or "—",
        ro_product=product or "—",
    )


async def developer_settings_read(client: AdbClient, serial: str) -> dict[str, str]:
    out: dict[str, str] = {}
    coros = [
        client.shell(f"settings get global {key}", serial=serial) for key in _DEV_KEYS
    ]
    results = await asyncio.gather(*coros)
    for key, result in zip(_DEV_KEYS, results, strict=True):
        out[key] = result.text or ""
    return out


async def developer_settings_write(
    client: AdbClient,
    serial: str,
    key: str,
    value: str,
) -> AdbResult:
    return await client.shell(
        f"settings put global {key} {value}",
        serial=serial,
    )


async def screen_stay_on(client: AdbClient, serial: str, mode: StayOn) -> AdbResult:
    arg = {"usb": "usb", "on": "true", "off": "false"}[mode]
    return await client.shell(f"svc power stayon {arg}", serial=serial)


async def root_check(client: AdbClient, serial: str) -> RootReport:
    report = RootReport()

    prop_results = await asyncio.gather(
        *(client.getprop(prop, serial=serial) for prop in _ROOT_PROPS)
    )
    report.properties = dict(zip(_ROOT_PROPS, prop_results, strict=True))

    sid, which, paths, magisk_paths, magisk_pkg = await asyncio.gather(
        client.shell("id", serial=serial),
        client.shell("which su", serial=serial),
        client.shell(
            "sh -c 'ls -l /system/xbin/su /system/bin/su 2>/dev/null | head -2'",
            serial=serial,
        ),
        client.shell(
            "sh -c 'ls /data/adb/magisk/magisk 2>/dev/null; "
            "ls /sbin/magisk 2>/dev/null; "
            "command -v magisk 2>/dev/null'",
            serial=serial,
        ),
        client.shell("pm path com.topjohnwu.magisk", serial=serial),
    )

    report.shell_id = sid.text
    report.which_su = which.text
    report.su_paths = paths.text
    report.magisk_paths = magisk_paths.text
    report.magisk_pkg = magisk_pkg.text

    _score_root(report)
    return report


def _score_root(report: RootReport) -> None:
    score = 0
    reasons: list[str] = []
    props = report.properties

    if "test-keys" in (props.get("ro.build.tags") or "").lower():
        score += 2
        reasons.append("ro.build.tags contains test-keys")
    if (props.get("ro.build.type") or "").lower() in {"eng", "userdebug"}:
        score += 1
        reasons.append(f"ro.build.type={props.get('ro.build.type')}")
    if props.get("ro.debuggable") == "1":
        score += 1
        reasons.append("ro.debuggable=1")
    if props.get("service.adb.root") == "1":
        score += 1
        reasons.append("service.adb.root=1")
    if report.which_su and "not found" not in report.which_su.lower() and report.which_su.strip():
        score += 2
        reasons.append("`which su` returned a path")
    if report.su_paths and "su" in report.su_paths:
        score += 1
        reasons.append("classic /system/*/su present")
    mp = report.magisk_paths
    if mp and ("magisk" in mp.lower() or "/data/adb" in mp):
        score += 3
        reasons.append("Magisk binary / /data/adb path present")
    if report.magisk_pkg and "package:" in report.magisk_pkg:
        score += 2
        reasons.append("Magisk manager package installed")

    report.score = score
    report.reasons = reasons
    if score >= 4:
        report.verdict = "strong root indicators"
    elif score >= 2:
        report.verdict = "some indicators (inconclusive)"
    else:
        report.verdict = "no strong root indicators (typical user build)"
