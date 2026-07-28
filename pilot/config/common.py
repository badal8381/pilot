from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

from pilot.config.letsencrypt import LetsEncryptConfig
from pilot.config.mariadb import MariaDBConfig
from pilot.config.monitor import monitor_log_dir
from pilot.config.postgres import PostgresConfig
from pilot.internal.atomic_file import atomic_write_private_text
from pilot.internal.toml import ConfigDict, Toml

FILENAME = "common_config.toml"


@dataclass
class CommonConfig:
    """Settings shared by every bench under one benches directory: one MariaDB
    server, one Postgres server, one ACME account, one trusted admin JWKS
    issuer, one host-wide system/DB monitor. Stored once at
    ``common_config.toml`` next to the bench folders. BenchConfig is the only
    reader/writer; other code reaches these values through a bench's own
    config instead."""

    mariadb: MariaDBConfig = field(default_factory=MariaDBConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    letsencrypt: LetsEncryptConfig = field(default_factory=LetsEncryptConfig)
    jwks_url: str = ""
    jwks_audience: str = ""
    system_log_path: Path = field(default_factory=lambda: monitor_log_dir() / "bench-system-stats.log")
    db_log_path: Path = field(default_factory=lambda: monitor_log_dir() / "bench-db-stats.log")
    slow_query_log_path: Path = field(
        default_factory=lambda: monitor_log_dir() / "bench-slow-queries.json"
    )

    @classmethod
    def path(cls, benches_root: Path) -> Path:
        return Path(benches_root) / FILENAME

    @classmethod
    def read(cls, benches_root: Path) -> "CommonConfig":
        path = cls.path(benches_root)
        if not path.exists():
            return cls()
        return cls.from_raw_dict(Toml.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def from_raw_dict(cls, data: dict) -> "CommonConfig":
        """Build from a parsed TOML dict shaped like common_config.toml (or a
        bench.toml that still carries these tables pre-migration)."""
        admin = data.get("admin", {})
        monitor = data.get("monitor", {})
        log_dir = monitor_log_dir()
        return cls(
            mariadb=MariaDBConfig(**_known_fields(MariaDBConfig, data.get("mariadb", {}))),
            postgres=PostgresConfig(**_known_fields(PostgresConfig, data.get("postgres", {}))),
            letsencrypt=LetsEncryptConfig.from_dict(data.get("letsencrypt", {})),
            jwks_url=admin.get("jwks_url", ""),
            jwks_audience=admin.get("jwks_audience", ""),
            system_log_path=Path(monitor.get("system_log_path", log_dir / "bench-system-stats.log")),
            db_log_path=Path(monitor.get("db_log_path", log_dir / "bench-db-stats.log")),
            slow_query_log_path=Path(
                monitor.get("slow_query_log_path", log_dir / "bench-slow-queries.json")
            ),
        )

    def write(self, benches_root: Path) -> None:
        atomic_write_private_text(self.path(benches_root), Toml.dumps(self._to_toml_dict()))

    def _to_toml_dict(self) -> ConfigDict:
        data: ConfigDict = {
            "mariadb": {
                "host": self.mariadb.host,
                "port": self.mariadb.port,
                "root_password": self.mariadb.root_password,
                "admin_user": self.mariadb.admin_user,
                "socket_path": self.mariadb.socket_path,
                "existing": self.mariadb.existing,
            },
            "postgres": {
                "host": self.postgres.host,
                "port": self.postgres.port,
                "root_password": self.postgres.root_password,
                "admin_user": self.postgres.admin_user,
                "existing": self.postgres.existing,
            },
            "letsencrypt": {
                "email": self.letsencrypt.email,
                "webroot_path": str(self.letsencrypt.webroot_path),
            },
            "monitor": {
                "system_log_path": str(self.system_log_path),
                "db_log_path": str(self.db_log_path),
                "slow_query_log_path": str(self.slow_query_log_path),
            },
        }
        if self.jwks_url:
            data["admin"] = {"jwks_url": self.jwks_url, "jwks_audience": self.jwks_audience}
        return data


def _known_fields(dataclass_type: type, data: dict) -> dict:
    known = {f.name for f in fields(dataclass_type)}
    return {key: value for key, value in data.items() if key in known}
