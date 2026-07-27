from __future__ import annotations

import secrets
import time
from pathlib import Path
from types import SimpleNamespace

import jwt as pyjwt
import pytest

from admin.backend.internal.session import Session
from pilot.config import BenchConfig
from pilot.core.bench import Bench


def _session_token(secret: str = "k3y", scope: str = "bench", site: str | None = None, ttl: int = 300) -> str:
    """A token signed with ``secret``, for authenticating a test client."""
    payload = {"sub": "admin", "scope": scope, "exp": int(time.time()) + ttl}
    if site:
        payload["site"] = site
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _login_token(secret: str = "k3y") -> str:
    """A single-use ?sid= sign-in token signed with ``secret``."""
    payload = {
        "sub": "admin",
        "scope": "bench",
        "jti": secrets.token_urlsafe(8),
        "exp": int(time.time()) + 300,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _bench(tmp_path: Path, password: str = "secret") -> Bench:
    toml_path = tmp_path / "bench.toml"
    toml_path.write_text(BenchConfig.from_flat(tmp_path.name, {"admin_password": password}).dumps())
    return _load_bench(tmp_path)


def _load_bench(tmp_path: Path) -> Bench:
    return Bench(BenchConfig.from_file(tmp_path / "bench.toml"), tmp_path)


def _initialized_bench(bench_dir: Path, password: str, jwt_secret: str) -> None:
    bench_dir.mkdir(parents=True, exist_ok=True)
    toml_path = bench_dir / "bench.toml"
    toml_path.write_text(
        BenchConfig.from_flat(bench_dir.name, {"admin_enabled": True, "admin_password": password}).dumps()
    )
    config = BenchConfig.from_file(toml_path)
    config.admin.jwt_secret = jwt_secret
    config.write(toml_path)
    python = bench_dir / "env" / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.touch()


def _client(tmp_path: Path, jwt_secret: str = "k3y"):
    from admin.backend.app import create_app

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", jwt_secret)
    app = create_app(bench_root)
    app.config["TESTING"] = True
    return app.test_client()


def test_valid_jwt_cookie_authenticates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())
    assert client.get("/api/v1/session").get_json() == {
        "authenticated": True,
        "scope": "bench",
    }
    assert client.get("/api/v1/benches").status_code != 401


def test_invalid_jwt_cookie_stays_unauthenticated(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token("wrong-secret"))
    assert client.get("/api/v1/session").get_json() == {"authenticated": False}
    assert client.get("/api/v1/benches").status_code == 401


def test_bootstrap_does_not_report_session_state(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())

    body = client.get("/api/v1/bootstrap").get_json()

    assert body["mode"] == "admin"
    assert "authenticated" not in body


def test_fresh_bench_bootstrap_and_session_are_explicit(tmp_path: Path) -> None:
    from admin.backend.app import create_app

    client = create_app(tmp_path).test_client()

    assert client.get("/api/v1/bootstrap").get_json() == {
        "enabled": True,
        "mode": "setup",
        "name": tmp_path.name,
    }
    assert client.get("/api/v1/session").get_json() == {"authenticated": False}


def test_delete_session_clears_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())

    response = client.delete("/api/v1/session")

    assert response.status_code == 204
    assert response.data == b""
    assert client.get("/api/v1/session").get_json() == {"authenticated": False}


def test_bootstrap_reports_bench_db_type(tmp_path: Path) -> None:
    # The engine is a bench-wide property; the admin reads it from bootstrap to
    # show one bench-level badge instead of a per-site one.
    client = _client(tmp_path)
    assert client.get("/api/v1/bootstrap").get_json()["db_type"] == "mariadb"


def test_bootstrap_reports_sanitized_task_activity(tmp_path: Path) -> None:
    body = _client(tmp_path).get("/api/v1/bootstrap").get_json()

    assert body["task_worker"] == {
        "active": False,
        "desired": "running",
        "status": "not-started",
        "uncertain": False,
    }
    assert "current_task_id" not in body["task_worker"]


def test_bootstrap_reports_postgres_engine(tmp_path: Path) -> None:
    from admin.backend.app import create_app
    bench_root = tmp_path / "benches" / "pg"
    _initialized_bench(bench_root, "secret", "k3y")
    toml_path = bench_root / "bench.toml"
    config = BenchConfig.from_file(toml_path)
    config.db_type = "postgres"
    config.write(toml_path)

    app = create_app(bench_root)
    app.config["TESTING"] = True
    assert app.test_client().get("/api/v1/bootstrap").get_json()["db_type"] == "postgres"


