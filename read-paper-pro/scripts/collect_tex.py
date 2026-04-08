#!/usr/bin/env python3
"""Expand a TeX entrypoint into a single concatenated file for easier reading."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INCLUDE_RE = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def resolve_child(parent: Path, target: str) -> Path | None:
    raw = (parent.parent / target).resolve()
    candidates = [raw]
    if raw.suffix != ".tex":
        candidates.append(raw.with_suffix(".tex"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def walk_tex(path: Path, visited: set[Path], chunks: list[str]) -> None:
    path = path.resolve()
    if path in visited:
        return
    visited.add(path)

    try:
        text = path.read_text(errors="ignore")
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc

    chunks.append(f"% ===== BEGIN FILE: {path} =====\n")
    chunks.append(text)
    if not text.endswith("\n"):
        chunks.append("\n")
    chunks.append(f"% ===== END FILE: {path} =====\n\n")

    for target in INCLUDE_RE.findall(strip_comments(text)):
        child = resolve_child(path, target.strip())
        if child is None:
            continue
        walk_tex(child, visited, chunks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrypoint", required=True, help="Path to the main TeX file")
    parser.add_argument("--output", help="Optional output file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entrypoint = Path(args.entrypoint).resolve()
    if not entrypoint.exists():
        raise RuntimeError(f"Entrypoint does not exist: {entrypoint}")

    chunks: list[str] = []
    walk_tex(entrypoint, set(), chunks)
    combined = "".join(chunks)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(combined)
    else:
        sys.stdout.write(combined)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
