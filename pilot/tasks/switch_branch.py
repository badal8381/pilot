import sys
from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks import Task, on_success, step


@dataclass(kw_only=True)
class SwitchBranchTask(Task):
    command: ClassVar[str] = "switch-branch"

    name: str
    branch: str

    def run(self) -> None:
        from pilot.managers.environment import PythonEnvManager

        app = self.bench.app(self.name)
        self.checkout(app)

        env = PythonEnvManager(self.bench)
        self.install(env, app)
        self.build_assets(env, app)

        app.record_branch()
        print(f"'{self.name}' switched to '{self.branch}' successfully.")

    @on_success
    def reload_workers(self) -> dict:
        """Long-lived web and background workers hold the old app list and
        import map, so they need a restart once this task lands."""
        return {"web_only": False}

    @step("checkout", lambda self: f"Switch to branch '{self.branch}'")
    def checkout(self, app) -> None:
        from pilot.exceptions import BenchError

        try:
            app.switch_branch(self.branch)
        except BenchError as exc:
            print(str(exc))
            sys.exit(1)

    @step("install", lambda self: f"Reinstall {self.name}")
    def install(self, env, app) -> None:
        env.install_app(app)

    @step("assets", "Build assets")
    def build_assets(self, env, app) -> None:
        env.build_assets_for_app(app)


if __name__ == "__main__":
    SwitchBranchTask.main()
