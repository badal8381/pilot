"""Tests for StorageProvider's disk usage breakdown."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from pilot.config import BenchConfig
from pilot.core.database.base import BinlogStatus, QueryResult


def _write_bench(bench_root: Path, db_type: str = "mariadb") -> None:
    bench_root.mkdir(parents=True, exist_ok=True)
    (bench_root / "bench.toml").write_text(
        BenchConfig.from_flat(bench_root.name, {"db_type": db_type}).dumps()
    )


def _make_app(bench_root: Path, name: str, content: bytes = b"x" * 1024) -> None:
    app_dir = bench_root / "apps" / name
    app_dir.mkdir(parents=True)
    (app_dir / ".git").mkdir()
    (app_dir / "payload.bin").write_bytes(content)


def _make_site(bench_root: Path, name: str, db_name: str, content: bytes = b"x" * 2048) -> None:
    site_dir = bench_root / "sites" / name
    site_dir.mkdir(parents=True)
    (site_dir / "site_config.json").write_text(f'{{"db_name": "{db_name}"}}')
    (site_dir / "payload.bin").write_bytes(content)


def test_bench_breakdown_sums_apps_sites_and_logs(tmp_path: Path) -> None:
    from admin.backend.providers.storage import StorageProvider

    _write_bench(tmp_path)
    _make_app(tmp_path, "frappe", b"a" * 4096)
    _make_site(tmp_path, "site1.local", "site1_db", b"b" * 8192)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "web.log").write_bytes(b"c" * 512)

    breakdown = StorageProvider(tmp_path)._bench_breakdown()

    assert [entry.name for entry in breakdown.apps] == ["frappe"]
    assert [entry.name for entry in breakdown.sites] == ["site1.local"]
    assert breakdown.apps_bytes > 0
    assert breakdown.sites_bytes > 0
    assert breakdown.logs_bytes > 0
    assert breakdown.used_bytes == (breakdown.apps_bytes + breakdown.sites_bytes + breakdown.logs_bytes)


def test_mariadb_breakdown_shapes_schemas_and_reconciles_core(tmp_path: Path) -> None:
    from admin.backend.providers.storage import DatabaseBreakdown, DatabaseRow, StorageProvider

    _write_bench(tmp_path)
    _make_site(tmp_path, "site1.local", "site1_db")

    db = Mock()
    db.execute.return_value = QueryResult(
        columns=["table_schema", "bytes"],
        rows=[["site1_db", 500], ["mysql", 100]],
        duration_ms=1.0,
    )
    db.get_binlog_status.return_value = BinlogStatus(enabled=True, file_count=1, size_bytes=50)

    with (
        patch("admin.backend.providers.storage.make_database", return_value=db),
        patch("admin.backend.providers.storage.directory_size_bytes", return_value=1000),
    ):
        breakdown = StorageProvider(tmp_path)._mariadb_breakdown()

    assert breakdown == DatabaseBreakdown(
        engine="mariadb",
        supported=True,
        used_bytes=1000,
        binlog_bytes=50,
        core_bytes=350,  # 1000 - 50 - (500 + 100)
        databases=[
            DatabaseRow(schema="site1_db", site="site1.local", system=False, bytes=500),
            DatabaseRow(schema="mysql", site=None, system=True, bytes=100),
        ],
    )


def test_sqlite_engine_is_not_supported(tmp_path: Path) -> None:
    from admin.backend.providers.storage import DatabaseBreakdown, StorageProvider

    _write_bench(tmp_path, db_type="sqlite")

    breakdown = StorageProvider(tmp_path)._database_breakdown()

    assert breakdown == DatabaseBreakdown(
        engine="sqlite", supported=False, used_bytes=0, binlog_bytes=0, core_bytes=0
    )
