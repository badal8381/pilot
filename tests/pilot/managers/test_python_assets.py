"""Tests for PythonAssetBuilder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pilot.managers.python_assets import PythonAssetBuilder


def make_app(app_path: Path, name: str = "gameplan") -> MagicMock:
    app = MagicMock()
    app.path = app_path
    app.config.name = name
    return app


def test_build_assets_for_app_installs_js_deps_before_frappe_build_runs(tmp_path: Path) -> None:
    """frappe's own `bench build` step shells into `frontend` and runs `yarn build` there,
    so node_modules must be synced before that step, not only in the standalone loop after it."""
    app_path = tmp_path / "gameplan"
    frontend_dir = app_path / "frontend"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "package.json").write_text("{}")

    manager = MagicMock()
    manager.bench.frappe_call = ["python"]
    manager.bench.sites_path = tmp_path / "sites"
    builder = PythonAssetBuilder(manager)

    events: list[str] = []

    with (
        patch("pilot.managers.python_assets.git_has_local_changes", return_value=True),
        patch(
            "pilot.managers.python_assets.run_command",
            side_effect=lambda *a, **k: events.append("run_command"),
        ),
        patch.object(
            builder,
            "ensure_yarn_install",
            side_effect=lambda path: events.append(f"ensure_yarn_install:{path.name}"),
        ),
    ):
        builder.build_assets_for_app(make_app(app_path))

    assert events.index("ensure_yarn_install:frontend") < events.index("run_command")
