import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pilot.tasks import Task, on_cancel, on_failure

if TYPE_CHECKING:
    from pilot.core.bench.migration.operation import MigrationOperation


@dataclass(kw_only=True)
class MigrationChainTask(Task):
    """One link of a migration chain: run its step, then queue whatever the operation wants next."""

    operation_id: str

    def run(self) -> None:
        operation = self.bench.migrations.get(self.operation_id)
        try:
            self.run_step(operation)
        except Exception:
            self.step_failed()
            sys.exit(1)
        operation.enqueue_next(handoff_from=operation.chain[-1]["task_id"])

    def run_step(self, operation: "MigrationOperation") -> None:
        raise NotImplementedError

    @on_failure
    @on_cancel
    def strand_migration(self) -> dict:
        """A killed link never reaches its own error handling, so the operation is
        parked from outside instead - by the wrapper, or by task reconciliation."""
        return {"operation_id": self.operation_id}
