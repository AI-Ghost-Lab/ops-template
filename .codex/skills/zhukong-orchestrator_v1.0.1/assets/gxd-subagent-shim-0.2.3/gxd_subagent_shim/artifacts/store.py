from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import DEFAULT_LOG_FILE, ShimConfig
from ..io import append_jsonl, ensure_dir, write_bytes, write_json, write_text
from ..util import (
    git_short,
    lock_file_handle,
    repo_info,
    sha256_text,
    unlock_file_handle,
    utc_compact_stamp,
    utc_now_iso,
)


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    run_dir: Path
    events_path: Path
    meta_path: Path


def _safe_decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _build_request_raw(
    *,
    action: str,
    backend: str,
    run_id: str,
    step_id: str,
    round_num: int,
    thread_id_in: str | None,
    prompt: str,
    payload: dict[str, Any] | None,
) -> str:
    payload_json = "null"
    if payload is not None:
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    lines = [
        "PARAMS",
        f"action: {action}",
        f"backend: {backend}",
        f"run_id: {run_id}",
        f"step_id: {step_id}",
        f"round: {round_num}",
        f"thread_id: {thread_id_in or 'null'}",
        "",
        "PROMPT",
        prompt.rstrip(),
        "",
        "REQUEST_JSON",
        payload_json,
    ]
    return "\n".join(lines).rstrip() + "\n"


def _build_output_md(output_text: str | None, run_result: Any | None) -> str | None:
    stderr_text = ""
    if run_result is not None and getattr(run_result, "stderr", b""):
        stderr_text = _safe_decode(run_result.stderr).strip()
    if output_text is None and not stderr_text:
        return None

    parts: list[str] = []
    if output_text is not None:
        parts.append(output_text.rstrip())
    if stderr_text:
        parts.append(f"stderror:\n```\n{stderr_text}\n```")
    return "\n\n".join(parts).rstrip() + "\n"


def artifacts_root(cfg: ShimConfig) -> Path:
    return cfg.artifacts_root


def find_existing_run_id(task_id: str, root: Path) -> str | None:
    if not task_id:
        return None
    if not root.exists():
        return None

    candidates: list[Path] = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        name = p.name
        if name == task_id or name.startswith(task_id + "_"):
            candidates.append(p)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0].name


def generate_run_id(task_id: str) -> str:
    base = task_id.strip() or "run"
    stamp = utc_compact_stamp()
    return f"{base}_{stamp}_{git_short()}"


def resolve_run_id(task_id: str | None, cli_run_id: str | None, env_run_id: str | None, root: Path) -> str:
    if cli_run_id and cli_run_id.strip():
        return cli_run_id.strip()
    if env_run_id and env_run_id.strip():
        return env_run_id.strip()

    if task_id:
        existing = find_existing_run_id(task_id, root)
        if existing:
            return existing
        return generate_run_id(task_id)

    return generate_run_id("run")


def ensure_run_initialized(run_dir: Path, run_id: str) -> RunPaths:
    """Best-effort run init: meta.json + events.jsonl. Never raises."""
    events_path = run_dir / "events.jsonl"
    meta_path = run_dir / "meta.json"

    try:
        ensure_dir(run_dir)
        if not meta_path.exists():
            meta = {
                "run_id": run_id,
                "created_at": utc_now_iso(),
                "repo": repo_info(),
                "policy": {"max_rework_rounds_per_step": 6},
            }
            write_json(meta_path, meta)
            append_jsonl(
                events_path,
                {
                    "ts": utc_now_iso(),
                    "run_id": run_id,
                    "event_id": uuid.uuid4().hex,
                    "kind": "run.init",
                    "data": {"meta_path": "meta.json"},
                },
            )
    except Exception:
        pass

    return RunPaths(run_id=run_id, run_dir=run_dir, events_path=events_path, meta_path=meta_path)


def _list_round_nums(rounds_dir: Path) -> list[int]:
    nums: list[int] = []
    if not rounds_dir.exists():
        return nums
    for p in rounds_dir.iterdir():
        if not p.is_dir():
            continue
        if p.name.startswith("R") and p.name[1:].isdigit():
            try:
                nums.append(int(p.name[1:]))
            except Exception:
                continue
    return nums


def next_round_num(rounds_dir: Path) -> int:
    nums = _list_round_nums(rounds_dir)
    return (max(nums) + 1) if nums else 0


def allocate_round_dir(run_dir: Path, step_id: str) -> tuple[int, Path] | None:
    """Allocate a new rounds/Rk directory using a staging-rename."""
    rounds_dir = run_dir / "steps" / step_id / "rounds"
    try:
        ensure_dir(rounds_dir)
        staging = rounds_dir / (".staging_" + uuid.uuid4().hex)
        ensure_dir(staging)

        for _ in range(20):
            rn = next_round_num(rounds_dir)
            target = rounds_dir / f"R{rn}"
            try:
                staging.rename(target)
                return rn, target
            except FileExistsError:
                continue
        return None
    except Exception:
        return None


