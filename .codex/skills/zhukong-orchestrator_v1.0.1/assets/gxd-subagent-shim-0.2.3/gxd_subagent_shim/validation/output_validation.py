from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..io import extract_thread_id, regex_extract_thread_id


@dataclass(frozen=True)
class OutputValidationResult:
    ok: bool
    error: str | None
    thread_id: str | None


def validate_backend_output(
    *,
    action: str,
    parsed_json: Any | None,
    raw_stdout_text: str,
    thread_id_in: str | None,
    strict: bool = False,
) -> OutputValidationResult:
    """Validate backend output.

    When strict=False, always ok (but still tries to extract thread_id).
    When strict=True:
      - requires parseable JSON;
      - for create: requires a thread_id in output.
    """
    extracted = extract_thread_id(parsed_json) if parsed_json is not None else None
    if not extracted:
        extracted = regex_extract_thread_id(raw_stdout_text)
    if not extracted:
        extracted = thread_id_in

    if not strict:
        return OutputValidationResult(ok=True, error=None, thread_id=extracted)

    if parsed_json is None:
        return OutputValidationResult(ok=False, error="backend stdout is not valid JSON", thread_id=extracted)

    if action == "create" and not extracted:
        return OutputValidationResult(ok=False, error="missing thread_id in create response", thread_id=None)

    return OutputValidationResult(ok=True, error=None, thread_id=extracted)
