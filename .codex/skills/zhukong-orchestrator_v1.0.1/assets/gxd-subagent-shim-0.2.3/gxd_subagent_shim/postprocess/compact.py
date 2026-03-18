from __future__ import annotations

import json
from typing import Any

from ..io import extract_model, extract_text_output, extract_thread_id, try_parse_json


_KEEP_ITEM_TYPES = {
    "reasoning",
    "agent_message",
    "message",
    "final",
    "output_text",
    "assistant_message",
}


def _compact_codex_event(event: dict[str, Any], raw_line: str | None = None) -> list[str]:
    etype = event.get("type")
    if not isinstance(etype, str):
        return []

    if etype == "thread.started":
        if raw_line is not None:
            return [raw_line.strip()]
        return [json.dumps(event, ensure_ascii=False)]

    if etype != "item.completed":
        return ["."]

    item = event.get("item")
    if not isinstance(item, dict):
        return ["."]
    item_type = item.get("type")
    if not isinstance(item_type, str):
        return ["."]
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id:
        item_id = "item"

    if item_type == "todo_list":
        return _format_todo_list(item_id, item)

    if item_type not in _KEEP_ITEM_TYPES:
        return ["."]
    text = _extract_item_text(item)
    if not text:
        return ["."]
    return [f"{item_id}:{text}"]


def _extract_item_text(item: dict[str, Any]) -> str | None:
    text = item.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    content = item.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                ptext = part.get("text")
                if isinstance(ptext, str) and ptext.strip():
                    parts.append(ptext.strip())
            elif isinstance(part, str) and part.strip():
                parts.append(part.strip())
        if parts:
            return "\n".join(parts)

    return None


def _format_todo_list(item_id: str, item: dict[str, Any]) -> list[str]:
    lines = [f"{item_id}:todo_list"]
    items = item.get("items")
    if isinstance(items, list):
        for entry in items:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            mark = "x" if bool(entry.get("completed")) else " "
            lines.append(f"- [{mark}] {text.strip()}")
    return lines


def _compact_codex_event_stream(
    events: list[dict[str, Any]],
    raw_lines: list[str] | None = None,
) -> str | None:
    out_lines: list[str] = []
    dot_run = 0
    for idx, event in enumerate(events):
        if not isinstance(event, dict):
            return None
        raw_line = raw_lines[idx].strip() if raw_lines is not None and idx < len(raw_lines) else None
        lines = _compact_codex_event(event, raw_line)
        for line in lines:
            if line == ".":
                dot_run += 1
                continue
            if dot_run:
                out_lines.append("." * dot_run)
                dot_run = 0
            out_lines.append(line)

    if dot_run:
        out_lines.append("." * dot_run)
    if not out_lines:
        return None
    return "\n".join(out_lines).strip()


def _compact_codex_event_payload(payload: Any) -> str | None:
    if isinstance(payload, list) and payload:
        if all(isinstance(ev, dict) and isinstance(ev.get("type"), str) for ev in payload):
            return _compact_codex_event_stream(payload)
    return None


def _compact_codex_event_text(text: str) -> str | None:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            return None
        if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
            return None
        events.append(obj)
    return _compact_codex_event_stream(events, raw_lines=lines)


def compact_codex_events(stdout_bytes: bytes) -> tuple[bytes | None, bool]:
    """Return compacted codex JSONL event output when detected."""
    try:
        text = stdout_bytes.decode("utf-8", errors="replace")
        payload, _err = try_parse_json(text)
        if payload is not None:
            compacted = _compact_codex_event_payload(payload)
        else:
            compacted = _compact_codex_event_text(text)
        if compacted:
            return (compacted + "\n").encode("utf-8"), True
        return None, False
    except Exception:
        return None, False


class CodexEventStreamCompactor:
    def __init__(self, writer) -> None:
        self._writer = writer
        self._buf = ""
        self._mode = "auto"  # auto|codex|raw
        self._dot_active = False

    def feed(self, data: bytes) -> None:
        if not data:
            return
        text = data.decode("utf-8", errors="replace")
        self._buf += text
        while True:
            idx = self._buf.find("\n")
            if idx == -1:
                break
            line = self._buf[:idx]
            self._buf = self._buf[idx + 1 :]
            self._handle_line(line)

    def close(self) -> None:
        if self._buf:
            self._handle_line(self._buf)
            self._buf = ""
        self._flush_dot_line()

    def _handle_line(self, line: str) -> None:
        raw = line.rstrip("\r")
        if not raw.strip():
            return

        if self._mode == "raw":
            self._emit([raw.strip()])
            return

        event = _parse_codex_event_line(raw)
        if event is None:
            self._mode = "raw"
            self._emit([raw.strip()])
            return

        self._mode = "codex"
        self._emit(_compact_codex_event(event, raw))

    def _emit(self, lines: list[str]) -> None:
        if not lines:
            return
        if self._mode == "raw":
            self._flush_dot_line()
            self._write_payload("\n".join(lines) + "\n")
            return
        for line in lines:
            if line == ".":
                self._write_payload(".")
                self._dot_active = True
                continue
            self._flush_dot_line()
            self._write_payload(f"{line}\n")

    def _flush_dot_line(self) -> None:
        if not self._dot_active:
            return
        self._write_payload("\n")
        self._dot_active = False

    def _write_payload(self, payload: str) -> None:
        try:
            self._writer(payload.encode("utf-8"))
        except Exception:
            pass


def _parse_codex_event_line(line: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(line.strip())
    except Exception:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("type"), str):
        return None
    return obj


def _compact_json(payload: Any, profile: str) -> dict[str, Any]:
    """Return a smaller JSON object. Caller decides whether to print it."""
    thread_id = extract_thread_id(payload)
    model = extract_model(payload)
    out_text = extract_text_output(payload)

    env: dict[str, Any] = {
        "thread_id": thread_id,
        "model": model,
        "output_text": out_text,
    }

    if profile in ("codex", "claude", "copilot"):
        if isinstance(payload, dict):
            for k in ("id", "created", "type", "status"):
                if k in payload and k not in env:
                    env[k] = payload.get(k)

    return env


def _compact_plaintext(text: str, max_chars: int = 10000, max_lines: int = 200) -> str:
    t = (text or "").strip()
    if not t:
        return t
    lines = t.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    t2 = "\n".join(lines)
    if len(t2) > max_chars:
        t2 = t2[-max_chars:]
    return t2


def compact_stdout(stdout_bytes: bytes, profile: str = "auto") -> tuple[bytes, bool]:
    """Best-effort compaction.

    Returns (bytes, did_compact). Never raises.
    """
    try:
        text = stdout_bytes.decode("utf-8", errors="replace")
        payload, _err = try_parse_json(text)
        if payload is not None:
            prof = profile if profile != "auto" else "codex"
            if prof == "codex":
                compacted_events = _compact_codex_event_payload(payload)
                if compacted_events:
                    return (compacted_events + "\n").encode("utf-8"), True
            compacted = _compact_json(payload, prof)
            out = json.dumps(compacted, ensure_ascii=False)
            return (out + "\n").encode("utf-8"), True

        if profile in ("auto", "codex"):
            compacted_events = _compact_codex_event_text(text)
            if compacted_events:
                return (compacted_events + "\n").encode("utf-8"), True

        trimmed = _compact_plaintext(text)
        return (trimmed + "\n").encode("utf-8"), True
    except Exception:
        return stdout_bytes, False
