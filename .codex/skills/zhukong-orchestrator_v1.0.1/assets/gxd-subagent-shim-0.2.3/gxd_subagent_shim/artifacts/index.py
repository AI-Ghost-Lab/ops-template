from __future__ import annotations

from pathlib import Path


def build_index(run_dir: Path) -> str:
    """Generate a small markdown index for the run directory."""
    steps_dir = run_dir / "steps"

    lines: list[str] = []
    lines.append(f"# Agent Run {run_dir.name}")
    lines.append("")
    lines.append("- `meta.json`")
    lines.append("- `events.jsonl`")
    lines.append("")

    if not steps_dir.exists():
        return "\n".join(lines).rstrip() + "\n"

    step_names = sorted([d.name for d in steps_dir.iterdir() if d.is_dir()])
    lines.append("## Steps")
    lines.append("")
    lines.append("| Step | Rounds | Latest |")
    lines.append("|---|---|---|")

    def _round_num(name: str) -> int:
        if name.startswith("R") and name[1:].isdigit():
            return int(name[1:])
        return 0

    for s in step_names:
        rounds_dir = steps_dir / s / "rounds"
        round_names: list[str] = []
        if rounds_dir.exists():
            round_names = sorted([p.name for p in rounds_dir.iterdir() if p.is_dir()], key=_round_num)
        latest = round_names[-1] if round_names else "-"
        lines.append(f"| {s} | {', '.join(round_names) if round_names else '-'} | {latest} |")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
