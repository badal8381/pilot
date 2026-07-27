from __future__ import annotations

from pathlib import Path

import pytest

from admin.backend.internal.session import Session, issue_token
from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.core.bench.audit_log import AuditLog


def _bench(tmp_path: Path, password: str = "secret", jwt_secret: str | None = None) -> Bench:
    toml_path = tmp_path / "bench.toml"
    toml_path.write_text(BenchConfig.from_flat(tmp_path.name, {"admin_password": password}).dumps())
    if jwt_secret is not None:
        config = BenchConfig.from_file(toml_path)
        config.admin.jwt_secret = jwt_secret
        config.write(toml_path)
    return Bench(BenchConfig.from_file(toml_path), tmp_path)


def test_issue_session_token_is_verifiable_and_audited(tmp_path: Path) -> None:
    session = Session(_bench(tmp_path))
    token, jti = session.issue_session_token(via="password")

    claims = session.verify_token(token)
    assert claims["jti"] == jti
    assert claims["scope"] == "bench"

    entries = AuditLog(session.bench).entries(entry_type="session")
    assert len(entries) == 1
    assert entries[0]["event"] == "issued"
    assert entries[0]["jti"] == jti
    assert entries[0]["via"] == "password"


def test_ensure_jwt_secret_generates_and_persists(tmp_path: Path) -> None:
    bench = _bench(tmp_path)
    assert not bench.config.admin.jwt_secret

    secret = Session(bench).ensure_jwt_secret()
    assert secret
    assert BenchConfig.from_file(tmp_path / "bench.toml").admin.jwt_secret == secret

    reloaded = Bench(BenchConfig.from_file(tmp_path / "bench.toml"), tmp_path)
    assert Session(reloaded).ensure_jwt_secret() == secret


def test_verify_token_without_secret_returns_none(tmp_path: Path) -> None:
    assert Session(_bench(tmp_path)).verify_token("anything") is None


def test_verify_token_rejects_foreign_secret(tmp_path: Path) -> None:
    session = Session(_bench(tmp_path, jwt_secret="k3y"))
    assert session.verify_token(issue_token("other-secret", jti="x")) is None


def test_issue_site_token_is_scoped(tmp_path: Path) -> None:
    session = Session(_bench(tmp_path))
    claims = session.verify_token(session.issue_site_token("a.com"))
    assert claims["scope"] == "site"
    assert claims["site"] == "a.com"


def test_issue_login_token_carries_jti(tmp_path: Path) -> None:
    session = Session(_bench(tmp_path))
    assert session.verify_token(session.issue_login_token())["jti"]


def test_revoke_token_not_implemented(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError):
        Session(_bench(tmp_path)).revoke_token("token")
