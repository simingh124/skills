#!/usr/bin/env python3
"""Extract hyperlinkable reference metadata from .bib or .bbl files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ARXIV_RE = re.compile(r"(?<!\d)(\d{4}\.\d{4,5}(?:v\d+)?)")
ENTRY_START_RE = re.compile(r"@(\w+)\s*([({])", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s{}\\\\]+")
BBL_ITEM_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}")


def clean_tex(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip().strip(",")


def normalize_text(text: str) -> str:
    text = clean_tex(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def derive_short_name(title: str) -> str:
    title = clean_tex(title)
    for sep in (":", " - ", " -- "):
        if sep in title:
            head = title.split(sep, 1)[0].strip()
            if 2 <= len(head) <= 80:
                return head
    return title


def extract_balanced(text: str, start: int, open_char: str, close_char: str) -> tuple[str, int]:
    depth = 1
    i = start + 1
    chars: list[str] = []
    while i < len(text):
        ch = text[i]
        prev = text[i - 1] if i > 0 else ""
        if ch == open_char and prev != "\\":
            depth += 1
        elif ch == close_char and prev != "\\":
            depth -= 1
            if depth == 0:
                return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise RuntimeError("Unbalanced bibliographic entry.")


def extract_quoted(text: str, start: int) -> tuple[str, int]:
    i = start + 1
    chars: list[str] = []
    while i < len(text):
        ch = text[i]
        prev = text[i - 1] if i > 0 else ""
        if ch == '"' and prev != "\\":
            return "".join(chars), i + 1
        chars.append(ch)
        i += 1
    raise RuntimeError("Unbalanced quoted bibliographic field.")


def find_matching_paren(text: str, start: int) -> int:
    depth = 1
    i = start + 1
    while i < len(text):
        ch = text[i]
        prev = text[i - 1] if i > 0 else ""
        if ch == "(" and prev != "\\":
            depth += 1
        elif ch == ")" and prev != "\\":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise RuntimeError("Unbalanced bibliographic entry.")


def split_bib_entries(text: str) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    pos = 0
    while True:
        match = ENTRY_START_RE.search(text, pos)
        if not match:
            break
        entry_type = match.group(1).lower()
        delimiter = match.group(2)
        body_start = match.end() - 1
        if delimiter == "{":
            body, next_pos = extract_balanced(text, body_start, "{", "}")
        else:
            next_pos = find_matching_paren(text, body_start)
            body = text[body_start + 1 : next_pos - 1]
        key, _, remainder = body.partition(",")
        entries.append((entry_type, key.strip(), remainder))
        pos = next_pos
    return entries


def extract_field(body: str, field_name: str) -> str:
    pattern = re.compile(rf"(^|[,\\n])\s*{re.escape(field_name)}\s*=", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    i = match.end()
    while i < len(body) and body[i].isspace():
        i += 1
    if i >= len(body):
        return ""
    if body[i] == "{":
        value, _ = extract_balanced(body, i, "{", "}")
        return value.strip()
    if body[i] == '"':
        value, _ = extract_quoted(body, i)
        return value.strip()
    end = i
    while end < len(body) and body[end] not in ",\n":
        end += 1
    return body[i:end].strip()


def resolve_link(fields: dict[str, str]) -> str:
    url = clean_tex(fields.get("url", ""))
    if url:
        return url
    doi = clean_tex(fields.get("doi", ""))
    if doi:
        return f"https://doi.org/{doi}"
    eprint = clean_tex(fields.get("eprint", ""))
    archive_prefix = clean_tex(fields.get("archiveprefix", ""))
    if eprint and (archive_prefix.lower() == "arxiv" or ARXIV_RE.search(eprint)):
        match = ARXIV_RE.search(eprint)
        if match:
            return f"https://arxiv.org/abs/{match.group(1)}"
    journal = clean_tex(fields.get("journal", ""))
    match = ARXIV_RE.search(journal)
    if match:
        return f"https://arxiv.org/abs/{match.group(1)}"
    return ""


def parse_bib_file(path: Path) -> list[dict[str, str]]:
    text = path.read_text(errors="ignore")
    entries: list[dict[str, str]] = []
    for entry_type, key, body in split_bib_entries(text):
        fields = {
            name.lower(): extract_field(body, name)
            for name in ("title", "url", "doi", "eprint", "archivePrefix", "journal", "booktitle")
        }
        title = clean_tex(fields.get("title", ""))
        if not title:
            continue
        link = resolve_link(fields)
        entries.append(
            {
                "source_file": str(path),
                "entry_type": entry_type,
                "key": key,
                "title": title,
                "short_name": derive_short_name(title),
                "normalized_title": normalize_text(title),
                "link": link,
            }
        )
    return entries


def split_bbl_items(text: str) -> list[tuple[str, str]]:
    matches = list(BBL_ITEM_RE.finditer(text))
    items: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        items.append((match.group(1).strip(), text[start:end]))
    return items


def infer_bbl_title(block: str) -> str:
    newblocks = [clean_tex(part) for part in block.split("\\newblock")]
    candidates = [part for part in newblocks if part]
    for candidate in candidates:
        if len(candidate) < 12:
            continue
        lower = candidate.lower()
        if "proceedings" in lower or "conference" in lower or "journal" in lower:
            continue
        return candidate.strip(" .")
    raw = clean_tex(block)
    return raw[:200].strip(" .")


def parse_bbl_file(path: Path) -> list[dict[str, str]]:
    text = path.read_text(errors="ignore")
    entries: list[dict[str, str]] = []
    for key, block in split_bbl_items(text):
        title = infer_bbl_title(block)
        if not title:
            continue
        url_match = re.search(r"\\url\{([^}]*)\}", block)
        link = clean_tex(url_match.group(1)) if url_match else ""
        if not link:
            raw_url = URL_RE.search(block)
            if raw_url:
                link = raw_url.group(0)
        if not link:
            arxiv_match = ARXIV_RE.search(block)
            if arxiv_match:
                link = f"https://arxiv.org/abs/{arxiv_match.group(1)}"
        entries.append(
            {
                "source_file": str(path),
                "entry_type": "bbl",
                "key": key,
                "title": title,
                "short_name": derive_short_name(title),
                "normalized_title": normalize_text(title),
                "link": link,
            }
        )
    return entries


def deduplicate(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: dict[str, dict[str, str]] = {}
    for entry in entries:
        key = entry["normalized_title"] or entry["key"]
        existing = deduped.get(key)
        if existing is None or (not existing.get("link") and entry.get("link")):
            deduped[key] = entry
    return sorted(deduped.values(), key=lambda item: item["title"].lower())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, help="Directory that contains the arXiv source tree")
    parser.add_argument("--output", required=True, help="Path to the output JSON file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    output_path = Path(args.output).resolve()

    bib_files = sorted(source_dir.rglob("*.bib"))
    bbl_files = sorted(source_dir.rglob("*.bbl"))

    entries: list[dict[str, str]] = []
    for path in bib_files:
        entries.extend(parse_bib_file(path))
    if not entries:
        for path in bbl_files:
            entries.extend(parse_bbl_file(path))

    payload = {
        "source_dir": str(source_dir),
        "output_path": str(output_path),
        "bib_files": [str(path) for path in bib_files],
        "bbl_files": [str(path) for path in bbl_files],
        "references": deduplicate(entries),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
