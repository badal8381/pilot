from __future__ import annotations

import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from pilot.exceptions import BenchError
from pilot.utils import make_private_directory, open_private

UPLOADS_DIR = "backups-uploads"

_UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{16}$")
_CLAIM_MARKER = ".claimed"

# kind -> (stored stem, accepted suffixes, longest first)
_KINDS = {
    "database": ("database", (".sql.gz", ".sql")),
    "public_files": ("files", (".tar.gz", ".tgz", ".tar")),
    "private_files": ("private-files", (".tar.gz", ".tgz", ".tar")),
}


@dataclass(frozen=True)
class BackupUpload:
    upload_id: str
    directory: Path
    files: dict[str, str]

    @property
    def db_file(self) -> str:
        return self.files["database"]


class BackupUploads:
    """Backup archives uploaded through the admin, held under the bench until a
    restore consumes them. The database is required; file archives are optional."""

    def __init__(self, bench_root: Path) -> None:
        self.root = bench_root / UPLOADS_DIR

    def save(self, parts: dict[str, tuple[str, IO[bytes]]]) -> BackupUpload:
        """`parts` maps kind to (original filename, stream)."""
        if "database" not in parts:
            raise BenchError("A database backup file is required.")
        unknown = set(parts) - set(_KINDS)
        if unknown:
            raise BenchError(f"Unknown backup file kind: {', '.join(sorted(unknown))}.")

        upload_id = secrets.token_hex(8)
        directory = self.root / upload_id
        make_private_directory(directory, parents=True)
        files: dict[str, str] = {}
        try:
            for kind, (filename, stream) in parts.items():
                stem, allowed = _KINDS[kind]
                target = directory / f"{stem}{_extension(filename, allowed)}"
                with open_private(target, "wb") as out:
                    shutil.copyfileobj(stream, out)
                files[kind] = str(target)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        return BackupUpload(upload_id, directory, files)

    def get(self, upload_id: str) -> BackupUpload:
        if not _UPLOAD_ID_RE.match(upload_id or ""):
            raise BenchError("Invalid backup upload id.")
        directory = self.root / upload_id
        if not directory.is_dir():
            raise BenchError("Backup upload not found. Upload the files again.")
        if (directory / _CLAIM_MARKER).exists():
            raise BenchError("This backup upload is already being restored. Upload the files again.")
        files = {}
        for kind, (stem, _allowed) in _KINDS.items():
            match = next((p for p in directory.iterdir() if p.name.startswith(stem + ".")), None)
            if match:
                files[kind] = str(match)
        if "database" not in files:
            raise BenchError("Backup upload is missing its database file. Upload the files again.")
        return BackupUpload(upload_id, directory, files)

    def claim(self, upload_id: str) -> BackupUpload:
        """Reserve the upload for one restore: a task deletes it when done, so a
        second restore must not be pointed at the same archives."""
        upload = self.get(upload_id)
        (upload.directory / _CLAIM_MARKER).touch()
        return upload

    def release(self, upload_id: str) -> None:
        """Undo a claim whose restore never got queued."""
        if _UPLOAD_ID_RE.match(upload_id or ""):
            (self.root / upload_id / _CLAIM_MARKER).unlink(missing_ok=True)

    def remove(self, upload_id: str) -> None:
        """Delete an upload. The id is validated, so only a directory under
        backups-uploads can ever be removed - callers cannot aim this elsewhere."""
        if _UPLOAD_ID_RE.match(upload_id or ""):
            shutil.rmtree(self.root / upload_id, ignore_errors=True)


def _extension(filename: str, allowed: tuple[str, ...]) -> str:
    lowered = (filename or "").lower()
    for suffix in allowed:
        if lowered.endswith(suffix):
            return suffix
    raise BenchError(f"'{filename}' must end with one of: {', '.join(allowed)}.")
