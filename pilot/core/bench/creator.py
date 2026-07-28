from __future__ import annotations

import secrets
import socket
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pilot.exceptions import BenchAlreadyExistsError
from pilot.utils import iter_sibling_benches

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class BenchCreator:
    """Creates a bench. Host-shared settings (MariaDB/Postgres server, ACME
    email, admin JWKS trust) live in common_config.toml and are merged in
    automatically by BenchConfig - only a first-ever database needs seeding
    here."""

    def __init__(
        self,
        target_directory: Path,
        name: str,
        process_manager: str = "",
        admin_domain: str = "",
        admin_tls: bool | None = None,
        db_type: str = "mariadb",
    ) -> None:
        self.target_directory = target_directory
        self.name = name
        self.process_manager = process_manager
        self.admin_domain = admin_domain
        self.admin_tls = admin_tls
        self.db_type = db_type

    def run(self, on_progress: Callable[[str], None] = lambda message: None) -> "Bench":
        from pilot.config import BenchConfig
        from pilot.core.bench import Bench

        bench_toml = self.target_directory / "bench.toml"
        if bench_toml.exists():
            raise BenchAlreadyExistsError(f"Bench '{self.name}' already exists.")

        benches_dir = self.target_directory.parent
        if not benches_dir.exists():
            on_progress(f"Creating benches directory at {benches_dir}")
            benches_dir.mkdir(parents=True, exist_ok=True)

        on_progress(f"Creating bench directory: {self.target_directory}")
        self.target_directory.mkdir(parents=True, exist_ok=True)

        offset = self._pick_port_offset(self.target_directory)
        on_progress("Writing bench.toml")
        settings = self._initial_settings()

        BenchConfig.write_flat(bench_toml, self.name, settings, port_offset=offset)

        admin_port = BenchConfig.default_ports()["admin.port"] + offset
        on_progress(f"\nBench '{self.name}' created at {self.target_directory}")
        on_progress("\nNext step:")
        on_progress("  bench start")
        on_progress(f"  Then open http://localhost:{admin_port} - the setup wizard takes it from there.")

        return Bench(self.target_directory)

    def _initial_settings(self) -> dict:
        settings = {
            "admin_enabled": True,
            "admin_domain": self.admin_domain,
            # admin.tls is a per-bench choice, not inherited from siblings.
            "admin_tls": bool(self.admin_tls),
            "db_type": self.db_type,
        }
        self._add_database_settings(settings)
        if self.process_manager:
            settings["production_process_manager"] = self.process_manager
        return settings

    def _add_database_settings(self, settings: dict) -> None:
        """Pick a fresh port/password only the first time this host
        provisions the server; later benches inherit them automatically
        through BenchConfig's merge with common_config.toml."""
        from pilot.config import BenchConfig

        defaults = BenchConfig.default(benches_root=self.target_directory.parent)
        if self.db_type == "mariadb" and not defaults.mariadb.root_password:
            settings["mariadb_port"] = self._pick_mariadb_port()
            settings["mariadb_password"] = secrets.token_hex(nbytes=8)
        if self.db_type == "postgres" and not defaults.postgres.root_password:
            settings["postgres_port"] = self._pick_postgres_port()
            settings["postgres_password"] = secrets.token_hex(nbytes=8)

    def _pick_mariadb_port(self) -> int:
        """Pick the first free MariaDB port for the first bench on this host."""
        from pilot.config import MariaDBConfig
        from pilot.managers.platform import is_macos

        port = MariaDBConfig().port
        if is_macos():
            return port
        while self._port_is_live(port):
            port += 1
        return port

    def _pick_postgres_port(self) -> int:
        """Pick the first free PostgreSQL port for the first bench on this host."""
        from pilot.config import PostgresConfig
        from pilot.managers.platform import is_macos

        port = PostgresConfig().port
        if is_macos():
            return port
        while self._port_is_live(port):
            port += 1
        return port

    def _pick_port_offset(self, bench_path: Path) -> int:
        """Pick the first base-port offset unused by configs or live processes."""
        from pilot.config import BenchConfig

        bases = BenchConfig.default_ports()
        base_http_port = bases["http_port"]
        used = set()

        for _, config in iter_sibling_benches(bench_path):
            try:
                used.add(config.http_port - base_http_port)
            except Exception:
                continue

        admin_internal_port = bases["admin.port"] + 1

        offset = 0
        while (
            offset in used
            or any(self._port_is_live(base + offset) for base in bases.values())
            or self._port_is_live(admin_internal_port + offset)
        ):
            offset += 1
        return offset

    @staticmethod
    def _port_is_live(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            return False
