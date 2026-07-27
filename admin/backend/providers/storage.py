from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.core.database import make_database, site_database_name

_SYSTEM_SCHEMAS = {"mysql", "performance_schema", "information_schema", "sys"}

_SCHEMA_SIZE_QUERY = (
    "SELECT table_schema, COALESCE(SUM(data_length + index_length), 0) "
    "FROM information_schema.TABLES GROUP BY table_schema"
)
_PG_DATABASE_SIZE_QUERY = (
    "SELECT datname, pg_database_size(datname) FROM pg_database WHERE datistemplate = false"
)


@lru_cache(maxsize=256)
def directory_size_bytes(path: str) -> int:
    try:
        result = subprocess.run(["du", "-sb", path], capture_output=True, timeout=10)
        return int(result.stdout.split()[0]) if result.returncode == 0 else 0
    except Exception:
        return 0


class StorageProvider:
    """Disk usage breakdown for a bench's database engine and bench directories."""

    def __init__(self, bench_root: Path) -> None:
        self._bench_root = bench_root
        self._config = BenchConfig.read(bench_root, validate=False)
        self._bench = Bench(self._config, bench_root)

    def get_breakdown(self) -> dict:
        return {
            "database": self._database_breakdown(),
            "bench": self._bench_breakdown(),
        }

    def _database_breakdown(self) -> dict:
        engine = self._config.db_type
        if engine == "mariadb":
            return self._mariadb_breakdown()
        if engine == "postgres":
            return self._postgres_breakdown()
        return {"engine": engine, "supported": False, "used_bytes": 0, "databases": []}

    def _mariadb_breakdown(self) -> dict:
        from pilot.managers.database.mariadb import MariaDBManager

        data_dir = MariaDBManager(self._config.mariadb).data_dir
        total_bytes = directory_size_bytes(str(data_dir))
        database = make_database(self._config)
        databases = self._schema_sizes(database, _SCHEMA_SIZE_QUERY)
        binlog_bytes = database.get_binlog_status().size_bytes
        schema_bytes = sum(entry["bytes"] for entry in databases)
        core_bytes = max(total_bytes - binlog_bytes - schema_bytes, 0)
        return {
            "engine": "mariadb",
            "supported": True,
            "used_bytes": total_bytes,
            "binlog_bytes": binlog_bytes,
            "core_bytes": core_bytes,
            "databases": databases,
        }

    def _postgres_breakdown(self) -> dict:
        database = make_database(self._config)
        databases = self._schema_sizes(database, _PG_DATABASE_SIZE_QUERY)
        used_bytes = sum(entry["bytes"] for entry in databases)
        return {
            "engine": "postgres",
            "supported": True,
            "used_bytes": used_bytes,
            "binlog_bytes": 0,
            "core_bytes": 0,
            "databases": databases,
        }

    def _schema_sizes(self, database, query: str) -> list[dict]:
        site_by_db = self._site_by_database_name()
        result = database.execute(query)
        return [
            {
                "schema": row[0],
                "site": site_by_db.get(row[0]),
                "system": row[0] in _SYSTEM_SCHEMAS,
                "bytes": int(row[1]),
            }
            for row in result.rows
            if row[0] is not None
        ]

    def _site_by_database_name(self) -> dict[str, str]:
        mapping = {}
        for site in self._bench.sites():
            try:
                db_name = site_database_name(self._bench_root, site.config.name)
            except (FileNotFoundError, ValueError):
                continue
            if db_name:
                mapping[db_name] = site.config.name
        return mapping

    def _bench_breakdown(self) -> dict:
        apps = [
            {"name": app.config.name, "bytes": directory_size_bytes(str(app.path))}
            for app in self._bench.apps()
        ]
        sites = [
            {"name": site.config.name, "bytes": directory_size_bytes(str(site.path))}
            for site in self._bench.sites()
        ]
        logs_bytes = directory_size_bytes(str(self._bench.logs_path))
        apps_bytes = sum(entry["bytes"] for entry in apps)
        sites_bytes = sum(entry["bytes"] for entry in sites)
        return {
            "used_bytes": apps_bytes + sites_bytes + logs_bytes,
            "apps": apps,
            "apps_bytes": apps_bytes,
            "sites": sites,
            "sites_bytes": sites_bytes,
            "logs_bytes": logs_bytes,
        }
