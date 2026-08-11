from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.core.database.mariadb_variables import (
    MARIADB_VARIABLE_SPECS,
    MariaDBValue,
    mariadb_variable_spec,
)
from pilot.exceptions import DatabaseError
from pilot.managers.database.mariadb import MariaDBManager
from pilot.managers.platform import is_linux

if TYPE_CHECKING:
    from pilot.config import BenchConfig


_MARIADB_ONLY = "Database configurations are available only when the bench uses MariaDB."
_UNREACHABLE = "MariaDB is not reachable with Pilot's admin credentials."
_EXTERNAL_READ_ONLY = (
    "External MariaDB configurations are read-only. Pilot changes only the MariaDB instance it "
    "provisioned on this server."
)


class DatabaseConfigurations:
    """Read the MariaDB catalog and authorize its small editable subset."""

    def __init__(
        self,
        config: BenchConfig,
        manager: MariaDBManager | None = None,
    ) -> None:
        self.config = config
        self.manager = (
            manager
            if manager is not None
            else (MariaDBManager(config.mariadb) if config.db_type == "mariadb" else None)
        )

    def snapshot(self) -> dict:
        read_reason = self._read_reason()
        managed = self.config.db_type == "mariadb" and not self.config.mariadb.existing
        if read_reason:
            return {
                "engine": self.config.db_type,
                "managed": managed,
                "readable": False,
                "editable": False,
                "reason": read_reason,
                "edit_reason": read_reason,
                "variables": [],
            }

        manager = self._manager()
        values = manager.global_variable_values(spec.name for spec in MARIADB_VARIABLE_SPECS)
        edit_reason = self._edit_reason()
        variables = []
        for spec in MARIADB_VARIABLE_SPECS:
            raw_value = values.get(spec.name)
            supported = raw_value is not None
            try:
                value = spec.parse_server_value(raw_value) if supported else None
            except ValueError as exc:
                raise DatabaseError(str(exc)) from exc

            editable = supported and spec.editable and not edit_reason
            if not supported:
                variable_reason = "This variable is not exposed by the installed MariaDB version."
            elif not spec.editable:
                variable_reason = spec.read_only_reason
            else:
                variable_reason = edit_reason

            variables.append(
                {
                    "name": spec.name,
                    "label": spec.label,
                    "section": spec.section,
                    "description": spec.description,
                    "value": value,
                    "value_type": spec.value_type,
                    "unit": spec.unit,
                    "dynamic": spec.dynamic,
                    "requires_restart": not spec.dynamic,
                    "supported": supported,
                    "editable": editable,
                    "reason": variable_reason,
                    "min": spec.minimum,
                    "max": spec.maximum,
                    "step": spec.step,
                }
            )
        return {
            "engine": self.config.db_type,
            "managed": managed,
            "readable": True,
            "editable": not edit_reason,
            "reason": "",
            "edit_reason": edit_reason,
            "variables": variables,
        }

    def prepare_change(self, name: str, value: object) -> dict:
        spec = mariadb_variable_spec(name)
        requested = spec.validate_input(value)
        edit_reason = self._edit_reason(require_reachable=True)
        if edit_reason:
            raise DatabaseError(edit_reason)

        raw_value = self._manager().global_variable_values((name,)).get(name)
        if raw_value is None:
            raise DatabaseError(f"MariaDB variable '{name}' is not exposed by the installed MariaDB version.")
        try:
            current = spec.parse_server_value(raw_value)
        except ValueError as exc:
            raise DatabaseError(str(exc)) from exc
        return {
            "name": name,
            "value": requested,
            "current": current,
            "changed": current != requested,
        }

    def set(self, name: str, value: object) -> bool:
        spec = mariadb_variable_spec(name)
        requested: MariaDBValue = spec.validate_input(value)
        edit_reason = self._edit_reason(require_reachable=True)
        if edit_reason:
            raise DatabaseError(edit_reason)
        return self._manager().set_configuration_variable(name, requested)

    def _read_reason(self) -> str:
        if self.config.db_type != "mariadb":
            return _MARIADB_ONLY
        manager = self._manager()
        if not self.config.mariadb.existing:
            if not manager.is_installed():
                return "MariaDB is not installed on this server."
            if not manager.is_provisioned():
                return "Pilot's MariaDB server has not been provisioned."
        if not manager.is_healthy():
            return _UNREACHABLE
        return ""

    def _edit_reason(self, *, require_reachable: bool = False) -> str:
        if self.config.db_type != "mariadb":
            return _MARIADB_ONLY
        if self.config.mariadb.existing:
            return _EXTERNAL_READ_ONLY
        if not self.config.admin.allow_bench_management:
            return "Bench management is disabled on this server."
        if not is_linux():
            return "MariaDB configuration changes are available only on Linux."
        if require_reachable:
            return self._read_reason()
        return ""

    def _manager(self) -> MariaDBManager:
        if self.manager is None:
            raise DatabaseError(_MARIADB_ONLY)
        return self.manager
