from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# -------------------- DEFAULTS --------------------

DEFAULT_LOG_FILE = Path("subagent.log")
DEFAULT_ARTIFACTS_ROOT = Path(".artifacts") / "agent_runs"

# -------------------- ENV VARS --------------------

ENV_BACKEND = "SUBAGENT_BACKEND"
ENV_RUN_ID = "SUBAGENT_RUN_ID"
ENV_ARTIFACTS_ROOT = "SUBAGENT_ARTIFACTS_ROOT"

ENV_CODEX_BIN = "CODEX_BIN"      # default: codex
ENV_CLAUDE_BIN = "CLAUDE_BIN"    # default: claude

ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_ANTHROPIC_AUTH_TOKEN = "ANTHROPIC_AUTH_TOKEN"

# If set to 1, also store backend raw stdout/stderr alongside parsed json.
ENV_SAVE_RAW_IO = "SUBAGENT_SAVE_RAW_IO"   # default: 1

# If set to 0, do not write legacy subagent.log at repo root.
ENV_LEGACY_LOG = "SUBAGENT_LEGACY_LOG"     # default: 1

# Optional strict validation
ENV_VALIDATE_INPUT = "SUBAGENT_VALIDATE_INPUT"   # default: 0
ENV_VALIDATE_OUTPUT = "SUBAGENT_VALIDATE_OUTPUT" # default: 0

# Optional stdout post-processing
ENV_STDOUT_MODE = "SUBAGENT_STDOUT_MODE"         # raw|compact, default: raw
ENV_COMPACT_PROFILE = "SUBAGENT_COMPACT_PROFILE" # auto|codex|claude|copilot


def bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y", "on")


def str_env(name: str, default: str | None = None) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip()
    return v if v else default


@dataclass(frozen=True)
class ShimConfig:
    artifacts_root: Path
    save_raw_io: bool
    legacy_log: bool
    validate_input: bool
    validate_output: bool
    stdout_mode: str
    compact_profile: str


def load_config() -> ShimConfig:
    root = str_env(ENV_ARTIFACTS_ROOT)
    artifacts_root = Path(root) if root else DEFAULT_ARTIFACTS_ROOT

    save_raw_io = bool_env(ENV_SAVE_RAW_IO, default=True)
    legacy_log = bool_env(ENV_LEGACY_LOG, default=True)

    validate_input = bool_env(ENV_VALIDATE_INPUT, default=False)
    validate_output = bool_env(ENV_VALIDATE_OUTPUT, default=False)

    stdout_mode = (str_env(ENV_STDOUT_MODE, default="raw") or "raw").strip().lower()
    compact_profile = (str_env(ENV_COMPACT_PROFILE, default="auto") or "auto").strip().lower()

    if stdout_mode not in ("raw", "compact"):
        stdout_mode = "raw"
    if compact_profile not in ("auto", "codex", "claude", "copilot"):
        compact_profile = "auto"

    return ShimConfig(
        artifacts_root=artifacts_root,
        save_raw_io=save_raw_io,
        legacy_log=legacy_log,
        validate_input=validate_input,
        validate_output=validate_output,
        stdout_mode=stdout_mode,
        compact_profile=compact_profile,
    )
