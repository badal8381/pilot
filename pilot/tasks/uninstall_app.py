from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks import Task, step


@dataclass(kw_only=True)
class UninstallAppTask(Task):
    command: ClassVar[str] = "uninstall-app"
    # frappe writes module defs and doctypes before recording the app as
    # installed, so a kill leaves rows behind that fail every retry.
    is_cancellable: ClassVar[bool] = False

    site: str
    app: str
    force: bool = False

    def run(self) -> None:
        self.uninstall()

    @step("uninstall", lambda self: f"Uninstall {self.app} from {self.site}")
    def uninstall(self) -> None:
        site = self.bench.site(self.site)
        with site.under_maintenance():
            site.uninstall_apps([self.app], force=self.force, on_progress=self.report)
        site.clear_cache()


if __name__ == "__main__":
    UninstallAppTask.main()
