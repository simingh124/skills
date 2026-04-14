#!/usr/bin/env python3
"""Rebuild memory/optimized-workflow.md from recorded run logs."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REMOTE_SKILLS_TEXT = (
    "`read-paper-pro`, `find-skills`, `skill-creator`, `pdf`, "
    "`academic-researcher`, and `arxiv-search`"
)
DEFAULT_WORKSPACE_TEXT = "`/home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace`"


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild optimized workflow for tmux-remote-worker-setup.")
    parser.add_argument("--skill-dir", default=str(_default_skill_dir()))
    return parser


def _load_logs(runs_dir: Path) -> list[dict]:
    logs: list[dict] = []
    if not runs_dir.exists():
        return logs
    for path in sorted(runs_dir.glob("*.json")):
        logs.append(json.loads(path.read_text(encoding="utf-8")))
    return logs


def _render(logs: list[dict]) -> str:
    issue_counter: Counter[str] = Counter()
    lesson_counter: Counter[str] = Counter()
    for log in logs:
        issue_counter.update(log.get("issues", []))
        lesson_counter.update(log.get("lessons", []))

    recent_logs = logs[-5:]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "# Optimized Remote Worker Setup Workflow",
        "",
        f"Last rebuilt: {now}",
        "",
        "## Start Here",
        "",
        "- Read this file first.",
        "- Read `references/worker_setup_memory.md`.",
        "- Read the newest 3 logs in `memory/runs/` if they exist.",
        "- Prefer the helper script over ad-hoc shell work so future runs stay consistent and comparable.",
        f"- Keep helper payloads under {DEFAULT_WORKSPACE_TEXT} so the worker can read them through the shared mount.",
        "",
        "## Current Best Path",
        "",
        "1. Resolve the tmux session to a worker replica from pane scrollback.",
        "2. Use local `/kubebrain/brainctl` as the control path; do not depend on the remote tmux pane for setup steps.",
        f"3. Build the payload under {DEFAULT_WORKSPACE_TEXT}.",
        "4. Package `node`, `npm`, `npx`, `codex`, `rg`, local Codex skills, `.env`, `AGENTS.md`, and `feishu_notify.py` into that payload.",
        "5. Copy payload contents to the worker through the shared mount and install them remotely.",
        "6. Run `/home/i-huangsiming/work/install.sh`, then patch `notify` and trusted project entries in `/root/.codex/config.toml`.",
        f"7. Install the remote Codex skill bundle through `npx skills add ... --global`: {REMOTE_SKILLS_TEXT}.",
        "8. Install `nvitop` through `/mnt/step3-abla/siming/.venv/bin/python -m pip`.",
        "9. Verify command availability, config entries, host mapping, `feishu_notify.py` syntax, the required skill installations, and that `gpu_util.py` is still running.",
        "",
        "## Optional VS Code Remote Preload Path",
        "",
        "1. Extract the exact VS Code commit from the user's local Remote log or reuse a matching local `~/.vscode-server` cache entry.",
        f"2. Stage the VS Code server under {DEFAULT_WORKSPACE_TEXT} by reusing the local cache or downloading the tarball locally.",
        "3. Copy the staged `server/` tree to `/root/.vscode-server/cli/servers/<Quality>-<commit>/server` on the worker.",
        "4. Verify that `server/bin/code-server` exists before asking the user to reconnect from VS Code.",
        "",
        "## Dynamic Guardrails From Runs",
        "",
    ]

    if issue_counter:
        for item, count in issue_counter.most_common(8):
            lines.append(f"- [{count}x] {item}")
    else:
        lines.append("- No logged issues yet.")

    lines.extend(["", "## Stable Lessons", ""])
    if lesson_counter:
        for item, count in lesson_counter.most_common(8):
            lines.append(f"- [{count}x] {item}")
    else:
        lines.append("- No logged lessons yet.")

    lines.extend(["", "## Last 5 Runs", ""])
    if recent_logs:
        for log in recent_logs:
            lines.append(
                f"- {log.get('timestamp', 'unknown')} | {log.get('status', 'unknown')} | {log.get('title', 'untitled')}"
            )
    else:
        lines.append("- No runs recorded yet.")

    lines.extend(
        [
            "",
            "## Update Rule",
            "",
            "- After each invocation, add a JSON run log with `scripts/log_run.py`.",
            "- Rebuild this file with `scripts/update_workflow.py`.",
            "- If the run exposed a new durable lesson or pitfall, update `references/worker_setup_memory.md`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    runs_dir = skill_dir / "memory" / "runs"
    output_path = skill_dir / "memory" / "optimized-workflow.md"
    output_path.write_text(_render(_load_logs(runs_dir)), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
