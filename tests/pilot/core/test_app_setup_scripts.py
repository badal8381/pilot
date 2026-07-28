"""App._run_setup_scripts runs an app-shipped setup script from the app dir."""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot.exceptions import BenchError
from tests.pilot.commands.test_commands import make_bench


def _app(tmp_path: Path, pyproject: str, name: str = "mail"):
    from pilot.config import AppConfig
    from pilot.core.app import App

    bench = make_bench(tmp_path)
    bench.create_directories()
    app_dir = bench.apps_path / name
    app_dir.mkdir(parents=True)
    (app_dir / "pyproject.toml").write_text(pyproject)
    return App(AppConfig(name=name, repo=f"https://github.com/frappe/{name}", branch="main"), bench)


def test_setup_script_runs_from_app_dir(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["./bin"]\nsetup = "setup.sh"\n',
    )
    # Writes a marker into the app dir (cwd) so we can prove it ran there.
    (app.path / "setup.sh").write_text("#!/bin/bash\necho done > fetched.txt\n")

    app._run_setup_scripts(lambda message: None)

    assert (app.path / "fetched.txt").read_text().strip() == "done"


def test_missing_setup_script_fails_loudly(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["./bin"]\nsetup = "absent.sh"\n',
    )
    with pytest.raises(BenchError):
        app._run_setup_scripts(lambda message: None)


def test_no_setup_is_a_noop(tmp_path: Path) -> None:
    app = _app(tmp_path, '[[tool.bench.processes]]\nname = "p"\ncommand = ["./bin"]\n')
    app._run_setup_scripts(lambda message: None)  # must not raise


def test_extensionless_script_runs_via_shebang(tmp_path: Path) -> None:
    app = _app(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["./bin"]\nsetup = "install"\n',
    )
    (app.path / "install").write_text("#!/bin/sh\necho ok > fetched.txt\n")

    app._run_setup_scripts(lambda message: None)

    assert (app.path / "fetched.txt").read_text().strip() == "ok"
