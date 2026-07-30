"""Tests for SwitchBranchTask validating the branch it switches to."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pilot.core.app import App
from pilot.exceptions import AppValidationError
from pilot.managers.environment import PythonEnvManager
from pilot.tasks.switch_branch import SwitchBranchTask
from tests.pilot.commands.test_commands import make_bench


def _write_app(bench, fixture: str) -> None:
    app_path = bench.apps_path / "myapp"
    (app_path / "myapp").mkdir(parents=True)
    (app_path / ".git").mkdir()
    (app_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
    (app_path / "myapp" / "__init__.py").write_text("")
    (app_path / "myapp" / "hooks.py").write_text("app_name = 'myapp'\n")
    (app_path / "myapp" / "fixtures").mkdir()
    (app_path / "myapp" / "fixtures" / "role.json").write_text(fixture)


def _task(bench) -> SwitchBranchTask:
    return SwitchBranchTask(bench=bench, bench_root=bench.path, name="myapp", branch="develop")


def test_switch_branch_installs_a_branch_that_validates(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, '[{"doctype": "Role"}]\n')

    with (
        patch.object(App, "head_sha", "abc1234"),
        patch.object(App, "switch_branch"),
        patch.object(App, "record_branch"),
        patch.object(PythonEnvManager, "install_app") as mock_install,
        patch.object(PythonEnvManager, "build_assets_for_app") as mock_build,
    ):
        _task(bench).run()

    mock_install.assert_called_once()
    mock_build.assert_called_once()


def test_switch_branch_returns_to_the_old_commit_when_the_new_one_is_broken(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _write_app(bench, "{not json\n")

    with (
        patch.object(App, "head_sha", "abc1234"),
        patch.object(App, "switch_branch"),
        patch.object(App, "checkout_commit") as mock_checkout,
        patch.object(PythonEnvManager, "install_app") as mock_install,
        pytest.raises(AppValidationError, match=r"fixtures/role\.json"),
    ):
        _task(bench).run()

    mock_checkout.assert_called_once_with("abc1234")
    mock_install.assert_not_called()