def append_legacy_log(cfg: ShimConfig, entry: dict[str, Any]) -> None:
    if not cfg.legacy_log:
        return
    try:
        import json

        entry = dict(entry)
        entry["timestamp"] = utc_now_iso()
        ensure_dir(DEFAULT_LOG_FILE.parent)
        with DEFAULT_LOG_FILE.open("a", encoding="utf-8") as f:
            lock_file_handle(f)
            try:
                f.write(json.dumps(entry, ensure_ascii=False))
                f.write("\n")
            finally:
                unlock_file_handle(f)
    except Exception:
        return


def update_index(run_dir: Path) -> None:
    """Best-effort index.md generator."""
    try:
        from .index import build_index

        write_text(run_dir / "index.md", build_index(run_dir))
    except Exception:
        return


def record_call_start(
    *,
    cfg: ShimConfig,
    run_paths: RunPaths,
    action: str,
    backend: str,
    step_id: str,
    round_num: int,
    thread_id_in: str | None,
    prompt: str,
    payload: dict[str, Any] | None,
    prompt_parse_error: str | None,
) -> None:
    """Persist early artifacts + append a start event + legacy log."""
    try:
        steps_dir = run_paths.run_dir / "steps" / step_id / "rounds" / f"R{round_num}"
        ensure_dir(steps_dir)

        request_raw = _build_request_raw(
            action=action,
            backend=backend,
            run_id=run_paths.run_id,
            step_id=step_id,
            round_num=round_num,
            thread_id_in=thread_id_in,
            prompt=prompt,
            payload=payload,
        )
        write_text(steps_dir / "request_raw.txt", request_raw)
        if prompt_parse_error:
            write_text(steps_dir / "prompt_parse_error.txt", prompt_parse_error)

        request_json_path: Path | None = None
        if payload is not None:
            if action == "create":
                request_json_path = steps_dir / "create_request.json"
            else:
                if payload.get("feedback_kind") == "rework":
                    request_json_path = steps_dir / "rework_request.json"
                else:
                    request_json_path = steps_dir / "resume_request.json"
            write_json(request_json_path, payload)

        data: dict[str, Any] = {
            "dir": str(steps_dir.relative_to(run_paths.run_dir)),
            "request_raw": str((steps_dir / "request_raw.txt").relative_to(run_paths.run_dir)),
            "prompt_sha256": sha256_text(prompt),
            "prompt_len": len(prompt),
        }
        if request_json_path and request_json_path.exists():
            data["request_json"] = str(request_json_path.relative_to(run_paths.run_dir))
        if prompt_parse_error:
            data["prompt_parse_error"] = str((steps_dir / "prompt_parse_error.txt").relative_to(run_paths.run_dir))

        base_event = {
            "ts": utc_now_iso(),
            "run_id": run_paths.run_id,
            "event_id": uuid.uuid4().hex,
            "step_id": step_id,
            "round": round_num,
            "subagent_id": thread_id_in,
            "backend": backend,
            "model": None,
            "status": "started",
            "returncode": None,
            "duration_ms": None,
            "data": data,
        }
        append_jsonl(run_paths.events_path, dict(base_event, kind="step.start", action=action))

        append_legacy_log(
            cfg,
            {
                "phase": "start",
                "pid": os.getpid(),
                "action": action,
                "backend": backend,
                "run_id": run_paths.run_id,
                "step_id": step_id,
                "round": round_num,
                "thread_id": thread_id_in,
                "prompt_sha256": sha256_text(prompt),
                "prompt_len": len(prompt),
                "returncode": None,
                "duration_ms": None,
                "status": "started",
                "parse_error": None,
            },
        )

        update_index(run_paths.run_dir)
    except Exception:
        return


def record_abort(
    *,
    cfg: ShimConfig,
    run_paths: RunPaths,
    action: str,
    backend: str,
    step_id: str,
    round_num: int,
    thread_id_in: str | None,
    prompt: str,
    reason: str,
) -> None:
    """Persist abort artifacts + append abort event + legacy log."""
    try:
        steps_dir = run_paths.run_dir / "steps" / step_id / "rounds" / f"R{round_num}"
        ensure_dir(steps_dir)

        abort_path = steps_dir / "shim_abort.txt"
        write_text(abort_path, reason)

        data: dict[str, Any] = {
            "dir": str(steps_dir.relative_to(run_paths.run_dir)),
            "shim_abort": str(abort_path.relative_to(run_paths.run_dir)),
        }

        base_event = {
            "ts": utc_now_iso(),
            "run_id": run_paths.run_id,
            "event_id": uuid.uuid4().hex,
            "step_id": step_id,
            "round": round_num,
            "subagent_id": thread_id_in,
            "backend": backend,
            "model": None,
            "status": "aborted",
            "returncode": None,
            "duration_ms": None,
            "data": data,
        }
        append_jsonl(run_paths.events_path, dict(base_event, kind="step.abort", action=action, reason=reason))

        append_legacy_log(
            cfg,
            {
                "phase": "abort",
                "pid": os.getpid(),
                "action": action,
                "backend": backend,
                "run_id": run_paths.run_id,
                "step_id": step_id,
                "round": round_num,
                "thread_id": thread_id_in,
                "prompt_sha256": sha256_text(prompt),
                "prompt_len": len(prompt),
                "returncode": None,
                "duration_ms": None,
                "status": "aborted",
                "error": reason,
                "parse_error": None,
            },
        )

        update_index(run_paths.run_dir)
    except Exception:
        return


