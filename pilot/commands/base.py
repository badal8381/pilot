from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, ClassVar

from pilot.exceptions import BenchError

__all__ = ["Arg", "BenchMode", "Command"]

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class BenchMode(Enum):
    """How the registry resolves Command.bench before dispatch."""

    NONE = auto()
    OPTIONAL = auto()
    AUTO = auto()
    EXPLICIT = auto()


@dataclass(frozen=True)
class Arg:
    help: str = ""
    short: str | None = None
    cli: bool = True
    metavar: str | None = None
    required: bool = False


@dataclass
class Command:
    """Dataclass-backed CLI command base."""

    name: ClassVar[str]
    help: ClassVar[str] = ""
    group: ClassVar[str | None] = None
    bench_mode: ClassVar[BenchMode] = BenchMode.AUTO
    supports_all_benches: ClassVar[bool] = False
    # In a `-b all` sweep, also run on development benches. Off by default:
    # a foreground dev `start` would hang the loop.
    supports_dev_benches: ClassVar[bool] = False

    bench: Bench | None = None

    def run(self) -> None:
        raise NotImplementedError

    def report(self, message: str) -> None:
        print(message)
        sys.stdout.flush()

    def resolve_password(self, value: str | None, label: str = "admin password") -> str:
        """A validated password from the flag or the terminal. Returns "" when neither
        supplied one, leaving the caller to generate it."""
        from pilot.internal.validators import validate_admin_password

        password = value or self.ask_password(label)
        if not password:
            return ""
        if error := validate_admin_password(password):
            raise BenchError(error)
        return password

    def ask_password(self, label: str = "admin password") -> str:
        """Read a password twice from the terminal. Returns "" with no TTY to ask on,
        so an unattended run can fall back to a generated one."""
        import getpass

        if not sys.stdin.isatty():
            return ""
        password = getpass.getpass(f"New {label}: ")
        if password != getpass.getpass(f"Confirm {label}: "):
            raise BenchError("Passwords do not match.")
        return password

    def confirm(self, prompt: str, *, skip: bool = False, error: type[Exception] = BenchError) -> None:
        if skip:
            return
        try:
            answer = input(f"{prompt} [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            raise error("Aborted.")
