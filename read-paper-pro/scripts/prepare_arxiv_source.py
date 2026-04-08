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


def resolve_title(query: str) -> dict[str, str]:
    encoded = urllib.parse.quote(query)
    urls = [
        f"https://export.arxiv.org/api/query?search_query=ti:%22{encoded}%22&start=0&max_results=5",
        f"https://export.arxiv.org/api/query?search_query=all:%22{encoded}%22&start=0&max_results=5",
    ]

    entries: list[dict[str, str]] = []
    for url in urls:
        entries = extract_title_candidates(request_bytes(url))
        if entries:
            break

    if not entries:
        raise RuntimeError(f"No arXiv results found for title: {query}")

    normalized_query = normalize_text(query)
    exact = [entry for entry in entries if normalize_text(entry["title"]) == normalized_query]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        titles = "\n".join(f"- {entry['title']} ({entry['arxiv_id']})" for entry in exact)
        raise RuntimeError(f"Ambiguous title match for '{query}'. Candidates:\n{titles}")

    if len(entries) == 1:
        return entries[0]

    titles = "\n".join(f"- {entry['title']} ({entry['arxiv_id']})" for entry in entries)
    raise RuntimeError(f"Ambiguous title match for '{query}'. Candidates:\n{titles}")


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
    parser.add_argument("query", help="Paper title, arXiv ID, or arXiv URL")
    return parser.parse_args()


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

    download_if_needed(src_url, download_path)

    if not source_dir.exists() or not any(source_dir.iterdir()):
        eprint(f"Extracting source into: {source_dir}")
        unpack_source(download_path, source_dir)
    else:
        eprint(f"Source directory already populated: {source_dir}")

    entrypoint = find_entrypoint(source_dir)
    output = {
        "query": args.query,
        "query_kind": record["query_kind"],
        "title": title,
        "paper_slug": paper_slug,
        "arxiv_id": arxiv_id,
        "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        "src_url": src_url,
        "paper_dir": str(paper_dir),
        "download_path": str(download_path),
        "source_dir": str(source_dir),
        "entrypoint": str(entrypoint),
        "summary_path": str(summary_path),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
