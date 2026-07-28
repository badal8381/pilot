"""Tests for pilot.core.app.requirements.AppRequirements."""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot.core.app.requirements import AppRequirements, AppRequirementsError
from tests.pilot.commands.test_commands import make_bench


def _app_with_pyproject(tmp_path: Path, body: str, name: str = "mail"):
    from pilot.config import AppConfig
    from pilot.core.app import App

    bench = make_bench(tmp_path)
    bench.create_directories()
    app_dir = bench.apps_path / name
    app_dir.mkdir(parents=True)
    (app_dir / "pyproject.toml").write_text(body)
    return App(AppConfig(name=name, repo=f"https://github.com/frappe/{name}", branch="main"), bench)


def test_missing_section_yields_empty(tmp_path: Path) -> None:
    app = _app_with_pyproject(tmp_path, "[project]\nname = 'mail'\n")
    reqs = AppRequirements(app)
    assert reqs.process_definitions() == []
    assert reqs.setup_scripts() == []


def test_no_pyproject_yields_empty(tmp_path: Path) -> None:
    from pilot.config import AppConfig
    from pilot.core.app import App

    bench = make_bench(tmp_path)
    bench.create_directories()
    (bench.apps_path / "mail").mkdir(parents=True)
    app = App(AppConfig(name="mail", repo="https://github.com/frappe/mail", branch="main"), bench)
    reqs = AppRequirements(app)
    assert reqs.process_definitions() == []
    assert reqs.setup_scripts() == []


def test_reads_process_and_setup(tmp_path: Path) -> None:
    app = _app_with_pyproject(
        tmp_path,
        """
[[tool.bench.processes]]
name = "stalwart"
setup = "scripts/install_stalwart.sh"
command = ["./stalwart", "--config", "config.toml"]
working-dir = "/opt/stalwart"
stop-timeout = 30
[tool.bench.processes.env]
STALWART_PATH = "/opt/stalwart"
""",
    )
    reqs = AppRequirements(app)
    (pd,) = reqs.process_definitions()
    assert pd.name == "mail-stalwart"
    assert pd.argv == ["./stalwart", "--config", "config.toml"]
    assert pd.working_dir == Path("/opt/stalwart")
    assert pd.stop_timeout == 30
    assert pd.env == {"STALWART_PATH": "/opt/stalwart"}
    assert pd.log_file.name == "mail-stalwart.log"
    assert reqs.setup_scripts() == [app.path / "scripts" / "install_stalwart.sh"]


def test_no_setup_yields_no_scripts(tmp_path: Path) -> None:
    app = _app_with_pyproject(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["/bin/true"]\n',
    )
    assert AppRequirements(app).setup_scripts() == []


@pytest.mark.parametrize("setup", ["/etc/evil.sh", "../../evil.sh", "a/../../b.sh", "x\ny.sh"])
def test_setup_path_escaping_rejected(tmp_path: Path, setup: str) -> None:
    app = _app_with_pyproject(
        tmp_path,
        f'[[tool.bench.processes]]\nname = "p"\ncommand = ["/bin/true"]\nsetup = "{setup}"\n',
    )
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).setup_scripts()


def test_malformed_toml_raises(tmp_path: Path) -> None:
    app = _app_with_pyproject(tmp_path, "[tool.bench\n")
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()


@pytest.mark.parametrize("name", ["../evil", "bad name", "x\ninjected", "-flag", "UPPER", "a" * 40])
def test_bad_process_name_rejected(tmp_path: Path, name: str) -> None:
    app = _app_with_pyproject(
        tmp_path,
        f'[[tool.bench.processes]]\nname = "{name}"\ncommand = ["/bin/true"]\n',
    )
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()


def test_control_char_in_argv_rejected(tmp_path: Path) -> None:
    app = _app_with_pyproject(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["/bin/true\\n[Service]"]\n',
    )
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()


def test_control_char_in_env_value_rejected(tmp_path: Path) -> None:
    app = _app_with_pyproject(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["/bin/true"]\n'
        '[tool.bench.processes.env]\nK = "v\\nExecStartPre=/x"\n',
    )
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()


def test_bad_env_key_rejected(tmp_path: Path) -> None:
    app = _app_with_pyproject(
        tmp_path,
        '[[tool.bench.processes]]\nname = "p"\ncommand = ["/bin/true"]\n'
        '[tool.bench.processes.env]\n"bad-key" = "v"\n',
    )
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()


def test_empty_command_rejected(tmp_path: Path) -> None:
    app = _app_with_pyproject(tmp_path, '[[tool.bench.processes]]\nname = "p"\ncommand = []\n')
    with pytest.raises(AppRequirementsError):
        AppRequirements(app).process_definitions()
