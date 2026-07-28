from dataclasses import dataclass
from pathlib import Path


def monitor_log_dir() -> Path:
    """Monitor logs live beside the install, not in root-owned /var/log."""
    from pilot.utils import cli_root

    return cli_root() / "system" / "monitor"


def system_log_path() -> Path:
    return monitor_log_dir() / "bench-system-stats.log"


def db_log_path() -> Path:
    return monitor_log_dir() / "bench-db-stats.log"


def slow_query_log_path() -> Path:
    return monitor_log_dir() / "bench-slow-queries.json"


@dataclass
class MonitorConfig:
    log_path: Path | None = None  # set by `bench setup production`

    @classmethod
    def from_dict(cls, data: dict) -> "MonitorConfig":
        return cls(log_path=Path(data["log_path"]) if "log_path" in data else None)

    @staticmethod
    def default_log_path(bench_name: str) -> Path:
        return monitor_log_dir() / f"{bench_name}-stats.log"
