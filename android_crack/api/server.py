"""FastAPI REST front-end.

Exposes a subset of capabilities over JSON HTTP for automation. Binds to
127.0.0.1 by default; expose externally only behind your own auth/proxy.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from android_crack import __version__
from android_crack.capabilities import apps as cap_apps
from android_crack.capabilities import diagnostics as cap_diag
from android_crack.capabilities import exports as cap_exports
from android_crack.capabilities import info as cap_info
from android_crack.capabilities import media as cap_media
from android_crack.capabilities import wifi as cap_wifi
from android_crack.core.adb_client import AdbClient
from android_crack.core.audit import AuditLog
from android_crack.core.device_pool import DevicePool
from android_crack.core.settings import Settings
from android_crack.core.tool_finder import locate_tools


class HealthResponse(BaseModel):
    status: str
    version: str


class DeviceModel(BaseModel):
    serial: str
    state: str
    transport: str
    model: str
    product: str


class ScreenshotResponse(BaseModel):
    path: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    if not settings.authorized:
        raise RuntimeError(
            "Run `android-crack --i-have-authorization` before starting the API."
        )
    tools = locate_tools()
    if not tools.adb:
        raise RuntimeError("adb not on PATH; install Android platform-tools.")

    client = AdbClient(tools.adb)
    pool = DevicePool(client=client)
    audit = AuditLog(settings.audit_db)
    settings.ensure_dirs()

    api = FastAPI(title="Android-Crack API", version=__version__)

    @api.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @api.get("/devices", response_model=list[DeviceModel])
    async def list_devices() -> list[DeviceModel]:
        async with audit.scope("api.devices.list", None, {}):
            await pool.refresh()
            return [DeviceModel(**d.__dict__) for d in pool.devices]

    @api.get("/devices/{serial}/info")
    async def device_info(serial: str) -> dict[str, Any]:
        async with audit.scope("api.devices.info", serial, {}):
            info = await cap_info.collect_info(client, serial)
            return info.__dict__

    @api.get("/devices/{serial}/battery")
    async def device_battery(serial: str) -> dict[str, str]:
        async with audit.scope("api.devices.battery", serial, {}):
            return await cap_info.battery(client, serial)

    @api.get("/devices/{serial}/apps")
    async def device_apps(
        serial: str,
        kind: Literal["all", "third_party", "system"] = "third_party",
    ) -> list[dict[str, str]]:
        async with audit.scope("api.apps.list", serial, {"kind": kind}):
            packages = await cap_apps.list_packages(client, serial, kind)
            return [{"name": p.name} for p in packages]

    @api.post("/devices/{serial}/screenshot", response_model=ScreenshotResponse)
    async def device_screenshot(serial: str) -> ScreenshotResponse:
        async with audit.scope("api.media.screenshot", serial, {}):
            local = await cap_media.screenshot(client, serial, settings.captures_dir)
            return ScreenshotResponse(path=str(local))

    @api.get("/devices/{serial}/wifi/saved")
    async def device_wifi_saved(serial: str) -> list[str]:
        async with audit.scope("api.wifi.saved", serial, {}):
            return await cap_wifi.saved_networks(client, serial)

    @api.get("/devices/{serial}/root")
    async def device_root(serial: str) -> dict[str, Any]:
        async with audit.scope("api.diag.root", serial, {}):
            report = await cap_diag.root_check(client, serial)
            return {
                "properties": report.properties,
                "score": report.score,
                "verdict": report.verdict,
                "reasons": report.reasons,
            }

    @api.post("/devices/{serial}/exports/{source}")
    async def device_export(
        serial: str,
        source: Literal["sms", "contacts", "calls"],
    ) -> dict[str, str]:
        async with audit.scope(f"api.export.{source}", serial, {}):
            try:
                local = await cap_exports.dump_source(
                    client, serial, source, settings.downloads_dir
                )
            except RuntimeError as e:
                raise HTTPException(status_code=500, detail=str(e)) from e
            return {"path": str(local)}

    @api.get("/audit/tail")
    async def audit_tail(limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise HTTPException(status_code=400, detail="limit must be 1..1000")
        return audit.tail(limit)

    return api


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    import uvicorn

    uvicorn.run(
        "android_crack.api.server:create_app",
        host=host,
        port=port,
        factory=True,
    )
