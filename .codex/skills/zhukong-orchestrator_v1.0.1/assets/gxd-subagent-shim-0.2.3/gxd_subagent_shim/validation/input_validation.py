from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..io import parse_prompt_payload


@dataclass(frozen=True)
class InputValidationResult:
    ok: bool
    error: str | None
    payload: dict[str, Any] | None
    parse_error: str | None


def validate_prompt(prompt: str, strict: bool = False) -> InputValidationResult:
    payload, parse_err = parse_prompt_payload(prompt)

    if not strict:
        return InputValidationResult(ok=True, error=None, payload=payload, parse_error=parse_err)

    if payload is None:
        return InputValidationResult(
            ok=False,
            error="prompt must be a JSON object when SUBAGENT_VALIDATE_INPUT=1",
            payload=None,
            parse_error=parse_err,
        )

    task_id = payload.get("task_id")
    step_id = payload.get("step_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return InputValidationResult(ok=False, error="missing/invalid task_id", payload=payload, parse_error=parse_err)
    if not isinstance(step_id, str) or not step_id.strip():
        return InputValidationResult(ok=False, error="missing/invalid step_id", payload=payload, parse_error=parse_err)

    return InputValidationResult(ok=True, error=None, payload=payload, parse_error=parse_err)
