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
    """An app's [tool.pilot] declaration is malformed or unsafe."""


class AppRequirements:
    """Reads and validates an app's process declarations from the
    [tool.pilot.background_processes] table of its pyproject.toml.

    Each process is a sub-table keyed by its name:

        [tool.pilot.background_processes.flow_server]
        cmd = ["flow", "serve"]
        restart_on_failure = true
        pre_run = ["bash", "-c", "./scripts/install_flow.sh"]
        post_run = ["bash", "-c", "rm -f flow.sock"]

    Every declared value is attacker-controlled (any installed app), so each
    field is validated on read - reject, never sanitize - before it can reach a
    unit file or a shell.
    """

    def __init__(self, app: "App") -> None:
        self.app = app

    def process_definitions(self) -> list[ProcessDefinition]:
        return [self._build_definition(name, entry) for name, entry in self._process_entries.items()]

    @property
    def _process_entries(self) -> dict:
        entries = self._tool_pilot.get("background_processes", {})
        if not isinstance(entries, dict):
            raise self._error("[tool.pilot.background_processes] must be a table of tables.")
        return entries

    @property
    def _tool_pilot(self) -> dict:
        pyproject = self.app.path / "pyproject.toml"
        if not pyproject.exists():
            return {}
        try:
            data = tomllib.loads(pyproject.read_text())
        except (tomllib.TOMLDecodeError, OSError) as exc:
            raise self._error(f"unreadable pyproject.toml: {exc}") from exc
        section = data.get("tool", {}).get("pilot", {})
        return section if isinstance(section, dict) else {}

    def _build_definition(self, name: str, entry: object) -> ProcessDefinition:
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise self._error(f"process name '{name}' is invalid; must match {_NAME_RE.pattern}.")
        if not isinstance(entry, dict):
            raise self._error(f"process '{name}' must be a table.")

        cmd = self._argv(name, "cmd", entry.get("cmd"), required=True)
        pre_run = self._argv(name, "pre_run", entry.get("pre_run"))
        post_run = self._argv(name, "post_run", entry.get("post_run"))

        restart_on_failure = entry.get("restart_on_failure", True)
        if not isinstance(restart_on_failure, bool):
            raise self._error(f"process '{name}' restart_on_failure must be true or false.")

        env = self._env(name, entry.get("env", {}))

        working_dir = entry.get("working_dir")
        if working_dir is not None:
            self._reject_control(name, "working_dir", working_dir)

        stop_timeout = entry.get("stop_timeout")
        if stop_timeout is not None and (not isinstance(stop_timeout, int) or stop_timeout < 0):
            raise self._error(f"process '{name}' stop_timeout must be a non-negative integer.")

        prefixed = f"{self.app.config.name}-{name}"
        return ProcessDefinition(
            name=prefixed,
            argv=cmd,
            log_file=self.app.bench.logs_path / f"{prefixed}.log",
            env=env,
            working_dir=Path(working_dir) if working_dir else None,
            stop_timeout=stop_timeout,
            restart_on_failure=restart_on_failure,
            pre_run=pre_run,
            post_run=post_run,
        )

    def _env(self, name: str, env: object) -> dict[str, str]:
        if not isinstance(env, dict):
            raise self._error(f"process '{name}' env must be a table.")
        for key, value in env.items():
            if not _ENV_KEY_RE.match(key):
                raise self._error(
                    f"process '{name}' env key '{key}' is invalid; must match {_ENV_KEY_RE.pattern}."
                )
            self._reject_control(name, f"env[{key}]", value)
        return {key: str(value) for key, value in env.items()}

    def _argv(self, name: str, field: str, value: object, required: bool = False) -> list[str]:
        """An argv list - executable plus args, never a shell string."""
        if value is None:
            if required:
                raise self._error(f"process '{name}' needs a non-empty {field} list.")
            return []
        if not isinstance(value, list) or not value:
            raise self._error(f"process '{name}' {field} must be a non-empty list of strings.")
        for arg in value:
            self._reject_control(name, field, arg)
        return [str(arg) for arg in value]

    def _reject_control(self, process: str, field: str, value: object) -> None:
        if not isinstance(value, str) or _CONTROL_RE.search(value):
            raise self._error(
                f"process '{process}' field '{field}' must be a string with no control characters."
            )

    def _error(self, detail: str) -> AppRequirementsError:
        return AppRequirementsError(f"'{self.app.config.name}': {detail}")
