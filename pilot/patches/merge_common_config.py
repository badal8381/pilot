from __future__ import annotations

from pathlib import Path

PATCH_NAME = Path(__file__).stem


def run(benches_root: Path) -> None:
    """Move mariadb/postgres/letsencrypt/jwks_* from each bench.toml into one
    shared common_config.toml, then trim those fields from every bench.toml."""
    from pilot.config.common import CommonConfig
    from pilot.internal.patch_state import is_applied, mark_applied

    bench_dirs = [
        entry
        for entry in sorted(benches_root.iterdir())
        if entry.is_dir() and (entry / "bench.toml").exists() and not is_applied(entry, PATCH_NAME)
    ]
    if not bench_dirs:
        return

    if not CommonConfig.path(benches_root).exists():
        _seed_common_config(benches_root, bench_dirs)

    for bench_dir in bench_dirs:
        _trim_bench_toml(bench_dir)
        mark_applied(bench_dir, PATCH_NAME)


def _seed_common_config(benches_root: Path, bench_dirs: list[Path]) -> None:
    from pilot.config import BenchConfig
    from pilot.config.common import CommonConfig

    for bench_dir in bench_dirs:
        raw = BenchConfig.read_raw(bench_dir)
        admin = raw.get("admin", {})
        has_shared_fields = any(key in raw for key in ("mariadb", "postgres", "letsencrypt")) or (
            "jwks_url" in admin
        )
        if not has_shared_fields:
            continue
        CommonConfig.from_raw_dict(raw).write(benches_root)
        print(f"common_config.toml seeded from '{bench_dir.name}'.")
        return


def _trim_bench_toml(bench_dir: Path) -> None:
    from pilot.config import BenchConfig

    raw = BenchConfig.read_raw(bench_dir)
    changed = False
    for key in ("mariadb", "postgres", "letsencrypt"):
        if raw.pop(key, None) is not None:
            changed = True
    admin = raw.get("admin")
    if admin:
        for key in ("jwks_url", "jwks_audience"):
            if admin.pop(key, None) is not None:
                changed = True
    if changed:
        BenchConfig.write_raw(bench_dir, raw)


if __name__ == "__main__":
    from pilot.utils import benches_dir

    run(benches_dir())
