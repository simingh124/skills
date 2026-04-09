#!/usr/bin/env python3
"""Resolve an arXiv title/URL/ID, download the source, unpack it, and locate a TeX entrypoint."""

from __future__ import annotations

import argparse
import gzip
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = "read-paper-pro/1.0"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ID_RE = re.compile(r"(?<!\d)(\d{4}\.\d{4,5}(?:v\d+)?)(?!\d)")
ARXIV_LINK_RE = re.compile(r"(?:https?://arxiv\.org)?/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
HTML_TITLE_META_RE = re.compile(r'<meta\s+name="citation_title"\s+content="([^"]+)"', re.IGNORECASE)
HTML_TITLE_TAG_RE = re.compile(r"<title>\s*\[[^\]]+\]\s*(.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
PROXY_ENV_VARS = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def slugify(value: str, max_len: int = 180) -> str:
    value = normalize_text(value).replace(" ", "_")
    return value[:max_len].strip("_") or "paper"


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    has_proxy = any(os.environ.get(name) for name in PROXY_ENV_VARS)
    attempts = [("configured proxy", None)]
    if has_proxy:
        attempts.append(("direct connection", urllib.request.ProxyHandler({})))

    last_error: Exception | None = None
    for label, proxy_handler in attempts:
        opener = urllib.request.build_opener(proxy_handler) if proxy_handler else urllib.request.build_opener()
        try:
            with opener.open(request, timeout=30) as response:
                return response.read()
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            last_error = exc
            eprint(f"Request via {label} failed for {url}: {exc}")

    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def parse_arxiv_id(query: str) -> str | None:
    query = query.strip()
    match = ID_RE.search(query)
    if not match:
        return None
    return match.group(1)


def extract_title_candidates(xml_bytes: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_bytes)
    entries = []
    for entry in root.findall("atom:entry", ATOM_NS):
        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        paper_id = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        if not title or not paper_id:
            continue
        entries.append(
            {
                "title": " ".join(title.split()),
                "id_url": paper_id,
                "arxiv_id": paper_id.rsplit("/", 1)[-1],
                "summary": " ".join(summary.split()),
            }
        )
    return entries


def select_title_match(query: str, entries: list[dict[str, str]], source_label: str, require_exact: bool = False) -> dict[str, str]:
    if not entries:
        raise RuntimeError(f"No arXiv results found for title via {source_label}: {query}")

    normalized_query = normalize_text(query)
    exact = [entry for entry in entries if normalize_text(entry["title"]) == normalized_query]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        titles = "\n".join(f"- {entry['title']} ({entry['arxiv_id']})" for entry in exact)
        raise RuntimeError(f"Ambiguous title match for '{query}' via {source_label}. Candidates:\n{titles}")

    if len(entries) == 1 and not require_exact:
        return entries[0]

    titles = "\n".join(f"- {entry['title']} ({entry['arxiv_id']})" for entry in entries)
    raise RuntimeError(f"Ambiguous title match for '{query}' via {source_label}. Candidates:\n{titles}")


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def extract_arxiv_ids_from_html(text: str) -> list[str]:
    candidates: list[str] = []
    variants = [text, html.unescape(text)]
    for variant in variants:
        candidates.extend(ARXIV_LINK_RE.findall(variant))
        candidates.extend(ARXIV_LINK_RE.findall(urllib.parse.unquote(variant)))
    return dedupe_preserve_order(candidates)


def resolve_title_via_web_search(query: str) -> dict[str, str]:
    quoted_query = urllib.parse.quote(query)
    search_attempts = [
        (
            "arXiv HTML title search",
            f"https://arxiv.org/search/?query={quoted_query}&searchtype=title&abstracts=show&order=-announced_date_first&size=10",
        ),
        (
            "DuckDuckGo site search",
            "https://html.duckduckgo.com/html/?q="
            + urllib.parse.quote(f'site:arxiv.org/abs "{query}"'),
        ),
    ]

    errors: list[str] = []
    for label, url in search_attempts:
        try:
            payload = request_bytes(url)
        except RuntimeError as exc:
            errors.append(f"{label}: {exc}")
            continue

        text = payload.decode("utf-8", errors="ignore")
        candidate_ids = extract_arxiv_ids_from_html(text)
        if not candidate_ids:
            errors.append(f"{label}: no arXiv IDs found in search results")
            continue

        eprint(f"Web search via {label} found candidate arXiv IDs: {', '.join(candidate_ids[:5])}")
        records: list[dict[str, str]] = []
        for arxiv_id in candidate_ids[:8]:
            try:
                records.append(fetch_record_by_id(arxiv_id))
            except RuntimeError as exc:
                errors.append(f"{label}: failed to resolve {arxiv_id}: {exc}")

        if not records:
            continue

        try:
            return select_title_match(query, records, label, require_exact=True)
        except RuntimeError as exc:
            errors.append(str(exc))

    joined_errors = " | ".join(errors) if errors else "no search attempts succeeded"
    raise RuntimeError(f"Web search fallback failed for title '{query}': {joined_errors}")


def resolve_title(query: str) -> dict[str, str]:
    encoded = urllib.parse.quote(query)
    urls = [
        f"https://export.arxiv.org/api/query?search_query=ti:%22{encoded}%22&start=0&max_results=5",
        f"https://export.arxiv.org/api/query?search_query=all:%22{encoded}%22&start=0&max_results=5",
    ]

    entries: list[dict[str, str]] = []
    api_errors: list[str] = []
    for url in urls:
        try:
            entries = extract_title_candidates(request_bytes(url))
        except RuntimeError as exc:
            api_errors.append(f"{url}: {exc}")
            continue
        if entries:
            break

    try:
        return select_title_match(query, entries, "arXiv Atom API")
    except RuntimeError as atom_exc:
        eprint(f"Falling back to web search for title '{query}': {atom_exc}")
        try:
            return resolve_title_via_web_search(query)
        except RuntimeError as web_exc:
            if api_errors:
                raise RuntimeError(f"{atom_exc}\nAtom API errors: {' | '.join(api_errors)}\n{web_exc}") from web_exc
            raise RuntimeError(f"{atom_exc}\n{web_exc}") from web_exc


def resolve_query(query: str) -> dict[str, str]:
    arxiv_id = parse_arxiv_id(query)
    if arxiv_id:
        record = fetch_record_by_id(arxiv_id)
        record["query_kind"] = "url_or_id"
        return record

    record = resolve_title(query)
    record["query_kind"] = "title"
    return record


def fetch_record_by_id(arxiv_id: str) -> dict[str, str]:
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    try:
        entries = extract_title_candidates(request_bytes(url))
        if entries:
            return entries[0]
        raise RuntimeError(f"Could not resolve arXiv ID: {arxiv_id}")
    except RuntimeError as exc:
        eprint(f"Falling back to arXiv abs page lookup for {arxiv_id}: {exc}")
        return fetch_record_from_abs_page(arxiv_id)


def fetch_record_from_abs_page(arxiv_id: str) -> dict[str, str]:
    url = f"https://arxiv.org/abs/{urllib.parse.quote(arxiv_id)}"
    payload = request_bytes(url)
    text = payload.decode("utf-8", errors="ignore")
    match = HTML_TITLE_META_RE.search(text)
    if match:
        title = html.unescape(match.group(1)).strip()
    else:
        tag_match = HTML_TITLE_TAG_RE.search(text)
        if not tag_match:
            raise RuntimeError(f"Could not parse arXiv abs page for {arxiv_id}")
        title = html.unescape(tag_match.group(1)).strip()

    title = " ".join(title.split())
    if not title:
        raise RuntimeError(f"Could not recover paper title from arXiv abs page for {arxiv_id}")

    return {
        "title": title,
        "id_url": url,
        "arxiv_id": arxiv_id,
        "summary": "",
    }


def safe_extract_tar(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:*") as archive:
        dest_root = dest_dir.resolve()
        for member in archive.getmembers():
            member_path = (dest_dir / member.name).resolve()
            if member_path != dest_root and not str(member_path).startswith(str(dest_root) + os.sep):
                raise RuntimeError(f"Archive path escapes destination: {member.name}")
        archive.extractall(dest_dir)


def write_single_tex_source(download_path: Path, source_dir: Path) -> None:
    try:
        with gzip.open(download_path, "rb") as handle:
            payload = handle.read()
    except OSError:
        payload = download_path.read_bytes()

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("latin-1")

    if "\\documentclass" not in text and "\\begin{document}" not in text:
        raise RuntimeError("Downloaded src payload is not a tar archive and does not look like TeX source.")

    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "source.tex").write_text(text)


def unpack_source(download_path: Path, source_dir: Path) -> None:
    if source_dir.exists():
        shutil.rmtree(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    try:
        safe_extract_tar(download_path, source_dir)
    except tarfile.ReadError:
        write_single_tex_source(download_path, source_dir)


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def score_tex_file(path: Path) -> tuple[int, int, int]:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return (-1, 0, 0)

    content = strip_comments(text)
    score = 0
    name = path.name.lower()

    if name in {"main.tex", "paper.tex", "article.tex"}:
        score += 40
    if "\\documentclass" in content:
        score += 30
    if "\\begin{document}" in content:
        score += 20
    score += len(re.findall(r"\\(?:input|include|subfile)\{", content))
    score -= len(path.parts)
    return (score, len(content), -len(str(path)))


def find_entrypoint(source_dir: Path) -> Path:
    tex_files = sorted(source_dir.rglob("*.tex"))
    if not tex_files:
        raise RuntimeError(f"No .tex files found under {source_dir}")
    best = max(tex_files, key=score_tex_file)
    return best


def download_if_needed(src_url: str, download_path: Path) -> None:
    if download_path.exists():
        eprint(f"Download already exists: {download_path}")
        return
    download_path.parent.mkdir(parents=True, exist_ok=True)
    eprint(f"Downloading source tarball to: {download_path}")
    temp_path = download_path.with_name(f"{download_path.name}.part.{os.getpid()}")
    has_proxy = any(os.environ.get(name) for name in PROXY_ENV_VARS)
    attempts = [("configured proxy", os.environ.copy())]
    if has_proxy:
        direct_env = os.environ.copy()
        for name in PROXY_ENV_VARS:
            direct_env.pop(name, None)
        attempts.append(("direct connection", direct_env))

    errors: list[str] = []
    for label, env in attempts:
        if temp_path.exists():
            temp_path.unlink()
        result = subprocess.run(
            [
                "curl",
                "-L",
                "--fail",
                "--connect-timeout",
                "30",
                "--max-time",
                "180",
                "-o",
                str(temp_path),
                src_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if result.returncode == 0:
            if temp_path.exists():
                temp_path.replace(download_path)
                return
            if download_path.exists():
                return
        errors.append(f"{label}: {result.stderr.strip() or 'curl failed'}")
        eprint(f"curl via {label} failed for {src_url}: {result.stderr.strip()}")

    raise RuntimeError(f"Failed to download {src_url}: {' | '.join(errors)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="Resolve arXiv metadata and output title-derived paths without downloading or unpacking source.",
    )
    parser.add_argument("query", help="Paper title, arXiv ID, or arXiv URL")
    return parser.parse_args()


def build_output(
    query: str,
    record: dict[str, str],
    paper_dir: Path,
    download_path: Path,
    source_dir: Path,
    summary_path: Path,
    entrypoint: Path | None = None,
) -> dict[str, str | None]:
    arxiv_id = record["arxiv_id"]
    title = record["title"]
    paper_slug = slugify(title)
    src_url = f"https://arxiv.org/src/{arxiv_id}"
    return {
        "query": query,
        "query_kind": record["query_kind"],
        "title": title,
        "paper_slug": paper_slug,
        "arxiv_id": arxiv_id,
        "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        "src_url": src_url,
        "paper_dir": str(paper_dir),
        "download_path": str(download_path),
        "source_dir": str(source_dir),
        "entrypoint": str(entrypoint) if entrypoint else None,
        "summary_path": str(summary_path),
    }


def main() -> int:
    args = parse_args()
    record = resolve_query(args.query)
    arxiv_id = record["arxiv_id"]
    title = record["title"]
    paper_slug = slugify(title)
    src_url = f"https://arxiv.org/src/{arxiv_id}"
    paper_dir = Path.cwd().resolve() / paper_slug
    download_path = paper_dir / "paper.tar.gz"
    source_dir = paper_dir / "source"
    summary_path = paper_dir / f"summary_{paper_slug}.md"

    eprint(f"Resolved paper: {title} ({arxiv_id})")
    eprint(f"Source URL: {src_url}")
    eprint(f"Download path: {download_path}")
    eprint(f"Source directory: {source_dir}")
    eprint(f"Summary path: {summary_path}")

    output = build_output(
        query=args.query,
        record=record,
        paper_dir=paper_dir,
        download_path=download_path,
        source_dir=source_dir,
        summary_path=summary_path,
    )
    if args.resolve_only:
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    download_if_needed(src_url, download_path)

    if not source_dir.exists() or not any(source_dir.iterdir()):
        eprint(f"Extracting source into: {source_dir}")
        unpack_source(download_path, source_dir)
    else:
        eprint(f"Source directory already populated: {source_dir}")

    entrypoint = find_entrypoint(source_dir)
    output["entrypoint"] = str(entrypoint)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