def record_call(
    *,
    cfg: ShimConfig,
    run_paths: RunPaths,
    action: str,
    backend: str,
    step_id: str,
    round_num: int,
    thread_id_in: str | None,
    prompt: str,
    payload: dict[str, Any] | None,
    prompt_parse_error: str | None,
    run_result: Any | None,
    error: str | None,
    resolved_thread_id: str | None,
    model: str | None,
    output_text: str | None,
    parse_error: str | None,
) -> None:
    """Persist per-call artifacts + append events.jsonl + legacy log.

    Best-effort: never raises.
    """
    try:
        steps_dir = run_paths.run_dir / "steps" / step_id / "rounds" / f"R{round_num}"
        ensure_dir(steps_dir)

        request_raw = _build_request_raw(
            action=action,
            backend=backend,
            run_id=run_paths.run_id,
            step_id=step_id,
            round_num=round_num,
            thread_id_in=thread_id_in,
            prompt=prompt,
            payload=payload,
        )
        write_text(steps_dir / "request_raw.txt", request_raw)
        if prompt_parse_error:
            write_text(steps_dir / "prompt_parse_error.txt", prompt_parse_error)

        request_json_path: Path | None = None
        if payload is not None:
            if action == "create":
                request_json_path = steps_dir / "create_request.json"
            else:
                if payload.get("feedback_kind") == "rework":
                    request_json_path = steps_dir / "rework_request.json"
                else:
                    request_json_path = steps_dir / "resume_request.json"
            write_json(request_json_path, payload)

        if cfg.save_raw_io and run_result is not None:
            if getattr(run_result, "stdout", b""):
                stdout_path = steps_dir / "shim_stdout.txt"
                if not stdout_path.exists():
                    write_bytes(stdout_path, run_result.stdout)
            if getattr(run_result, "stderr", b""):
                stderr_path = steps_dir / "shim_stderr.txt"
                if not stderr_path.exists():
                    write_bytes(stderr_path, run_result.stderr)

        if run_result is not None and getattr(run_result, "parsed_json", None) is not None:
            write_json(steps_dir / "shim_response.json", run_result.parsed_json)

        output_md_path = steps_dir / "subagent_output.md"
        output_md = _build_output_md(output_text, run_result)
        if output_md is not None and not output_md_path.exists():
            write_text(output_md_path, output_md)

        if error:
            write_text(steps_dir / "shim_error.txt", error)

        data: dict[str, Any] = {
            "dir": str(steps_dir.relative_to(run_paths.run_dir)),
            "request_raw": str((steps_dir / "request_raw.txt").relative_to(run_paths.run_dir)),
        }
        if request_json_path and request_json_path.exists():
            data["request_json"] = str(request_json_path.relative_to(run_paths.run_dir))
        for fname, key in [
            ("prompt_parse_error.txt", "prompt_parse_error"),
            ("shim_response.json", "response_json"),
            ("subagent_output.md", "output_md"),
            ("shim_stdout.txt", "stdout_path"),
            ("shim_stderr.txt", "stderr_path"),
            ("shim_abort.txt", "shim_abort"),
            ("shim_error.txt", "shim_error"),
        ]:
            fp = steps_dir / fname
            if fp.exists():
                data[key] = str(fp.relative_to(run_paths.run_dir))

        status = "success"
        returncode = getattr(run_result, "returncode", None)
        duration_ms = getattr(run_result, "duration_ms", None)
        if error:
            status = "shim_error"
        elif returncode is not None and int(returncode) != 0:
            status = "backend_error"

        base_event = {
            "ts": utc_now_iso(),
            "run_id": run_paths.run_id,
            "event_id": uuid.uuid4().hex,
            "step_id": step_id,
            "round": round_num,
            "subagent_id": resolved_thread_id,
            "backend": backend,
            "model": model,
            "status": status,
            "returncode": returncode,
            "duration_ms": duration_ms,
            "data": data,
        }

        if action == "create":
            append_jsonl(run_paths.events_path, dict(base_event, kind="step.create"))
            append_jsonl(run_paths.events_path, dict(base_event, kind="step.output"))
        else:
            if payload is not None and payload.get("feedback_kind") == "rework":
                append_jsonl(run_paths.events_path, dict(base_event, kind="step.rework"))
            append_jsonl(run_paths.events_path, dict(base_event, kind="step.resume"))
            append_jsonl(run_paths.events_path, dict(base_event, kind="step.output"))

        append_legacy_log(
            cfg,
            {
                "action": action,
                "backend": backend,
                "run_id": run_paths.run_id,
                "step_id": step_id,
                "round": round_num,
                "thread_id": resolved_thread_id,
                "prompt_sha256": sha256_text(prompt),
                "prompt_len": len(prompt),
                "returncode": returncode,
                "duration_ms": duration_ms,
                "status": status,
                "parse_error": parse_error,
            },
        )

        update_index(run_paths.run_dir)
    except Exception:
        return
