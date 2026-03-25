#!/usr/bin/env python3
"""Write a structured run log for this skill."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _default_skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "run"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a JSON run log for read-feishu-doc-custom.")
    parser.add_argument("--skill-dir", default=str(_default_skill_dir()), help="Absolute path to the skill directory.")
    parser.add_argument("--title", required=True, help="Short run title.")
    parser.add_argument("--request", required=True, help="Original user request summary.")
    parser.add_argument("--status", required=True, choices=["success", "partial", "failed"], help="Run status.")
    parser.add_argument("--source-url", default="", help="Source Feishu URL if available.")
    parser.add_argument("--token", default="", help="Relevant wiki or doc token if available.")
    parser.add_argument("--issue", action="append", default=[], help="Issue encountered during the run.")
    parser.add_argument("--action", action="append", default=[], help="Action taken during the run.")
    parser.add_argument("--lesson", action="append", default=[], help="Lesson learned from the run.")
    parser.add_argument("--output", action="append", default=[], help="Output path or artifact from the run.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    runs_dir = skill_dir / "memory" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}-{_slugify(args.title)}.json"
    output_path = runs_dir / filename

    payload = {
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "title": args.title,
        "request": args.request,
        "status": args.status,
        "source_url": args.source_url,
        "token": args.token,
        "issues": args.issue,
        "actions": args.action,
        "lessons": args.lesson,
        "outputs": args.output,
    }

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
