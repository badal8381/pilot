from __future__ import annotations

import typing

from pilot.core.app.validator.dependency_declarations import DependencyDeclarationsCheck
from pilot.core.app.validator.dependency_resolution import DependencyResolutionCheck
from pilot.core.app.validator.fixtures import FixturesCheck
from pilot.core.app.validator.frappe_compatibility import FrappeCompatibilityCheck
from pilot.core.app.validator.hooks import HooksCheck
from pilot.core.app.validator.imports import ImportCheck
from pilot.core.app.validator.repo_structure import RepoStructureCheck
from pilot.core.app.validator.symlinks import SymlinkCheck
from pilot.core.app.validator.syntax import SyntaxCheck
from pilot.core.app.validator.version_specifiers import VersionSpecifiersCheck

if typing.TYPE_CHECKING:
    from pilot.core.app import App
    from pilot.core.app.validator.base import ValidationCheck


class Validator:
    """Runs validation checks against an app."""

    def __init__(self, app: "App", checks: list["ValidationCheck"] | None = None) -> None:
        self.app = app
        self.checks = checks or _install_checks()

    @classmethod
    def for_update(cls, app: "App") -> "Validator":
        """The narrower gate for an app already on the bench that has just moved
        to a new revision."""
        return cls(app, checks=_update_checks())

    def validate(self) -> None:
        for check in self.checks:
            check.run(self.app)


def _install_checks() -> list["ValidationCheck"]:
    return [
        RepoStructureCheck(),
        VersionSpecifiersCheck(),
        SymlinkCheck(),
        SyntaxCheck(),
        HooksCheck(),
        FixturesCheck(),
        DependencyDeclarationsCheck(),
        FrappeCompatibilityCheck(),
        DependencyResolutionCheck(),
        ImportCheck(),
    ]


def _update_checks() -> list["ValidationCheck"]:
    """Leaves out repo-structure and dependency-declarations, which demand a
    layout and a pyproject.toml table an app already on the bench predates.

    Everything a new revision can change is still checked. The reinstall that
    follows an update runs `uv pip install` with no constraints, so it resolves
    the app's own requirements and will happily move a package another app
    pinned - resolution here is the only thing that sees that.
    """
    return [
        VersionSpecifiersCheck(),
        SymlinkCheck(),
        SyntaxCheck(),
        HooksCheck(),
        FixturesCheck(),
        FrappeCompatibilityCheck(),
        DependencyResolutionCheck(),
        ImportCheck(),
    ]
