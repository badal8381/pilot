"""Tests for DependencyResolutionCheck, the --dry-run resolve against the bench env."""

from __future__ import annotations

from pathlib import Path

import pytest

from pilot.core.app.validator import dependency_resolution
from pilot.core.app.validator.dependency_resolution import DependencyResolutionCheck
from pilot.exceptions import AppValidationError, CommandError

UV_URL_DEPENDENCY_ERROR = (
    "Failed to resolve dependencies for `frappe` (v16.16.0)\n"
    "Package `pypika` was included as a URL dependency."
)


class _FakeApp:
    def __init__(self, bench_root: Path, name: str = "myapp") -> None:
        self.path = bench_root / "apps" / name
        self.config = type("Config", (), {"name": name})
        self.bench = type("Bench", (), {"env_path": bench_root / "env"})


def _make_bench(tmp_path: Path, *, with_env: bool = True) -> _FakeApp:
    (tmp_path / "apps" / "myapp").mkdir(parents=True)
    if with_env:
        (tmp_path / "env" / "bin").mkdir(parents=True)
        (tmp_path / "env" / "bin" / "python").write_text("")
    return _FakeApp(tmp_path)


def test_resolution_runs_the_real_install_command_with_dry_run(monkeypatch, tmp_path: Path) -> None:
    app = _make_bench(tmp_path)
    commands: list[list[str]] = []
    monkeypatch.setattr(dependency_resolution, "ensure_uv", lambda: "/bin/uv")
    monkeypatch.setattr(dependency_resolution, "run_command", lambda argv, **kw: commands.append(argv))

    DependencyResolutionCheck().run(app)

    assert commands == [
        [
            "/bin/uv",
            "pip",
            "install",
            "--dry-run",
            "--python",
            str(tmp_path / "env" / "bin" / "python"),
            "-e",
            str(app.path),
        ]
    ]


def test_resolution_reports_what_uv_could_not_resolve(monkeypatch, tmp_path: Path) -> None:
    app = _make_bench(tmp_path)
    monkeypatch.setattr(dependency_resolution, "ensure_uv", lambda: "/bin/uv")

    def fail(argv, **kwargs):
        raise CommandError(UV_URL_DEPENDENCY_ERROR)

    monkeypatch.setattr(dependency_resolution, "run_command", fail)

    with pytest.raises(AppValidationError, match="pypika"):
        DependencyResolutionCheck().run(app)


def test_resolution_is_skipped_before_the_bench_has_an_environment(monkeypatch, tmp_path: Path) -> None:
    app = _make_bench(tmp_path, with_env=False)

    def fail(*args, **kwargs):
        raise AssertionError("nothing to resolve against without an env")

    monkeypatch.setattr(dependency_resolution, "run_command", fail)

    DependencyResolutionCheck().run(app)
