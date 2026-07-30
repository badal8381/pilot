"""Tests for BenchUpdater.update_apps validating apps after they move revision."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pilot.core.app import App
from pilot.core.bench.update import BenchUpdater
from pilot.exceptions import AppValidationError
from tests.pilot.commands.test_commands import make_bench


def _write_app(bench, name: str, hooks: str = "app_name = 'x'\n", fixture: str | None = None) -> Path:
    app_path = bench.apps_path / name
    (app_path / name).mkdir(parents=True)
    (app_path / ".git").mkdir()
    (app_path / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n')
    (app_path / name / "__init__.py").write_text("")
    (app_path / name / "hooks.py").write_text(hooks)
    if fixture is not None:
        (app_path / name / "fixtures").mkdir()
        (app_path / name / "fixtures" / "role.json").write_text(fixture)
    return app_path


def test_update_apps_validates_every_updated_app(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, "myapp", fixture='[{"doctype": "Role"}]\n')
    _write_app(bench, "otherapp")

    with patch.object(App, "update") as mock_update:
        BenchUpdater(bench).update_apps(None, lambda message: None, pins={})

    assert mock_update.call_count == 2


def test_update_apps_rejects_a_corrupt_fixture_before_installing(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, "myapp", fixture='[{"doctype":\n')

    with (
        patch.object(App, "update"),
        pytest.raises(AppValidationError, match=r"fixtures/role\.json"),
    ):
        BenchUpdater(bench).update_apps(None, lambda message: None, pins={})


def test_update_apps_rejects_a_hook_pointing_at_deleted_code(tmp_path: Path) -> None:
    """The common update failure: the new revision renamed a hooked function."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, "myapp", hooks='after_migrate = "myapp.setup.after_migrate"\n')

    with (
        patch.object(App, "update"),
        pytest.raises(AppValidationError, match="has no 'setup'"),
    ):
        BenchUpdater(bench).update_apps(None, lambda message: None, pins={})


def test_update_apps_only_validates_the_filtered_apps(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, "myapp")
    _write_app(bench, "brokenapp", fixture="{oops\n")

    with patch.object(App, "update"):
        BenchUpdater(bench).update_apps({"myapp"}, lambda message: None, pins={})


def test_update_apps_skips_checks_an_installed_app_may_predate(tmp_path: Path) -> None:
    """No pyproject.toml or hooks.py: those rules apply to new installs, not to
    an app that is already on the bench and working."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    app_path = bench.apps_path / "oldapp"
    app_path.mkdir(parents=True)
    (app_path / ".git").mkdir()
    (app_path / "setup.py").write_text("from setuptools import setup; setup()\n")

    with patch.object(App, "update"):
        BenchUpdater(bench).update_apps(None, lambda message: None, pins={})
