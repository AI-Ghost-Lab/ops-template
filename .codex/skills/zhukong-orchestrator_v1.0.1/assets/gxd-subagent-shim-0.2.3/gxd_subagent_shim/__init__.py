"""gxd_subagent_shim package.

Stdlib-only runner shim for codex / claude-code style backends.

Design goals:
- Keep create/resume working even if audit writing fails.
- Provide pluggable validation and post-processing hooks.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "2.0.0-refactor"
