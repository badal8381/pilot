from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar

from pilot.commands import Arg, Command
from pilot.exceptions import BenchError


@dataclass(kw_only=True)
class SetAdminPasswordCommand(Command):
    name: ClassVar[str] = "set-admin-password"
    help: ClassVar[str] = "Set the admin panel password (prompts if --password is omitted)."

    password: Annotated[str | None, Arg(help="New password; omit to be prompted securely.")] = None

    def run(self) -> None:
        from pilot.config import BenchConfig

        password = self.resolve_password(self.password)
        if not password:
            raise BenchError("Password must not be empty.")

        with BenchConfig.open(self.bench.path, mode="raw") as data:
            data.setdefault("admin", {})["password"] = password
        self.bench.config.admin.password = password
        self.report("Admin password updated.")
