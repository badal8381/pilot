"""Bench-wide append-only audit log, sharded by ISO week."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pilot.utils import open_private

_FILE_RE = re.compile(r"^audit_\d{4}_\d{2}\.jsonl$")


@dataclass
class AuditEntry:
    """Shape of one audit record. Every call site passes only the fields relevant to
    its event, so everything but `type`/`logged_at` is optional - this is a type
    contract for the TS generator, not a struct `append()` requires callers to build."""

    type: str
    logged_at: str
    event: str | None = None
    site: str | None = None
    app: str | None = None
    status: str | None = None
    ip: str | None = None
    actor: str | None = None
    actor_jti: str | None = None
    jti: str | None = None
    command: str | None = None
    task_id: str | None = None
    provider: str | None = None
    username: str | None = None
    fingerprint: str | None = None
    patch: str | None = None
    operation: str | None = None
    device: str | None = None
    via: str | None = None
    scope: str | None = None
    timestamp: str | None = None
    finished_at: str | None = None
    with_files: bool | None = None
    file: str | None = None
    name: str | None = None

# Extra fields merged into every audit entry. The admin backend registers a provider that
# reads the current request (IP + actor); the CLI/worker leave the empty default.
def _context_provider() -> dict:
    return {}


def set_audit_context_provider(provider: Callable[[], dict]) -> None:
    global _context_provider
    _context_provider = provider


def audit_context() -> dict:
    """Registered context fields, or empty if none/failing. Never raises."""
    try:
        return _context_provider() or {}
    except Exception:
        return {}


class AuditLog:
    def __init__(self, bench) -> None:
        self._dir = bench.logs_path

    def append(self, entry_type: str, entry: dict) -> None:
        record = {"type": entry_type, "logged_at": self._now(), **entry}
        self._dir.mkdir(parents=True, exist_ok=True)
        with open_private(self._current_file(), "a") as handle:
            handle.write(json.dumps(record) + "\n")

    def entries(self, entry_type=None, site=None, status=None, jti=None, limit=None) -> list[dict]:
        """Return matching records newest first across weekly files."""
        matched = []
        for record in self._read_newest_first():
            if self._matches(record, entry_type, site, status, jti):
                matched.append(record)
                if limit is not None and len(matched) >= limit:
                    break
        return matched

    def _current_file(self):
        year, week, _ = datetime.now(UTC).isocalendar()
        return self._dir / f"audit_{year}_{week:02d}.jsonl"

    def _weekly_files(self) -> list:
        if not self._dir.is_dir():
            return []
        files = [p for p in self._dir.iterdir() if _FILE_RE.match(p.name)]
        return sorted(files, key=lambda p: p.name, reverse=True)  # zero-padded, so name sort == time sort

    def _read_newest_first(self):
        for path in self._weekly_files():
            for line in self._reversed_lines(path):
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _reversed_lines(path, chunk_size: int = 65536):
        """Yield non-empty lines newest first without loading the whole file."""
        with path.open("rb") as handle:
            handle.seek(0, 2)
            pointer = handle.tell()
            tail = b""
            while pointer > 0:
                step = min(chunk_size, pointer)
                pointer -= step
                handle.seek(pointer)
                lines = (handle.read(step) + tail).split(b"\n")
                tail = lines.pop(0)  # may be a partial line completed by the next (earlier) chunk
                for line in reversed(lines):
                    if line:
                        yield line.decode()
            if tail:
                yield tail.decode()

    @staticmethod
    def _matches(record: dict, entry_type, site, status, jti=None) -> bool:
        return (
            (entry_type is None or record.get("type") == entry_type)
            and (site is None or record.get("site") == site)
            and (status is None or record.get("status") == status)
            and (jti is None or jti in (record.get("jti"), record.get("actor_jti")))
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()
