from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks import Task, on_success, step


@dataclass(kw_only=True)
class UninstallAppTask(Task):
    command: ClassVar[str] = "uninstall-app"

    site: str
    app: str
    force: bool = False

    def run(self) -> None:
        self.uninstall()

    @on_success
    def reload_workers(self) -> dict:
        """Long-lived web and background workers hold the old app list and
        import map, so they need a restart once this task lands."""
        return {"web_only": False}

    @step("uninstall", lambda self: f"Uninstall {self.app} from {self.site}")
    def uninstall(self) -> None:
        site = self.bench.site(self.site)
        site.uninstall_apps([self.app], force=self.force, on_progress=self.report)


if __name__ == "__main__":
    UninstallAppTask.main()
