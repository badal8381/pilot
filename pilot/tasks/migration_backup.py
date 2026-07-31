from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class MigrationBackupTask(MigrationChainTask):
    """Chain link: back up one site's tables before a migration, then queue the next step."""

    command: ClassVar[str] = "migration-backup"

    site: str

    def run_step(self, operation) -> None:
        operation.back_up_site(self.site, on_step=self.step, on_progress=self.report)


if __name__ == "__main__":
    MigrationBackupTask.main()