def test_bootstrap_reports_allow_bench_management_default_true(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/v1/bootstrap").get_json()["allow_bench_management"] is True


def test_bootstrap_reports_allow_bench_management_when_disabled(tmp_path: Path) -> None:
    from admin.backend.app import create_app
    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    toml_path = bench_root / "bench.toml"
    config = BenchConfig.from_file(toml_path)
    config.admin.allow_bench_management = False
    config.write(toml_path)

    app = create_app(bench_root)
    app.config["TESTING"] = True
    assert app.test_client().get("/api/v1/bootstrap").get_json()["allow_bench_management"] is False


def test_login_with_sid_sets_httponly_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/v1/session", json={"sid": _login_token()})
    assert resp.status_code == 201
    assert resp.headers["Location"] == "/api/v1/session"
    assert resp.get_json() == {"authenticated": True, "scope": "bench"}
    cookie = next(h for k, h in resp.headers if k == "Set-Cookie" and h.startswith("sid="))
    assert "HttpOnly" in cookie
    assert "Secure" not in cookie
    assert client.get("/api/v1/benches").status_code != 401


def test_password_login_records_session_issued(tmp_path: Path) -> None:
    from pilot.core.bench.audit_log import AuditLog

    client = _client(tmp_path)
    assert client.post("/api/v1/session", json={"password": "secret"}).status_code == 201

    issued = AuditLog(Bench(tmp_path / "benches" / "current")).entries(entry_type="session")
    assert len(issued) == 1
    assert issued[0]["event"] == "issued"
    assert issued[0]["via"] == "password"
    assert issued[0]["jti"]


def test_sid_login_records_redeemed_and_issued(tmp_path: Path) -> None:
    from pilot.core.bench.audit_log import AuditLog

    client = _client(tmp_path)
    assert client.post("/api/v1/session", json={"sid": _login_token()}).status_code == 201

    entries = AuditLog(Bench(tmp_path / "benches" / "current")).entries(entry_type="session")
    assert {e["event"] for e in entries} == {"issued", "login_redeemed"}
    issued = next(e for e in entries if e["event"] == "issued")
    assert issued["via"] == "login_link"


def test_login_cookie_uses_explicit_is_secure_cookie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.application.config["SESSION_COOKIE_SECURE"] = True

    response = client.post("/api/v1/session", json={"sid": _login_token()})

    cookie = next(
        value for key, value in response.headers if key == "Set-Cookie" and value.startswith("sid=")
    )
    assert "Secure" in cookie


def test_setup_session_cookie_uses_explicit_is_secure_cookie(tmp_path: Path) -> None:
    from admin.backend.app import create_app

    app = create_app(tmp_path)
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=True)

    response = app.test_client().put(
        "/api/v1/setup/configuration",
        json={"admin_password": "secret", "mariadb_password": "db-secret"},
    )

    cookie = next(
        value for key, value in response.headers if key == "Set-Cookie" and value.startswith("sid=")
    )
    assert response.status_code == 200
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=Lax" in cookie


def test_is_secure_cookie_requires_tls_or_configured_proxy(monkeypatch) -> None:
    from admin.backend.app import is_secure_cookie

    config = SimpleNamespace(
        production=SimpleNamespace(enabled=True),
        admin=SimpleNamespace(tls=False),
    )
    monkeypatch.setattr(BenchConfig, "read", lambda bench_root: config)
    unused_root = Path("unused")

    monkeypatch.setattr("pilot.core.adapters.domain_provider.DomainRouteProvider.proxy_servers", lambda: [])
    assert is_secure_cookie(unused_root) is False

    monkeypatch.setattr(
        "pilot.core.adapters.domain_provider.DomainRouteProvider.proxy_servers",
        lambda: ["203.0.113.10"],
    )
    assert is_secure_cookie(unused_root) is True

    config.admin.tls = True
    monkeypatch.setattr("pilot.core.adapters.domain_provider.DomainRouteProvider.proxy_servers", lambda: [])
    assert is_secure_cookie(unused_root) is True


