#!/usr/bin/env python3
"""Rebuild memory/optimized-workflow.md from run logs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild optimized-workflow.md from memory/runs logs.")
    parser.add_argument("--skill-dir", default=str(_default_skill_dir()), help="Absolute path to the skill directory.")
    return parser


def _load_logs(runs_dir: Path) -> list[dict]:
    logs = []
    for path in sorted(runs_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        logs.append(data)
    return logs


def _format_counter(counter: Counter, limit: int) -> list[str]:
    lines = []
    for item, count in counter.most_common(limit):
        lines.append(f"- [{count}x] {item}")
    return lines


def _render(logs: list[dict]) -> str:
    issue_counter: Counter[str] = Counter()
    lesson_counter: Counter[str] = Counter()

    for log in logs:
        issue_counter.update(log.get("issues", []))
        lesson_counter.update(log.get("lessons", []))

    recent_logs = logs[-5:]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "# Optimized Feishu Read Workflow",
        "",
        f"Last rebuilt: {now}",
        "",
        "## Start Here",
        "",
        "- Read this file first.",
        "- Read the newest 3 logs in `memory/runs/` before starting a new task.",
        "- Prefer direct in-session `mcp__lark_mcp__...` calls over terminal transport work.",
        "- Keep secrets redacted by default unless the user explicitly wants a raw export.",
        "",
        "## Current Best Path",
        "",
        "1. Inspect the user input and decide whether it is a wiki URL, docx URL, or bare token.",
        "2. If the input is a wiki token or wiki URL, resolve it with `wiki_v2_space_getNode` using `useUAT=true`.",
        "3. When the resolved `obj_type` is `docx`, pass `obj_token` to `docx_v1_document_rawContent` with `useUAT=true`.",
        "4. Treat `rawContent` as plaintext and convert it into a lossy Markdown export.",
        "5. If the user asked for a Markdown file and did not provide a filename, default to a sanitized version of the Feishu document title plus `.md`.",
        "6. Save the Markdown locally, verify the file exists, and tell the user if formatting is approximate.",
        "",
        "## Dynamic Guardrails From History",
        "",
    ]

    issue_lines = _format_counter(issue_counter, limit=8)
    if issue_lines:
        lines.extend(issue_lines)
    else:
        lines.append("- No recorded issues yet.")

    lines.extend(
        [
            "",
            "## Stable Lessons",
            "",
        ]
    )

    lesson_lines = _format_counter(lesson_counter, limit=8)
    if lesson_lines:
        lines.extend(lesson_lines)
    else:
        lines.append("- No recorded lessons yet.")

    lines.extend(
        [
            "",
            "## Last 5 Runs",
            "",
        ]
    )

    if recent_logs:
        for log in recent_logs:
            lines.append(f"- {log.get('timestamp', 'unknown')} | {log.get('status', 'unknown')} | {log.get('title', 'untitled')}")
    else:
        lines.append("- No runs recorded yet.")

    lines.extend(
        [
            "",
            "## Update Rule",
            "",
            "- After each invocation, add a JSON log with `scripts/log_run.py`.",
            "- Rebuild this file with `scripts/update_workflow.py`.",
            "- If a new failure mode appears, update `references/pitfalls.md` as well.",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    runs_dir = skill_dir / "memory" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    logs = _load_logs(runs_dir)
    output_path = skill_dir / "memory" / "optimized-workflow.md"
    output_path.write_text(_render(logs), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
