"""App-declared processes are registered into prod_process_definitions, fault-isolated."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pilot.managers.processes.definitions import ProcessDefinitionBuilder
from tests.pilot.commands.test_commands import make_bench


def _make_app(bench, name: str, pyproject: str) -> None:
    app_dir = bench.apps_path / name
    (app_dir / ".git").mkdir(parents=True)
    (app_dir / "pyproject.toml").write_text(pyproject)


def _builder(bench) -> ProcessDefinitionBuilder:
    return ProcessDefinitionBuilder(bench, Path("/usr/bin/python3"), watch_admin_js=False)


_GOOD = '[tool.pilot.background_processes.stalwart]\ncmd = ["/usr/bin/stalwart-mail"]\n'


def test_app_processes_appended(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _make_app(bench, "mail", _GOOD)

    names = [d.name for d in _builder(bench).prod_process_definitions()]
    assert "mail-stalwart" in names
    assert "web" in names  # core processes still present


def test_one_bad_app_does_not_break_core(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    _make_app(bench, "broken", "[tool.pilot\n")  # malformed TOML
    _make_app(bench, "mail", _GOOD)

    names = [d.name for d in _builder(bench).prod_process_definitions()]
    assert "web" in names  # core survives the bad app
    assert "mail-stalwart" in names  # the good app still registers


def test_removed_app_drops_out_of_definitions(tmp_path: Path) -> None:
    """Removing an app removes its process from the desired set, so systemd's
    existing reaping unlinks its stale unit."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    _make_app(bench, "mail", _GOOD)
    assert "mail-stalwart" in [d.name for d in _builder(bench).prod_process_definitions()]

    subprocess.run(["rm", "-rf", str(bench.apps_path / "mail")], check=True)
    assert "mail-stalwart" not in [d.name for d in _builder(bench).prod_process_definitions()]
