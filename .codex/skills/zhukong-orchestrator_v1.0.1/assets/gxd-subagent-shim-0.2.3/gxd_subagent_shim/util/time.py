from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def utc_compact_stamp(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y%m%dT%H%M%SZ")