def test_login_with_invalid_sid_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    resp = client.post("/api/v1/session", json={"sid": _login_token("wrong-secret")})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_login_token"
    assert client.get("/api/v1/benches").status_code == 401


def test_session_creation_requires_a_json_object(tmp_path: Path) -> None:
    response = _client(tmp_path).post("/api/v1/session", json=["secret"])

    assert response.status_code == 400
    assert response.get_json() == {
        "error": {
            "code": "malformed_request",
            "details": {},
            "message": "Expected a JSON object.",
        }
    }


def test_sid_is_single_use(tmp_path: Path) -> None:
    client = _client(tmp_path)
    sid = _login_token()
    assert client.post("/api/v1/session", json={"sid": sid}).status_code == 201
    assert client.post("/api/v1/session", json={"sid": sid}).status_code == 401


def test_login_rate_limited_after_limit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for _ in range(5):
        assert client.post("/api/v1/session", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/v1/session", json={"password": "wrong"})

    assert response.status_code == 429
    assert response.get_json() == {
        "error": {
            "code": "rate_limit_exceeded",
            "details": {},
            "message": "Too many attempts. Try again later.",
        }
    }


def test_login_rate_limit_is_scoped_to_each_app(tmp_path: Path) -> None:
    first_client = _client(tmp_path / "first")
    for _ in range(5):
        first_client.post("/api/v1/session", json={"password": "wrong"})

    second_client = _client(tmp_path / "second")

    response = second_client.post("/api/v1/session", json={"password": "wrong"})
    assert response.status_code == 401


def test_login_rate_limit_ignores_spoofed_forwarded_ips(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for index in range(5):
        response = client.post(
            "/api/v1/session",
            json={"password": "wrong"},
            headers={"X-Real-IP": f"203.0.113.{index + 1}"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/session",
        json={"password": "wrong"},
        headers={"X-Real-IP": "203.0.113.99"},
    )
    assert response.status_code == 429


def test_forwarded_headers_are_trusted_only_behind_production_nginx(monkeypatch) -> None:
    from admin.backend.app import trusted_proxy_peers

    development = SimpleNamespace(production=SimpleNamespace(enabled=False))
    production = SimpleNamespace(production=SimpleNamespace(enabled=True))
    unused_root = Path("unused")

    monkeypatch.setattr(BenchConfig, "read", lambda bench_root: development)
    assert trusted_proxy_peers(unused_root) == ()

    monkeypatch.setattr(BenchConfig, "read", lambda bench_root: production)
    assert trusted_proxy_peers(unused_root) == ("127.0.0.1", "::1", "")


def test_setup_endpoint_requires_auth_once_password_set(tmp_path: Path) -> None:
    client = _client(tmp_path)
    path = "/api/v1/setup/database-validations"
    assert client.post(path, json={"engine": "mariadb"}).status_code == 401
    client.set_cookie("sid", _session_token())
    assert client.post(path, json={"engine": "mariadb"}).status_code != 401


def test_setup_endpoint_open_before_password_set(tmp_path: Path) -> None:
    from admin.backend.app import create_app

    app = create_app(tmp_path)  # no bench.toml → first-time setup
    app.config["TESTING"] = True
    response = app.test_client().post(
        "/api/v1/setup/database-validations",
        json={"engine": "mariadb"},
    )
    assert response.status_code != 401


def test_setup_endpoint_fails_closed_when_config_is_corrupt(tmp_path: Path) -> None:
    from admin.backend.app import create_app

    (tmp_path / "bench.toml").write_text("[bench\n")
    app = create_app(tmp_path)
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/api/v1/setup/database-validations",
        json={"engine": "mariadb"},
    )

    assert response.status_code == 503


def test_has_scope_bench_token_allows_any_site() -> None:
    assert Session.has_scope({"scope": "bench"}, "example.com")
    assert Session.has_scope({"scope": "bench"}, "other.com")


def test_has_scope_site_token_allows_matching_site() -> None:
    assert Session.has_scope({"scope": "site", "site": "example.com"}, "example.com")


def test_has_scope_site_token_rejects_different_site() -> None:
    assert not Session.has_scope({"scope": "site", "site": "example.com"}, "other.com")


def test_has_scope_none_claims_rejected() -> None:
    assert not Session.has_scope(None, "example.com")


@pytest.mark.parametrize(
    ("scope", "site"),
    [
        ("site", "example.com"),
        ("unknown", None),
    ],
)
def test_non_bench_token_cannot_access_bench_route(
    tmp_path: Path,
    scope: str,
    site: str | None,
) -> None:
    client = _client(tmp_path)
    token = _session_token(scope=scope, site=site)

    response = client.get("/api/v1/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_require_scope_allows_unscoped_token(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scoped")
    @require_scope("example.com")
    def scoped_view():
        return jsonify({"ok": True})

    client = app.test_client()
    client.set_cookie("sid", _session_token())
    assert client.get("/api/v1/test-scoped").status_code == 200


def test_require_scope_allows_matching_scoped_token(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scoped")
    @require_scope("example.com")
    def scoped_view():
        return jsonify({"ok": True})

    client = app.test_client()
    client.set_cookie("sid", _session_token(scope="site", site="example.com"))
    assert client.get("/api/v1/test-scoped").status_code == 200


def test_require_scope_rejects_mismatched_scoped_token(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scoped")
    @require_scope("example.com")
    def scoped_view():
        return jsonify({"ok": True})

    client = app.test_client()
    client.set_cookie("sid", _session_token(scope="site", site="other.com"))
    assert client.get("/api/v1/test-scoped").status_code == 403


def test_current_site_scope_returns_site_from_claims(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import current_site_scope, require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scope")
    @require_scope("example.com")
    def scope_view():
        return jsonify({"site": current_site_scope()})

    client = app.test_client()
    client.set_cookie("sid", _session_token(scope="site", site="example.com"))
    assert client.get("/api/v1/test-scope").get_json()["site"] == "example.com"


def test_current_site_scope_returns_none_for_unscoped(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import current_site_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scope")
    def scope_view():
        return jsonify({"site": current_site_scope()})

    client = app.test_client()
    client.set_cookie("sid", _session_token())
    assert client.get("/api/v1/test-scope").get_json()["site"] is None


def test_bearer_token_authenticates(tmp_path: Path) -> None:
    client = _client(tmp_path)
    token = _session_token()
    resp = client.get("/api/v1/benches", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code != 401


def test_bearer_token_with_site_scope(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scoped")
    @require_scope("example.com")
    def scoped_view():
        return jsonify({"ok": True})

    client = app.test_client()
    token = _session_token(scope="site", site="example.com")
    resp = client.get("/api/v1/test-scoped", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_bearer_token_wrong_site_rejected(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/test-scoped")
    @require_scope("example.com")
    def scoped_view():
        return jsonify({"ok": True})

    client = app.test_client()
    token = _session_token(scope="site", site="other.com")
    resp = client.get("/api/v1/test-scoped", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_require_scope_with_callable(tmp_path: Path) -> None:
    from flask import jsonify

    from admin.backend.app import create_app
    from admin.backend.middleware import require_scope

    bench_root = tmp_path / "benches" / "current"
    _initialized_bench(bench_root, "secret", "k3y")
    app = create_app(bench_root)
    app.config["TESTING"] = True

    @app.route("/api/v1/sites/<name>/action")
    @require_scope(lambda kw: kw["name"])
    def scoped_view(name):
        return jsonify({"ok": True, "site": name})

    client = app.test_client()
    client.set_cookie("sid", _session_token(scope="site", site="example.com"))
    assert client.get("/api/v1/sites/example.com/action").status_code == 200
    assert client.get("/api/v1/sites/other.com/action").status_code == 403


def test_revoke_session_endpoint_revokes_active_jti(tmp_path: Path) -> None:
    from admin.backend.internal.session import ActiveTokens, RevokedTokens, Session

    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())
    bench = Bench(tmp_path / "benches" / "current")
    _, jti = Session(bench).issue_session_token()
    assert jti in ActiveTokens(bench)

    assert client.post("/api/v1/session/revoke", json={"jti": jti}).status_code == 204
    assert jti in RevokedTokens(bench)


def test_revoke_session_unknown_jti_is_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())
    assert client.post("/api/v1/session/revoke", json={"jti": "nope"}).status_code == 404


def test_revoke_session_requires_jti(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.set_cookie("sid", _session_token())
    assert client.post("/api/v1/session/revoke", json={}).status_code == 400


def test_revoke_session_requires_authentication(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.post("/api/v1/session/revoke", json={"jti": "x"}).status_code == 401
