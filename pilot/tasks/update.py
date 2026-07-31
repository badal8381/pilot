from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class UpdateTask(MigrationChainTask):
    """Chain link: update/reinstall/rebuild apps, then queue the first site migration."""

    command: ClassVar[str] = "update"

    def run_step(self, operation) -> None:
        operation.update_apps(on_step=self.step, on_progress=self.report)


if __name__ == "__main__":
    UpdateTask.main()
