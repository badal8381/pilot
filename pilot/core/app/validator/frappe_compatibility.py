from __future__ import annotations

import ast
import typing

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from pilot.core.app.validator.base import module_path, read_pyproject
from pilot.exceptions import AppValidationError, BenchError

if typing.TYPE_CHECKING:
    from pathlib import Path

    from pilot.core.app import App


class FrappeCompatibilityCheck:
    """Check the bench actually satisfies the app versions an app declares.

    DependencyDeclarationsCheck only validates the shape of
    `[tool.bench.frappe-dependencies]`. This compares it to what is installed,
    which is what catches a new revision that needs a newer frappe than the
    bench runs. An app that declares nothing is left alone, so an app older
    than the rule still updates.
    """

    def run(self, app: "App") -> None:
        declared = (read_pyproject(app) or {}).get("tool", {}).get("bench", {}).get("frappe-dependencies", {})
        if not isinstance(declared, dict):
            return  # DependencyDeclarationsCheck reports a malformed table on install

        problems = [
            problem
            for name, specifier in declared.items()
            if (problem := self._mismatch(app, name, str(specifier)))
        ]
        if problems:
            raise AppValidationError(
                f"'{app.config.name}' needs app versions this bench doesn't have:\n"
                + "\n".join(f"  {problem}" for problem in problems)
                + f"\nUpdate the app it needs, or move '{app.config.name}' to a revision that "
                "supports what is installed."
            )

    def _mismatch(self, app: "App", name: str, specifier: str) -> str | None:
        """Why the installed `name` falls outside `specifier`, or None if it fits.

        None also covers what this check can't judge: an app that isn't installed
        (the dependency installer reports that), and a version or range it can't read.
        """
        try:
            installed = app.bench.app(name)
        except BenchError:
            return None
        version = self._declared_version(module_path(installed) / "__init__.py")
        if version is None:
            return None
        try:
            # Without prereleases the bench's own dev build matches nothing.
            allowed = SpecifierSet(specifier, prereleases=True)
        except InvalidSpecifier:
            return None  # VersionSpecifiersCheck reports an unreadable range
        if version in allowed:
            return None
        return f"needs {name} {specifier}, but {version} is installed"

    @staticmethod
    def _declared_version(init_file: "Path") -> Version | None:
        """The `__version__` an app assigns at the top of its package."""
        try:
            tree = ast.parse(init_file.read_text())
        except (OSError, SyntaxError):
            return None

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "__version__" not in names or not isinstance(node.value, ast.Constant):
                continue
            try:
                return Version(str(node.value.value))
            except InvalidVersion:
                return None
        return None
