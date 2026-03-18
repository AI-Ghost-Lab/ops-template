from __future__ import annotations

import re
from typing import Any, Iterable


def deep_find_first_str(obj: Any, keys: Iterable[str]) -> str | None:
    """DFS: find the first string value for any key in keys."""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            s = deep_find_first_str(v, keys)
            if s:
                return s
    elif isinstance(obj, list):
        for it in obj:
            s = deep_find_first_str(it, keys)
            if s:
                return s
    return None


def extract_thread_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for k in ("thread_id", "threadId", "session_id", "sessionId", "id"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        nested = payload.get("thread") or payload.get("session")
        if isinstance(nested, dict):
            for k in ("id", "thread_id", "session_id"):
                v = nested.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return None


def extract_model(payload: Any) -> str | None:
    return deep_find_first_str(payload, keys=("model", "model_name", "modelName"))


def extract_text_output(payload: Any) -> str | None:
    """Heuristic extraction of human-visible assistant output."""
    direct = deep_find_first_str(payload, keys=("output_text", "output", "text", "completion", "final", "answer"))
    if direct:
        return direct

    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list):
            parts: list[str] = []
            for c in choices:
                if not isinstance(c, dict):
                    continue
                msg = c.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str) and content.strip():
                        parts.append(content.strip())
                t = c.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t.strip())
            if parts:
                return "\n\n".join(parts).strip()

    return None


_THREAD_ID_RE = re.compile(r"\bthread_id\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-]+)['\"]?")


def regex_extract_thread_id(text: str) -> str | None:
    """Best-effort thread_id extraction from raw text (when JSON parse fails)."""
    m = _THREAD_ID_RE.search(text or "")
    if not m:
        return None
    v = (m.group(1) or "").strip()
    return v if v else None
