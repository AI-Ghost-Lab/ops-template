from __future__ import annotations


def lock_file_handle(f) -> None:
    """Best-effort advisory lock for concurrent writes."""
    try:
        import fcntl  # type: ignore

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except Exception:
        return


def unlock_file_handle(f) -> None:
    try:
        import fcntl  # type: ignore

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        return
