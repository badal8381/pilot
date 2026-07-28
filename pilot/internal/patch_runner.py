from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Progress = Callable[[str], None]

_PHASES = ("pre_update", "post_update")
PATCHES_DIR = Path(__file__).parent.parent / "patches"
PATCHES_TXT = PATCHES_DIR / "patches.txt"


def patch_names(phase: str) -> list[str]:
    """Patch names listed under [phase] in patches.txt, in file order."""
    if phase not in _PHASES:
        raise ValueError(f"Unknown patch phase: {phase!r}. Must be one of {_PHASES}.")
    names: list[str] = []
    current: str | None = None
    for raw_line in PATCHES_TXT.read_text().splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            continue
        if current == phase:
            names.append(line)
    return names


def run_patches(phase: str, on_progress: Progress = lambda message: None) -> None:
    """Run every patch listed under `phase` ("pre_update", "post_update", or "all")."""
    phases = _PHASES if phase == "all" else (phase,)
    for one_phase in phases:
        for name in patch_names(one_phase):
            _run_one(name, on_progress)


def _run_one(name: str, on_progress: Progress) -> None:
    patch_file = PATCHES_DIR / f"{name}.py"
    if not patch_file.exists():
        on_progress(f"Skipping '{name}': no such patch file ({patch_file}).")
        return
    on_progress(f"Running patch '{name}'...")
    subprocess.run([sys.executable, str(patch_file)], check=True)
