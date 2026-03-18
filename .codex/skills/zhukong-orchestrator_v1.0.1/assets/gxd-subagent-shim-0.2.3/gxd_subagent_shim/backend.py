from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Any, BinaryIO, Callable, Sequence

from .config import (
    ENV_ANTHROPIC_API_KEY,
    ENV_ANTHROPIC_AUTH_TOKEN,
    ENV_CLAUDE_BIN,
    ENV_CODEX_BIN,
    ENV_BACKEND,
)
from .io import ensure_dir, try_parse_json
from .util import utc_now


def safe_decode(b: bytes) -> str:
    return b.decode("utf-8", errors="replace")


@dataclass
class RunResult:
    cmd: Sequence[str]
    returncode: int
    stdout: bytes
    stderr: bytes
    duration_ms: int
    parsed_json: Any | None
    parse_error: str | None


def normalize_backend(name: str) -> str:
    b2 = (name or "").strip().lower().replace("_", "-")
    if b2 in ("claude-code", "claudecode", "anthropic", "claude"):
        return "claude"
    return b2


def resolve_backend(cli_backend: str | None) -> str:
    if cli_backend:
        return normalize_backend(cli_backend)
    env_backend = os.getenv(ENV_BACKEND)
    if env_backend:
        return normalize_backend(env_backend)
    return "codex"


def codex_bin() -> str:
    return os.getenv(ENV_CODEX_BIN, "codex")


def claude_bin() -> str:
    return os.getenv(ENV_CLAUDE_BIN, "claude")


def ensure_anthropic_auth() -> None:
    key = os.getenv(ENV_ANTHROPIC_API_KEY) or os.getenv(ENV_ANTHROPIC_AUTH_TOKEN)
    if not key:
        raise RuntimeError(f"Missing {ENV_ANTHROPIC_API_KEY} or {ENV_ANTHROPIC_AUTH_TOKEN} for Claude backend")
    os.environ.setdefault(ENV_ANTHROPIC_API_KEY, key)
    os.environ.setdefault(ENV_ANTHROPIC_AUTH_TOKEN, key)


def _drain_stream(
    stream: BinaryIO,
    sink_path: Path | None,
    chunks: list[bytes],
    chunk_cb: Callable[[bytes], None] | None = None,
    close_cb: Callable[[], None] | None = None,
) -> None:
    fh: BinaryIO | None = None
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk_cb is not None:
                try:
                    chunk_cb(chunk)
                except Exception:
                    pass
            if sink_path is not None:
                if fh is None:
                    try:
                        ensure_dir(sink_path.parent)
                        fh = sink_path.open("ab", buffering=0)
                    except Exception:
                        sink_path = None
                        fh = None
                if fh is not None:
                    try:
                        fh.write(chunk)
                        fh.flush()
                    except Exception:
                        pass
    finally:
        if close_cb is not None:
            try:
                close_cb()
            except Exception:
                pass
        try:
            stream.close()
        except Exception:
            pass
        if fh is not None:
            try:
                fh.close()
            except Exception:
                pass


def run_capture(
    cmd: Sequence[str],
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    stdout_chunk_cb: Callable[[bytes], None] | None = None,
    stderr_chunk_cb: Callable[[bytes], None] | None = None,
    stdout_close_cb: Callable[[], None] | None = None,
    stderr_close_cb: Callable[[], None] | None = None,
) -> RunResult:
    start = utc_now()
    try:
        proc = subprocess.Popen(list(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    except FileNotFoundError as e:
        end = utc_now()
        dur_ms = int((end - start).total_seconds() * 1000)
        return RunResult(
            cmd=cmd,
            returncode=127,
            stdout=b"",
            stderr=str(e).encode("utf-8", errors="replace"),
            duration_ms=dur_ms,
            parsed_json=None,
            parse_error=None,
        )

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    threads: list[threading.Thread] = []

    if proc.stdout is not None:
        t = threading.Thread(
            target=_drain_stream,
            args=(proc.stdout, stdout_path, stdout_chunks, stdout_chunk_cb, stdout_close_cb),
        )
        t.start()
        threads.append(t)
    if proc.stderr is not None:
        t = threading.Thread(
            target=_drain_stream,
            args=(proc.stderr, stderr_path, stderr_chunks, stderr_chunk_cb, stderr_close_cb),
        )
        t.start()
        threads.append(t)

    returncode = proc.wait()
    for t in threads:
        t.join()

    end = utc_now()
    dur_ms = int((end - start).total_seconds() * 1000)

    stdout_b = b"".join(stdout_chunks)
    stderr_b = b"".join(stderr_chunks)

    parsed, parse_err = try_parse_json(safe_decode(stdout_b))
    return RunResult(
        cmd=cmd,
        returncode=int(returncode),
        stdout=stdout_b,
        stderr=stderr_b,
        duration_ms=dur_ms,
        parsed_json=parsed,
        parse_error=parse_err,
    )


def passthrough_raw(stdout_b: bytes, stderr_b: bytes) -> None:
    if stdout_b:
        sys.stdout.buffer.write(stdout_b)
        sys.stdout.buffer.flush()
    if stderr_b:
        sys.stderr.buffer.write(stderr_b)
        sys.stderr.buffer.flush()


def build_backend_cmd(backend: str, action: str, prompt: str, thread_id: str | None) -> list[str]:
    if backend == "codex":
        if action == "create":
            return [
                codex_bin(),
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--json",
                prompt,
            ]
        if action == "resume":
            assert thread_id, "resume requires thread_id"
            return [
                codex_bin(),
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--json",
                prompt,
                "resume",
                thread_id,
            ]
        raise RuntimeError(f"Unknown action for codex: {action}")

    if backend == "claude":
        ensure_anthropic_auth()
        if action == "create":
            return [
                claude_bin(),
                "-p",
                "--output-format",
                "json",
                "--dangerously-skip-permissions",
                prompt,
            ]
        if action == "resume":
            assert thread_id, "resume requires thread_id"
            return [
                claude_bin(),
                "-p",
                "--output-format",
                "json",
                "--dangerously-skip-permissions",
                "--resume",
                str(thread_id),
                prompt,
            ]
        raise RuntimeError(f"Unknown action for claude: {action}")

    raise RuntimeError(f"Unknown backend: {backend}")
