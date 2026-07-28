"""Renderers reject control chars as a last gate before writing unit files."""

from pathlib import Path

import pytest

from pilot.managers.processes.definitions import ProcessDefinition
from pilot.managers.processes.supervisor import SupervisorRenderer
from pilot.managers.processes.systemd_render import SystemdRenderer


def test_systemd_render_rejects_newline_in_argv() -> None:
    pd = ProcessDefinition(
        name="mail-x",
        argv=["/bin/true\n[Service]\nExecStartPre=/x"],
        log_file=Path("/tmp/x.log"),
    )
    with pytest.raises(ValueError):
        SystemdRenderer("bench").render(pd)


def test_systemd_render_rejects_newline_in_env_value() -> None:
    pd = ProcessDefinition(
        name="mail-x",
        argv=["/bin/true"],
        log_file=Path("/tmp/x.log"),
        env={"K": "v\nExecStartPre=/x"},
    )
    with pytest.raises(ValueError):
        SystemdRenderer("bench").render(pd)


def test_supervisor_render_rejects_newline_in_argv() -> None:
    pd = ProcessDefinition(
        name="mail-x",
        argv=["/bin/true\ncommand=/x"],
        log_file=Path("/tmp/x.log"),
    )
    with pytest.raises(ValueError):
        SupervisorRenderer("bench", Path("/tmp")).render(pd)


def test_systemd_env_value_with_space_is_quoted() -> None:
    pd = ProcessDefinition(
        name="mail-x",
        argv=["/bin/true"],
        log_file=Path("/tmp/x.log"),
        env={"ARGS": "--flag one two"},
    )
    text = SystemdRenderer("bench").render(pd)
    # Quoted as one assignment, not split into stray tokens.
    assert 'Environment="ARGS=--flag one two"' in text


def test_supervisor_escapes_percent_and_quote() -> None:
    pd = ProcessDefinition(
        name="mail-x",
        argv=["/bin/foo", "--date=%Y"],
        log_file=Path("/tmp/x.log"),
        env={"MSG": 'a"b', "PCT": "50%"},
    )
    text = SupervisorRenderer("bench", Path("/tmp")).render(pd)
    assert "--date=%%Y" in text  # % doubled so supervisord won't expand it
    assert "%%" in text and "50%%" in text
    assert '\\"' in text  # embedded quote escaped
