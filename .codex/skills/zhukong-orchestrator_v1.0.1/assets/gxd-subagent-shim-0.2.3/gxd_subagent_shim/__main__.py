from __future__ import annotations

from .cli import entrypoint


def main() -> int:
    return entrypoint()


if __name__ == "__main__":
    raise SystemExit(main())
