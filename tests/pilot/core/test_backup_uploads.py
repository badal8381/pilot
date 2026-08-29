"""Uploaded backup archives are staged privately until a restore consumes them."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pilot.core.site.backup_uploads import BackupUploads
from pilot.exceptions import BenchError


def _part(name: str, content: bytes = b"data"):
    return (name, io.BytesIO(content))


def test_save_stores_each_kind_under_a_fixed_name(tmp_path: Path) -> None:
    upload = BackupUploads(tmp_path).save(
        {
            "database": _part("20240101_000000-site-database.sql.gz", b"db"),
            "public_files": _part("20240101_000000-site-files.tar"),
            "private_files": _part("20240101_000000-site-private-files.tar"),
        }
    )

    assert upload.directory == tmp_path / "backups-uploads" / upload.upload_id
    assert Path(upload.db_file).name == "database.sql.gz"
    assert Path(upload.files["public_files"]).name == "files.tar"
    assert Path(upload.files["private_files"]).name == "private-files.tar"
    assert Path(upload.db_file).read_bytes() == b"db"


def test_save_requires_a_database_and_known_kinds(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)

    with pytest.raises(BenchError, match="database"):
        uploads.save({"public_files": _part("files.tar")})
    with pytest.raises(BenchError, match="Unknown"):
        uploads.save({"database": _part("db.sql.gz"), "logs": _part("x.log")})
    assert not (tmp_path / "backups-uploads").exists() or not any(
        (tmp_path / "backups-uploads").iterdir()
    )


def test_save_rejects_wrong_extensions_and_leaves_nothing_behind(tmp_path: Path) -> None:
    with pytest.raises(BenchError, match="must end with"):
        BackupUploads(tmp_path).save(
            {"database": _part("db.sql.gz"), "public_files": _part("files.zip")}
        )

    assert not any((tmp_path / "backups-uploads").iterdir())


def test_get_returns_the_saved_upload_and_rejects_bad_ids(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql")})

    found = uploads.get(saved.upload_id)

    assert found.files == saved.files
    with pytest.raises(BenchError, match="Invalid"):
        uploads.get("../etc")
    with pytest.raises(BenchError, match="not found"):
        uploads.get("0123456789abcdef")


def test_remove_deletes_the_upload(tmp_path: Path) -> None:
    uploads = BackupUploads(tmp_path)
    saved = uploads.save({"database": _part("db.sql.gz")})

    uploads.remove(saved.upload_id)

    assert not saved.directory.exists()
