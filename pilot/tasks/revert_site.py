from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks.migration_chain import MigrationChainTask


@dataclass(kw_only=True)
class RevertSiteTask(MigrationChainTask):
    """Chain link: restore one site's database and clear its cache, then queue the next site."""

    command: ClassVar[str] = "revert-site"

    site: str

    def run_step(self, operation) -> None:
        operation.revert_site(self.site, on_step=self.step, on_progress=self.report)


if __name__ == "__main__":
    RevertSiteTask.main()
