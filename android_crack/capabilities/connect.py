from __future__ import annotations

from android_crack.core.adb_client import AdbClient, AdbResult


async def connect_tcp(client: AdbClient, host: str, port: int = 5555) -> AdbResult:
    """Connect to a device exposed via `adb tcpip` on the given port."""
    return await client.run(["connect", f"{host}:{port}"])


async def pair_wireless(client: AdbClient, host: str, port: int, code: str) -> AdbResult:
    """Android 11+ wireless debug pairing.

    Host shows port + 6-digit code under Developer Options →
    Wireless debugging → Pair device with pairing code.
    """
    proc = await client.run(["pair", f"{host}:{port}", code])
    return proc


async def disconnect(client: AdbClient, host: str | None = None) -> AdbResult:
    args = ["disconnect"]
    if host:
        args.append(host)
    return await client.run(args)


async def kill_server(client: AdbClient) -> AdbResult:
    return await client.run(["kill-server"])


async def start_server(client: AdbClient) -> AdbResult:
    return await client.run(["start-server"])
