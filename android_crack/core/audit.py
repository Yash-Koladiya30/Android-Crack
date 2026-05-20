"""SQLite-backed audit log of capability invocations.

Used at the CLI layer (and any other consumer) to record what was run,
against which serial, by whom (operator + host), how long it took, and
the exit code. The full stdout is NOT stored — only a sha256 digest of
it, so the trail proves provenance without bloating the database.

This is a forensic / accountability tool, not a debug log.
"""

from __future__ import annotations

import asyncio
import getpass
import hashlib
import json
import socket
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterator


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          REAL    NOT NULL,
    operator    TEXT    NOT NULL,
    host        TEXT    NOT NULL,
    capability  TEXT    NOT NULL,
    serial      TEXT,
    args_json   TEXT,
    exit_code   INTEGER NOT NULL,
    duration_ms REAL    NOT NULL,
    stdout_sha  TEXT,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_cap ON events(capability);
CREATE INDEX IF NOT EXISTS idx_events_serial ON events(serial);
"""


class AuditLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = asyncio.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path, isolation_level=None)
        try:
            yield conn
        finally:
            conn.close()

    def record(
        self,
        *,
        capability: str,
        serial: str | None,
        args: dict[str, Any],
        exit_code: int,
        duration_ms: float,
        stdout: str = "",
        error: str | None = None,
    ) -> int:
        digest = (
            hashlib.sha256(stdout.encode("utf-8", "replace")).hexdigest()
            if stdout
            else None
        )
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO events("
                "ts, operator, host, capability, serial, args_json, "
                "exit_code, duration_ms, stdout_sha, error"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    getpass.getuser(),
                    socket.gethostname(),
                    capability,
                    serial,
                    json.dumps(args, default=str),
                    exit_code,
                    duration_ms,
                    digest,
                    error,
                ),
            )
            return int(cur.lastrowid or 0)

    def tail(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT id, ts, operator, host, capability, serial, args_json, "
                "exit_code, duration_ms, stdout_sha, error "
                "FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": row[0],
                    "ts": row[1],
                    "operator": row[2],
                    "host": row[3],
                    "capability": row[4],
                    "serial": row[5],
                    "args": json.loads(row[6]) if row[6] else None,
                    "exit_code": row[7],
                    "duration_ms": row[8],
                    "stdout_sha": row[9],
                    "error": row[10],
                }
            )
        return out

    def clear(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM events")
            return cur.rowcount

    @asynccontextmanager
    async def scope(
        self,
        capability: str,
        serial: str | None,
        args: dict[str, Any],
    ) -> AsyncIterator["AuditScope"]:
        scope = AuditScope(capability=capability, serial=serial, args=args)
        scope._started = time.perf_counter()
        try:
            yield scope
        except BaseException as exc:
            scope.error = type(exc).__name__ + ": " + str(exc)
            scope.exit_code = 1
            self.record(
                capability=capability,
                serial=serial,
                args=args,
                exit_code=scope.exit_code,
                duration_ms=(time.perf_counter() - scope._started) * 1000.0,
                stdout=scope.stdout,
                error=scope.error,
            )
            raise
        self.record(
            capability=capability,
            serial=serial,
            args=args,
            exit_code=scope.exit_code,
            duration_ms=(time.perf_counter() - scope._started) * 1000.0,
            stdout=scope.stdout,
            error=scope.error,
        )


class AuditScope:
    __slots__ = ("capability", "serial", "args", "exit_code", "stdout", "error", "_started")

    def __init__(
        self,
        *,
        capability: str,
        serial: str | None,
        args: dict[str, Any],
    ) -> None:
        self.capability = capability
        self.serial = serial
        self.args = args
        self.exit_code: int = 0
        self.stdout: str = ""
        self.error: str | None = None
        self._started: float = 0.0
