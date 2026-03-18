from __future__ import annotations

import os
import signal
import sys
import threading

from .artifacts import (
    allocate_round_dir,
    artifacts_root,
    ensure_run_initialized,
    record_abort,
    record_call,
    record_call_start,
    resolve_run_id,
)
from .backend import build_backend_cmd, resolve_backend, run_capture, safe_decode
from .config import ENV_RUN_ID, ShimConfig, load_config
from .io import ensure_dir, extract_model, extract_thread_id, regex_extract_ids
from .postprocess import CodexEventStreamCompactor, compact_codex_events, compact_stdout
from .validation import validate_backend_output, validate_prompt


def _extract_flag_value(args: list[str], flag: str) -> tuple[str | None, list[str]]:
    """Extract --flag value and --flag=value forms (last wins). Removes them from args."""
    out: list[str] = []
    value: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == flag:
            if i + 1 >= len(args):
                raise SystemExit(2)
            value = args[i + 1]
            i += 2
            continue
        prefix = flag + "="
        if a.startswith(prefix):
            value = a[len(prefix) :]
            i += 1
            continue
        out.append(a)
        i += 1
    return value, out


def _parse_cli(argv: list[str]) -> tuple[str, str | None, str | None, str | None, list[str]]:
    """Returns: (backend, run_id, task_id_override, step_id_override, remaining_args)."""
    backend1, rest = _extract_flag_value(list(argv), "--backend")
    backend2, rest = _extract_flag_value(rest, "-b")
    backend = resolve_backend(backend2 or backend1)

    run1, rest = _extract_flag_value(rest, "--run-id")
    run2, rest = _extract_flag_value(rest, "-r")
    run_id = run2 or run1

    t1, rest = _extract_flag_value(rest, "--task-id")
    s1, rest = _extract_flag_value(rest, "--step-id")

    return backend, run_id, t1, s1, rest


def _safe_next_round_num(run_dir, step_id: str) -> int:
    rounds_dir = run_dir / "steps" / step_id / "rounds"
    try:
        if not rounds_dir.exists():
            return 0
        nums = []
        for d in rounds_dir.iterdir():
            if not d.is_dir():
                continue
            name = d.name
            if name.startswith("R") and name[1:].isdigit():
                nums.append(int(name[1:]))
        return (max(nums) + 1) if nums else 0
    except Exception:
        return 0


def _stderr(msg: str) -> None:
    sys.stderr.write(msg.rstrip() + "\n")
    sys.stderr.flush()


