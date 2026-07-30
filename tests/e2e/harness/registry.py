"""A local marketplace registry for the bench under test to clone."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def build_registry(root: Path) -> Path:
    """Create an empty registry repo and return its path.

    The bench clones this instead of the public marketplace: the run then needs
    no network for the catalog, and cannot break when the public registry's
    format moves. Empty is deliberate - the lifecycle spec imports an app from a
    repo, so every app it touches belongs under "Custom Apps".
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "apps.json").write_text(json.dumps([], indent=2) + "\n")
    (root / "apps").mkdir(exist_ok=True)
    (root / "apps" / ".gitkeep").write_text("")

    if not (root / ".git").is_dir():
        _git(root, "init", "-q", "-b", "main")
        _git(root, "config", "user.email", "e2e@example.com")
        _git(root, "config", "user.name", "e2e")
    _git(root, "add", "-A")
    if _git(root, "status", "--porcelain").stdout.strip():
        _git(root, "commit", "-q", "-m", "e2e registry")
    return root


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)
