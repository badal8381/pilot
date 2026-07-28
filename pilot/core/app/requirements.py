from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from pilot.exceptions import BenchError
from pilot.managers.processes.definitions import ProcessDefinition

if TYPE_CHECKING:
    from pilot.core.app import App

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class AppRequirementsError(BenchError):
    """An app's [tool.bench] declaration is malformed or unsafe."""


class AppRequirements:
    """Reads and validates an app's process declarations from the
    [[tool.bench.processes]] tables of its pyproject.toml.

    A process may ship a `setup` script (bash or plain python, no root) that
    fetches the binary it runs; the bench runs it at install time. Every declared
    value is attacker-controlled (any installed app), so each field is validated
    on read - reject, never sanitize - before it can reach a unit file or a shell.
    """

    def __init__(self, app: "App") -> None:
        self.app = app

    def process_definitions(self) -> list[ProcessDefinition]:
        return [self._build_definition(entry) for entry in self._process_entries]

    def setup_scripts(self) -> list[Path]:
        """Resolved paths of app-shipped setup scripts, in declaration order."""
        scripts = []
        for entry in self._process_entries:
            setup = entry.get("setup")
            if setup is not None:
                scripts.append(self._resolve_setup(entry.get("name", ""), setup))
        return scripts

    @property
    def _process_entries(self) -> list[dict]:
        entries = self._tool_bench.get("processes", [])
        if not isinstance(entries, list):
            raise self._error("[[tool.bench.processes]] must be a list of tables.")
        return entries

    @property
    def _tool_bench(self) -> dict:
        pyproject = self.app.path / "pyproject.toml"
        if not pyproject.exists():
            return {}
        try:
            data = tomllib.loads(pyproject.read_text())
        except (tomllib.TOMLDecodeError, OSError) as exc:
            raise self._error(f"unreadable pyproject.toml: {exc}") from exc
        section = data.get("tool", {}).get("bench", {})
        return section if isinstance(section, dict) else {}

    def _build_definition(self, entry: dict) -> ProcessDefinition:
        name = entry.get("name", "")
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise self._error(f"process name '{name}' is invalid; must match {_NAME_RE.pattern}.")

        command = entry.get("command", [])
        if not isinstance(command, list) or not command:
            raise self._error(f"process '{name}' needs a non-empty command list.")
        for arg in command:
            self._reject_control(name, "command", arg)

        env = entry.get("env", {})
        if not isinstance(env, dict):
            raise self._error(f"process '{name}' env must be a table.")
        for key, value in env.items():
            if not _ENV_KEY_RE.match(key):
                raise self._error(
                    f"process '{name}' env key '{key}' is invalid; must match {_ENV_KEY_RE.pattern}."
                )
            self._reject_control(name, f"env[{key}]", value)

        working_dir = entry.get("working-dir")
        if working_dir is not None:
            self._reject_control(name, "working-dir", working_dir)

        stop_timeout = entry.get("stop-timeout")
        if stop_timeout is not None and (not isinstance(stop_timeout, int) or stop_timeout < 0):
            raise self._error(f"process '{name}' stop-timeout must be a non-negative integer.")

        prefixed = f"{self.app.config.name}-{name}"
        return ProcessDefinition(
            name=prefixed,
            argv=[str(arg) for arg in command],
            log_file=self.app.bench.logs_path / f"{prefixed}.log",
            env={key: str(value) for key, value in env.items()},
            working_dir=Path(working_dir) if working_dir else None,
            stop_timeout=stop_timeout,
        )

    def _resolve_setup(self, name: str, setup: object) -> Path:
        if not isinstance(setup, str) or not setup or _CONTROL_RE.search(setup):
            raise self._error(f"process '{name}' setup must be a relative path with no control chars.")
        path = Path(setup)
        if path.is_absolute() or ".." in path.parts:
            raise self._error(f"process '{name}' setup '{setup}' must stay inside the app directory.")
        resolved = (self.app.path / path).resolve()
        app_root = self.app.path.resolve()
        if app_root not in resolved.parents:
            raise self._error(f"process '{name}' setup '{setup}' escapes the app directory.")
        return resolved

    def _reject_control(self, process: str, field: str, value: object) -> None:
        if not isinstance(value, str) or _CONTROL_RE.search(value):
            raise self._error(
                f"process '{process}' field '{field}' must be a string with no control characters."
            )

    def _error(self, detail: str) -> AppRequirementsError:
        return AppRequirementsError(f"'{self.app.config.name}': {detail}")
