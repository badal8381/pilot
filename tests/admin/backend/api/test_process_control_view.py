"""Tests for the per-process control route."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pilot.config import BenchConfig


def _client(bench_root: Path, password: str = "secret"):
    from admin.backend.app import create_app
    from admin.backend.internal.session import Session
    from pilot.core.bench import Bench

    bench_root.mkdir(parents=True, exist_ok=True)
    flat = {
        "admin_enabled": True,
        "admin_password": password,
        "admin_allow_bench_management": True,
        "db_type": "mariadb",
    }
    (bench_root / "bench.toml").write_text(BenchConfig.from_flat(bench_root.name, flat).dumps())
    app = create_app(bench_root)
    app.config["TESTING"] = True
    client = app.test_client()
    client.set_cookie("sid", Session(Bench(bench_root)).issue_session_token()[0])
    return client


def test_bad_action_verb_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path / "benches" / "current")
    response = client.post("/api/v1/runtime/actions/delete/process", json={"name": "web"})
    assert response.status_code == 400


def test_unknown_process_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path / "benches" / "current")
    with patch("admin.backend.api.v1.processes.ProcessProvider.get_all", return_value=[]):
        response = client.post("/api/v1/runtime/actions/restart/process", json={"name": "ghost"})
    assert response.status_code == 404


def test_controllable_true_in_production(tmp_path: Path) -> None:
    client = _client(tmp_path / "benches" / "current")
    with (
        patch("admin.backend.api.v1.processes.ProcessProvider.get_all", return_value=[]),
        patch("admin.backend.api.v1.processes._is_production", return_value=True),
    ):
        response = client.get("/api/v1/runtime/processes")
    assert response.status_code == 200
    assert response.get_json()["controllable"] is True


def test_controllable_false_outside_production(tmp_path: Path) -> None:
    client = _client(tmp_path / "benches" / "current")
    with (
        patch("admin.backend.api.v1.processes.ProcessProvider.get_all", return_value=[]),
        patch("admin.backend.api.v1.processes._is_production", return_value=False),
    ):
        response = client.get("/api/v1/runtime/processes")
    assert response.get_json()["controllable"] is False
