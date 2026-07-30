from __future__ import annotations

import os
import typing

from pilot.exceptions import AppValidationError, CommandError
from pilot.managers.environment import ensure_uv
from pilot.managers.platform import add_mysqlclient_flags
from pilot.utils import run_command

if typing.TYPE_CHECKING:
    from pilot.core.app import App


class DependencyResolutionCheck:
    """Resolve the app's dependencies against the bench environment, without
    installing anything.

    Runs the same command the real install runs, with --dry-run, so a set that
    uv cannot resolve - a URL dependency it refuses, a version no release
    satisfies - fails here instead of halfway through the install.
    """

    def run(self, app: "App") -> None:
        python = app.bench.env_path / "bin" / "python"
        if not python.exists():
            return  # no environment to resolve against yet

        env = os.environ.copy()
        add_mysqlclient_flags(env)
        try:
            run_command(
                [ensure_uv(), "pip", "install", "--dry-run", "--python", str(python), "-e", str(app.path)],
                env=env,
            )
        except CommandError as exc:
            raise AppValidationError(
                f"'{app.config.name}' has dependencies that can't be resolved against this bench:\n"
                f"{exc.message}\n"
                "Fix the requirements in pyproject.toml, or install what they need first."
            ) from exc
