from __future__ import annotations

import json
import re
from typing import Any


def extract_json_candidate(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None

    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        return s

    obj_start = s.find("{")
    obj_end = s.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        return s[obj_start : obj_end + 1]

    arr_start = s.find("[")
    arr_end = s.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        return s[arr_start : arr_end + 1]

    return None


_JSON_START_RE = re.compile(r"[{\[]")


def _scan_json_objects(text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    objs: list[Any] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch not in "{[":
            m = _JSON_START_RE.search(text, i)
            if not m:
                break
            i = m.start()
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        objs.append(obj)
        i = end
    return objs


def try_parse_json(text: str) -> tuple[Any | None, str | None]:
    cand = extract_json_candidate(text)
    if cand is None:
        return None, None
    try:
        return json.loads(cand), None
    except Exception as e:
        objs = _scan_json_objects(cand)
        if objs:
            return objs, None
        return None, f"{type(e).__name__}: {e}"


def parse_prompt_payload(prompt: str) -> tuple[dict[str, Any] | None, str | None]:
    payload_any, err = try_parse_json(prompt)
    if isinstance(payload_any, dict):
        return payload_any, err
    return None, err


_TASK_ID_RE = re.compile(r'["\']task_id["\']\s*:\s*["\']([^"\']+)["\']')
_STEP_ID_RE = re.compile(r'["\']step_id["\']\s*:\s*["\']([^"\']+)["\']')


def looks_like_placeholder(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if "<" in v or ">" in v:
        return True
    if "{{" in v or "}}" in v:
        return True
    return False


def regex_extract_ids(prompt: str) -> tuple[str | None, str | None]:
    """Best-effort extraction when JSON parsing fails."""
    s = prompt or ""
    task_id: str | None = None
    step_id: str | None = None

    m = _TASK_ID_RE.search(s)
    if m:
        cand = (m.group(1) or "").strip()
        if cand and not looks_like_placeholder(cand):
            task_id = cand

    m = _STEP_ID_RE.search(s)
    if m:
        cand = (m.group(1) or "").strip()
        if cand and not looks_like_placeholder(cand):
            step_id = cand

    return task_id, step_id
