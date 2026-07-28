from dataclasses import dataclass, field
from pathlib import Path


def monitor_log_dir() -> Path:
    """Monitor logs live beside the install, not in root-owned /var/log."""
    from pilot.utils import cli_root

    return cli_root() / "system" / "monitor"


@dataclass
class MonitorConfig:
    # system_log_path/db_log_path/slow_query_log_path are host-shared
    # (common_config.toml) - the defaults here only matter for a parse with
    # no common config available (see BenchConfig._validate_serialized).
    system_log_path: Path = field(default_factory=lambda: monitor_log_dir() / "bench-system-stats.log")
    db_log_path: Path = field(default_factory=lambda: monitor_log_dir() / "bench-db-stats.log")
    slow_query_log_path: Path = field(default_factory=lambda: monitor_log_dir() / "bench-slow-queries.json")
    log_path: Path | None = None  # set by `bench setup production`

    @classmethod
    def from_dict(cls, data: dict) -> "MonitorConfig":
        log_dir = monitor_log_dir()
        return cls(
            system_log_path=Path(data.get("system_log_path", log_dir / "bench-system-stats.log")),
            db_log_path=Path(data.get("db_log_path", log_dir / "bench-db-stats.log")),
            slow_query_log_path=Path(data.get("slow_query_log_path", log_dir / "bench-slow-queries.json")),
            log_path=Path(data["log_path"]) if "log_path" in data else None,
        )

    @staticmethod
    def default_log_path(bench_name: str) -> Path:
        return monitor_log_dir() / f"{bench_name}-stats.log"
