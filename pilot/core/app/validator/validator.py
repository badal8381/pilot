from __future__ import annotations

import typing

from pilot.core.app.validator.dependency_declarations import DependencyDeclarationsCheck
from pilot.core.app.validator.dependency_resolution import DependencyResolutionCheck
from pilot.core.app.validator.fixtures import FixturesCheck
from pilot.core.app.validator.hooks import HooksCheck
from pilot.core.app.validator.imports import ImportCheck
from pilot.core.app.validator.repo_structure import RepoStructureCheck
from pilot.core.app.validator.symlinks import SymlinkCheck
from pilot.core.app.validator.syntax import SyntaxCheck
from pilot.core.app.validator.version_specifiers import VersionSpecifiersCheck

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from pilot.core.app import App
    from pilot.core.app.validator.base import ValidationCheck


class Validator:
    """Runs pre-install checks against a cloned app."""

    def __init__(self, app: "App", checks: list["ValidationCheck"] | None = None) -> None:
        self.app = app
        self.checks = checks or [
            RepoStructureCheck(),
            VersionSpecifiersCheck(),
            SymlinkCheck(),
            SyntaxCheck(),
            HooksCheck(),
            FixturesCheck(),
            DependencyDeclarationsCheck(),
            DependencyResolutionCheck(),
            ImportCheck(),
        ]

    def validate(self) -> None:
        for check in self.checks:
            check.run(self.app)


def update_checks() -> list["ValidationCheck"]:
    """Checks an app must pass after it moves to a new revision.

    Leaves out the repo-structure and dependency-declaration checks: an app
    already on the bench predates those rules, and an update is the wrong moment
    to start enforcing them. Resolution is left out because the pip install that
    follows resolves the same dependencies against the real environment - but
    nothing there reads the new revision's imports, so ImportCheck stays in.
    """
    return [
        VersionSpecifiersCheck(),
        SymlinkCheck(),
        SyntaxCheck(),
        HooksCheck(),
        FixturesCheck(),
        ImportCheck(),
    ]


def validate_updated_apps(apps: list["App"], on_progress: "Callable[[str], None]") -> None:
    """Validate updated apps in place, before anything installs or builds them."""
    for app in apps:
        on_progress(f"Validating {app.config.name}...")
        Validator(app, checks=update_checks()).validate()
