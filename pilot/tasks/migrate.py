from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class MigrateTask(MigrationChainTask):
    """Chain link: migrate one site, then queue the next site (or complete)."""

    command: ClassVar[str] = "migrate"

    site: str

    def run_step(self, operation) -> None:
        operation.migrate_site(self.site, on_step=self.step, on_progress=self.report)


if __name__ == "__main__":
    MigrateTask.main()
