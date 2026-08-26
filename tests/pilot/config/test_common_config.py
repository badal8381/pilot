from __future__ import annotations

import threading
from pathlib import Path

from pilot.config.alert_limit import ResourceLimitConfig
from pilot.config.central import CentralConfig
from pilot.config.common import CommonConfig
from pilot.config.datum import DatumConfig
from pilot.config.letsencrypt import LetsEncryptConfig
from pilot.config.mariadb import MariaDBConfig
from pilot.config.postgres import PostgresConfig


def test_path_resolves_next_to_benches_root(tmp_path: Path) -> None:
    assert CommonConfig.path(tmp_path) == tmp_path / "common_config.toml"


def test_read_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert CommonConfig.read(tmp_path) == CommonConfig()


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    config = CommonConfig(
        mariadb=MariaDBConfig(host="db.internal", port=3307, root_password="s3cret", admin_user="root"),
        postgres=PostgresConfig(host="pg.internal", port=5433, root_password="pgsecret"),
        letsencrypt=LetsEncryptConfig(email="ops@example.com"),
        central=CentralConfig(endpoint="https://central.test", auth_token="tok-123"),
        datum=DatumConfig(endpoint="https://datum.internal", token="s3cret"),
        jwks_url="https://issuer.example.com/jwks.json",
        jwks_audience="bench-fleet",
    )
    config.write(tmp_path)
    assert CommonConfig.read(tmp_path) == config


def test_read_ignores_stale_mariadb_instance_keys(tmp_path: Path) -> None:
    """Legacy MariaDB instance keys (from an older Pilot schema) are
    ignored, not rejected, when read back."""
    (tmp_path / "common_config.toml").write_text(
        '[mariadb]\nroot_password = "root"\ninstance = "old-bench"\n'
        'version = "10.6"\ndata_dir = "/var/lib/mysql-old-bench"\n'
    )
    config = CommonConfig.read(tmp_path)
    assert not hasattr(config.mariadb, "instance")
    assert config.mariadb.root_password == "root"


def test_read_ignores_stale_postgres_instance_keys(tmp_path: Path) -> None:
    (tmp_path / "common_config.toml").write_text(
        '[postgres]\nroot_password = "secret"\ninstance = "old-bench"\nversion = "15"\n'
    )
    config = CommonConfig.read(tmp_path)
    assert not hasattr(config.postgres, "instance")
    assert config.postgres.root_password == "secret"


def test_jwks_omitted_from_output_when_unset(tmp_path: Path) -> None:
    CommonConfig().write(tmp_path)
    assert "[admin]" not in CommonConfig.path(tmp_path).read_text()


def test_central_omitted_from_output_when_unset(tmp_path: Path) -> None:
    CommonConfig().write(tmp_path)
    assert "[central]" not in CommonConfig.path(tmp_path).read_text()


def test_datum_omitted_from_output_when_unset(tmp_path: Path) -> None:
    CommonConfig().write(tmp_path)
    assert "[datum]" not in CommonConfig.path(tmp_path).read_text()


def test_smtp_password_is_not_stored_as_plaintext(tmp_path: Path) -> None:
    config = CommonConfig(
        resource_limits=ResourceLimitConfig(
            smtp_server="smtp.test",
            smtp_email="alerts@smtp.test",
            smtp_password="s3cret",
            email_recipients=["ops@example.com"],
        )
    )
    config.write(tmp_path)

    assert "s3cret" not in CommonConfig.path(tmp_path).read_text()
    assert CommonConfig.read(tmp_path).resource_limits.smtp_password == "s3cret"


def test_key_creation_is_covered_by_the_write_lock(tmp_path: Path, monkeypatch) -> None:
    """Two processes racing to save the first SMTP password must not each mint
    their own encryption key: whichever write lands second would then be
    undecryptable under the key the other one left behind. Assert directly
    that write()'s file lock is already held by the time key creation runs,
    rather than relying on timing to expose the race."""
    import fcntl

    from pilot.config import secret_box
    from pilot.internal import atomic_file

    lock_path = atomic_file._lock_path(CommonConfig.path(tmp_path))
    real_load_or_create_key = secret_box._load_or_create_key
    lock_was_held = False

    def _checking_load_or_create_key(benches_root: Path) -> bytes:
        nonlocal lock_was_held
        with open(lock_path) as check:
            try:
                fcntl.flock(check.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(check.fileno(), fcntl.LOCK_UN)
            except OSError:
                lock_was_held = True
        return real_load_or_create_key(benches_root)

    monkeypatch.setattr(secret_box, "_load_or_create_key", _checking_load_or_create_key)

    CommonConfig(
        resource_limits=ResourceLimitConfig(
            smtp_server="smtp.test",
            smtp_email="alerts@smtp.test",
            smtp_password="s3cret",
            email_recipients=["ops@example.com"],
        )
    ).write(tmp_path)

    assert lock_was_held


def test_datum_is_shared_by_every_bench(tmp_path: Path) -> None:
    """Metrics ship to one destination per host, so the config is not per-bench."""
    from pilot.config import BenchConfig

    benches_root = tmp_path / "benches"
    bench_root = benches_root / "main"
    bench_root.mkdir(parents=True)
    (bench_root / "bench.toml").write_text('[bench]\nname = "main"\npython = "3.11"\n')
    CommonConfig(datum=DatumConfig(endpoint="https://datum.internal", token="s3cret")).write(
        benches_root
    )

    config = BenchConfig.read(bench_root)

    assert config.datum.endpoint == "https://datum.internal"
    assert config.datum.is_enabled