class _OutputMerger:
    def __init__(self, path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._fh = None

    def write(self, data: bytes) -> None:
        if not data:
            return
        with self._lock:
            if self._fh is None:
                ensure_dir(self._path.parent)
                self._fh = self._path.open("ab", buffering=0)
            self._fh.write(data)
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                finally:
                    self._fh = None


def main(argv: list[str]) -> int:
    cfg: ShimConfig = load_config()
    backend, cli_run_id, cli_task_id, cli_step_id, args = _parse_cli(argv)

    if not args:
        _stderr("usage: gxd_subagent_shim (create|resume) <prompt> [thread_id] [--backend=...] [--run-id=...]")
        return 2

    cmd = args[0]
    if cmd not in ("create", "resume"):
        _stderr("error: command must be 'create' or 'resume'")
        return 2

    if cmd == "create":
        if len(args) != 2:
            _stderr("error: create requires exactly 1 argument: <prompt>")
            return 2
        prompt = args[1]
        thread_id_in = None
    else:
        if len(args) != 3:
            _stderr("error: resume requires exactly 2 arguments: <prompt> <thread_id>")
            return 2
        prompt = args[1]
        thread_id_in = args[2]

    in_val = validate_prompt(prompt, strict=cfg.validate_input)
    if not in_val.ok:
        _stderr(f"error: invalid input: {in_val.error}")
        return 2

    payload = in_val.payload
    payload_err = in_val.parse_error

    rx_task_id, rx_step_id = regex_extract_ids(prompt)

    task_id_any: str | None = None
    if isinstance(cli_task_id, str) and cli_task_id.strip():
        task_id_any = cli_task_id.strip()
    elif payload and isinstance(payload.get("task_id"), str) and str(payload.get("task_id")).strip():
        task_id_any = str(payload.get("task_id")).strip()
    elif isinstance(rx_task_id, str) and rx_task_id.strip():
        task_id_any = rx_task_id.strip()

    step_id_any: str | None = None
    if isinstance(cli_step_id, str) and cli_step_id.strip():
        step_id_any = cli_step_id.strip()
    elif payload and isinstance(payload.get("step_id"), str) and str(payload.get("step_id")).strip():
        step_id_any = str(payload.get("step_id")).strip()
    elif isinstance(rx_step_id, str) and rx_step_id.strip():
        step_id_any = rx_step_id.strip()

    step_id = step_id_any or "S_UNKNOWN"

    root = artifacts_root(cfg)
    env_run_id = os.getenv(ENV_RUN_ID)
    run_id = resolve_run_id(task_id_any, cli_run_id, env_run_id, root)
    run_dir = root / run_id

    run_paths = ensure_run_initialized(run_dir, run_id)

    alloc = allocate_round_dir(run_dir, step_id)
    if alloc is None:
        round_num = _safe_next_round_num(run_dir, step_id)
        steps_dir = run_dir / "steps" / step_id / "rounds" / f"R{round_num}"
        ensure_dir(steps_dir)
    else:
        round_num, steps_dir = alloc

    abort_reason: str | None = None
    exit_code_override: int | None = None

    def _signal_name(signum: int) -> str:
        try:
            return signal.Signals(signum).name
        except Exception:
            return str(signum)

    def _handle_signal(signum, _frame) -> None:
        nonlocal abort_reason
        abort_reason = f"signal:{_signal_name(signum)}"
        raise KeyboardInterrupt

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except Exception:
            pass

    run_result = None
    shim_error: str | None = None
    streamed_output = False
    runtime_stdout_chunks: list[bytes] = []
    runtime_stderr_chunks: list[bytes] = []
    output_merger = _OutputMerger(steps_dir / "subagent_output.md")

    def _emit(stdout_b: bytes, stderr_b: bytes) -> None:
        if stdout_b:
            sys.stdout.buffer.write(stdout_b)
            sys.stdout.buffer.flush()
            runtime_stdout_chunks.append(stdout_b)
            output_merger.write(stdout_b)
        if stderr_b:
            sys.stderr.buffer.write(stderr_b)
            sys.stderr.buffer.flush()
            runtime_stderr_chunks.append(stderr_b)
            output_merger.write(stderr_b)

    try:
        record_call_start(
            cfg=cfg,
            run_paths=run_paths,
            action=cmd,
            backend=backend,
            step_id=step_id,
            round_num=round_num,
            thread_id_in=thread_id_in,
            prompt=prompt,
            payload=payload,
            prompt_parse_error=payload_err,
        )
    except KeyboardInterrupt:
        reason = abort_reason or "KeyboardInterrupt"
        shim_error = reason
        exit_code_override = 130
        try:
            record_abort(
                cfg=cfg,
                run_paths=run_paths,
                action=cmd,
                backend=backend,
                step_id=step_id,
                round_num=round_num,
                thread_id_in=thread_id_in,
                prompt=prompt,
                reason=reason,
            )
        except Exception:
            pass
    except Exception:
        pass

    if shim_error is None:
        try:
            cmdline = build_backend_cmd(backend, cmd, prompt, thread_id_in)
            _stderr("The subagent is processing. Please be patient and do not terminate the program.")
            _stderr("This process may take 40 minutes or longer before producing any output.")
            _stderr("Do NOT exit or interrupt the program while it is running.")
            stdout_path = None
            stderr_path = None
            if cfg.save_raw_io:
                stdout_path = steps_dir / "shim_stdout.txt"
                stderr_path = steps_dir / "shim_stderr.txt"
            stdout_chunk_cb = None
            stderr_chunk_cb = None
            stdout_close_cb = None
            stderr_close_cb = None
            if backend == "codex":
                (steps_dir / "subagent_output.md").write_bytes(b"")

                def _write_stdout(data: bytes) -> None:
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                        runtime_stdout_chunks.append(data)
                        output_merger.write(data)

                def _write_stderr(data: bytes) -> None:
                    if data:
                        sys.stderr.buffer.write(data)
                        sys.stderr.buffer.flush()
                        runtime_stderr_chunks.append(data)
                        output_merger.write(data)

                stream_compactor = CodexEventStreamCompactor(_write_stdout)
                stdout_chunk_cb = stream_compactor.feed
                stdout_close_cb = stream_compactor.close
                stderr_chunk_cb = _write_stderr
                streamed_output = True

            run_result = run_capture(
                cmdline,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                stdout_chunk_cb=stdout_chunk_cb,
                stderr_chunk_cb=stderr_chunk_cb,
                stdout_close_cb=stdout_close_cb,
                stderr_close_cb=stderr_close_cb,
            )
        except KeyboardInterrupt:
            reason = abort_reason or "KeyboardInterrupt"
            shim_error = reason
            exit_code_override = 130
            try:
                record_abort(
                    cfg=cfg,
                    run_paths=run_paths,
                    action=cmd,
                    backend=backend,
                    step_id=step_id,
                    round_num=round_num,
                    thread_id_in=thread_id_in,
                    prompt=prompt,
                    reason=reason,
                )
            except Exception:
                pass
        except Exception as e:
            shim_error = f"{type(e).__name__}: {e}"
        finally:
            output_merger.close()

    if run_result is not None and not streamed_output:
        compacted = None
        if backend == "codex":
            compacted, ok = compact_codex_events(run_result.stdout)
            if ok and compacted is not None:
                _emit(compacted, run_result.stderr)
            else:
                compacted = None

        if compacted is None:
            if cfg.stdout_mode == "raw":
                _emit(run_result.stdout, run_result.stderr)
            else:
                compacted, ok = compact_stdout(run_result.stdout, profile=cfg.compact_profile)
                if ok:
                    _emit(compacted, run_result.stderr)
                else:
                    _emit(run_result.stdout, run_result.stderr)

    raw_stdout_text = safe_decode(run_result.stdout) if run_result is not None else ""
    parsed_json = getattr(run_result, "parsed_json", None) if run_result is not None else None

    resolved_thread_id = extract_thread_id(parsed_json) if parsed_json is not None else None
    if not resolved_thread_id:
        resolved_thread_id = thread_id_in

    model = extract_model(parsed_json) if parsed_json is not None else None
    runtime_stdout_text = safe_decode(b"".join(runtime_stdout_chunks)).rstrip()
    output_text = runtime_stdout_text if runtime_stdout_text else None
    if not output_text:
        output_text = raw_stdout_text.strip() or None

    out_val = validate_backend_output(
        action=cmd,
        parsed_json=parsed_json,
        raw_stdout_text=raw_stdout_text,
        thread_id_in=thread_id_in,
        strict=cfg.validate_output,
    )

    try:
        record_call(
            cfg=cfg,
            run_paths=run_paths,
            action=cmd,
            backend=backend,
            step_id=step_id,
            round_num=round_num,
            thread_id_in=thread_id_in,
            prompt=prompt,
            payload=payload,
            prompt_parse_error=payload_err,
            run_result=run_result,
            error=shim_error or (None if out_val.ok else f"OutputValidationError: {out_val.error}"),
            resolved_thread_id=out_val.thread_id,
            model=model,
            output_text=output_text,
            parse_error=getattr(run_result, "parse_error", None) if run_result is not None else None,
        )
    except Exception:
        pass

    if exit_code_override is not None:
        return exit_code_override
    if shim_error:
        return 1
    if run_result is None:
        return 1
    if not out_val.ok:
        return 3
    return int(run_result.returncode)


def entrypoint() -> int:
    return main(sys.argv[1:])
