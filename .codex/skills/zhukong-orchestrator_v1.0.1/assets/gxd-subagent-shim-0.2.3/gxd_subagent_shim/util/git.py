from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git(args: list[str]) -> str | None:
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    out = (p.stdout or "").strip()
    return out or None


def repo_info() -> dict[str, Any]:
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    commit = _git(["rev-parse", "HEAD"])
    short = _git(["rev-parse", "--short", "HEAD"])

    dirty = None
    st = _git(["status", "--porcelain"])
    if st is not None:
        dirty = bool(st.strip())

    return {
        "path": str(Path.cwd()),
        "branch": branch,
        "commit": commit,
        "commit_short": short,
        "dirty": dirty,
    }


def git_short() -> str:
    return _git(["rev-parse", "--short", "HEAD"]) or "nogit"
