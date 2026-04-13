#!/usr/bin/env python3
"""Write a structured run log for tmux-remote-worker-setup."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record a remote worker setup run.")
    parser.add_argument("--skill-dir", default=str(_default_skill_dir()))
    parser.add_argument("--request", required=True, help="Original user request or condensed task summary.")
    parser.add_argument("--status", choices=["success", "partial", "failed"], required=True)
    parser.add_argument("--session-name", required=True)
    parser.add_argument("--replica", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--issue", action="append", default=[])
    parser.add_argument("--lesson", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--note", action="append", default=[])
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    skill_dir = Path(args.skill_dir).resolve()
    runs_dir = skill_dir / "memory" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    title = args.title or f"{args.session_name} | {args.status}"

    payload = {
        "timestamp": timestamp,
        "title": title,
        "request": args.request,
        "status": args.status,
        "session_name": args.session_name,
        "replica": args.replica,
        "issues": args.issue,
        "lessons": args.lesson,
        "actions": args.action,
        "outputs": args.output,
        "notes": args.note,
    }

    output_path = runs_dir / f"{timestamp}.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
