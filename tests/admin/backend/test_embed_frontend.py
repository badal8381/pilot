"""Cloud Settings embed must answer Desk's /embed/cloud-settings/ URL."""

from __future__ import annotations

from pathlib import Path

import pytest

from admin.backend import app as admin_app


def _client(tmp_path: Path):
    from admin.backend.app import create_app

    bench = tmp_path / "bench"
    bench.mkdir()
    (bench / "bench.toml").write_text('[bench]\nname = "bench"\n')
    flask_app = create_app(bench)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_embed_bundle_is_served_at_desk_contract_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embed_dir = tmp_path / "embed" / "cloud-settings"
    embed_dir.mkdir(parents=True)
    (embed_dir / "cloud-settings.js").write_text("frappe.cloudSettings={show(){}}")
    monkeypatch.setattr(admin_app, "STATIC_DIR", tmp_path)

    response = _client(tmp_path).get("/embed/cloud-settings/cloud-settings.js")

    assert response.status_code == 200
    assert response.content_type.startswith("text/javascript")
    assert b"frappe.cloudSettings" in response.data
    assert "immutable" in response.headers.get("Cache-Control", "")


def test_embed_bundle_is_not_swallowed_by_dashboard_spa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dashboard = tmp_path / "dashboard"
    dashboard.mkdir()
    (dashboard / "index.html").write_text("<!doctype html><title>dashboard</title>")
    embed_dir = tmp_path / "embed" / "cloud-settings"
    embed_dir.mkdir(parents=True)
    (embed_dir / "cloud-settings.js").write_text("// embed")
    monkeypatch.setattr(admin_app, "STATIC_DIR", tmp_path)

    response = _client(tmp_path).get("/embed/cloud-settings/cloud-settings.js")

    assert response.status_code == 200
    assert b"dashboard" not in response.data
    assert response.data.startswith(b"// embed")


def test_missing_embed_build_returns_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_app, "STATIC_DIR", tmp_path / "empty-static")
    (tmp_path / "empty-static").mkdir()

    response = _client(tmp_path).get("/embed/cloud-settings/cloud-settings.js")

    assert response.status_code == 503
    assert b"not built" in response.data
