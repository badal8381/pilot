from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class RestartServicesTask(MigrationChainTask):
    """Chain link: restart services to finish a restore, then mark the operation reverted."""

    command: ClassVar[str] = "restart-services"

    def run_step(self, operation) -> None:
        operation.restart(on_step=self.step)


if __name__ == "__main__":
    RestartServicesTask.main()
