from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class RevertAppsTask(MigrationChainTask):
    """Chain link: roll app revisions back and rebuild, then queue the next revert step."""

    command: ClassVar[str] = "revert-apps"

    def run_step(self, operation) -> None:
        operation.revert_apps(on_step=self.step, on_progress=self.report)


if __name__ == "__main__":
    RevertAppsTask.main()
