#!/usr/bin/env python3
"""Scan paper figures and materialize only the images that the summary will use."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import fitz

SECTION_RE = re.compile(r"\\section\{([^}]*)\}")
FIGURE_BEGIN_RE = re.compile(r"\\begin\{figure\*?\}")
FIGURE_END_RE = re.compile(r"\\end\{figure\*?\}")
INPUT_RE = re.compile(r"\\(?:input|include|subfile)\{([^}]+)\}")
INCLUDE_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
DEFAULT_ZOOM = 2.0
MIN_RENDER_WIDTH = 1400
MAX_RENDER_WIDTH = 2400
MAX_RENDER_HEIGHT = 2800


def slugify(value: str, max_len: int = 120) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")[:max_len] or "figure"


def clean_tex(text: str) -> str:
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\textbf\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\emph\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\small", "", text)
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\ref\{[^}]*\}", "", text)
    text = re.sub(r"\\cite[p|t]?\{[^}]*\}", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("\\", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_braced_content(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    i = start + len(marker)
    depth = 1
    chars: list[str] = []
    while i < len(text):
        ch = text[i]
        prev = text[i - 1] if i > 0 else ""
        if ch == "{" and prev != "\\":
            depth += 1
            chars.append(ch)
        elif ch == "}" and prev != "\\":
            depth -= 1
            if depth == 0:
                return "".join(chars)
            chars.append(ch)
        else:
            chars.append(ch)
        i += 1
    return "".join(chars)


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


def resolve_image_path(base_dir: Path, target: str) -> Path | None:
    raw = (base_dir / target).resolve()
    candidates = [raw]
    if not raw.suffix:
        candidates.extend(raw.with_suffix(ext) for ext in (".pdf", ".png", ".jpg", ".jpeg"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def choose_render_zoom(page: fitz.Page) -> float:
    width = float(page.rect.width)
    height = float(page.rect.height)
    zoom = DEFAULT_ZOOM
    if width * zoom < MIN_RENDER_WIDTH:
        zoom = MIN_RENDER_WIDTH / width
    if width * zoom > MAX_RENDER_WIDTH or height * zoom > MAX_RENDER_HEIGHT:
        zoom = min(MAX_RENDER_WIDTH / width, MAX_RENDER_HEIGHT / height)
    return max(0.5, zoom)


def render_pdf_to_png(src: Path, dest: Path) -> None:
    doc = fitz.open(src)
    try:
        page = doc.load_page(0)
        zoom = choose_render_zoom(page)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(dest)
    finally:
        doc.close()


def convert_raster_to_png(src: Path, dest: Path) -> None:
    if src.suffix.lower() == ".png":
        shutil.copy2(src, dest)
        return
    pix = fitz.Pixmap(str(src))
    try:
        pix.save(dest)
    finally:
        pix = None


def choose_display_width_pct(width: int, height: int) -> int:
    ratio = width / max(height, 1)
    if ratio < 0.6:
        return 42
    if ratio < 0.9:
        return 50
    if ratio < 1.3:
        return 58
    if ratio < 1.8:
        return 66
    if ratio < 2.6:
        return 72
    return 78


def read_dimensions(src: Path) -> tuple[int, int]:
    if src.suffix.lower() == ".pdf":
        doc = fitz.open(src)
        try:
            page = doc.load_page(0)
            return int(round(page.rect.width)), int(round(page.rect.height))
        finally:
            doc.close()
    pix = fitz.Pixmap(str(src))
    try:
        return pix.width, pix.height
    finally:
        pix = None


def materialize_figure_asset(src: Path, dest_dir: Path, figure_id: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(src.stem)
    if src.suffix.lower() == ".pdf":
        dest = dest_dir / f"{figure_id}_{slug}.png"
        render_pdf_to_png(src, dest)
        return dest
    dest = dest_dir / f"{figure_id}_{slug}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    return dest


def materialize_header_image(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "header.png"
    if src.suffix.lower() == ".pdf":
        render_pdf_to_png(src, dest)
    else:
        convert_raster_to_png(src, dest)
    return dest


def clean_generated_assets(figures_dir: Path) -> None:
    if not figures_dir.exists():
        return
    for pattern in ("figure_*", "header.png", "manifest.json"):
        for path in figures_dir.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def load_tex_lines(path: Path, visited: set[Path]) -> list[tuple[Path, str]]:
    path = path.resolve()
    if path in visited:
        return []
    visited.add(path)

    text = path.read_text(errors="ignore")
    lines: list[tuple[Path, str]] = []
    for raw_line in text.splitlines():
        stripped = strip_comments(raw_line).strip()
        include_targets = INPUT_RE.findall(stripped)
        if include_targets and INPUT_RE.fullmatch(stripped):
            for target in include_targets:
                child = resolve_child(path, target.strip())
                if child is not None:
                    lines.extend(load_tex_lines(child, visited))
            continue
        lines.append((path, raw_line))
    return lines


def extract_resolved_images(block_lines: list[tuple[Path, str]]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []
    for line_path, line in block_lines:
        for target in INCLUDE_RE.findall(line):
            src = resolve_image_path(line_path.parent, target)
            if src is None:
                continue
            images.append(
                {
                    "include_target": target,
                    "source_path": str(src),
                }
            )
    return images


def parse_figures(entrypoint: Path) -> list[dict[str, object]]:
    lines = load_tex_lines(entrypoint, set())
    figures: list[dict[str, object]] = []
    current_section = "front_matter"
    i = 0
    while i < len(lines):
        line_path, line = lines[i]
        section_match = SECTION_RE.search(line)
        if section_match:
            current_section = clean_tex(section_match.group(1))
        if FIGURE_BEGIN_RE.search(line):
            block_lines = [(line_path, line)]
            i += 1
            while i < len(lines):
                block_lines.append(lines[i])
                if FIGURE_END_RE.search(lines[i][1]):
                    break
                i += 1
            block = "\n".join(text for _, text in block_lines)
            caption = clean_tex(extract_braced_content(block, r"\caption{"))
            if not caption:
                caption = clean_tex(extract_braced_content(block, r"\captionof{figure}{"))
            images = extract_resolved_images(block_lines)
            if images:
                figures.append(
                    {
                        "section": current_section,
                        "caption": caption,
                        "images": images,
                    }
                )
        elif INCLUDE_RE.search(line):
            block_lines = [(line_path, line)]
            j = i
            max_lookahead = 20
            while j + 1 < len(lines) and j - i < max_lookahead:
                next_path, next_line = lines[j + 1]
                if FIGURE_BEGIN_RE.search(next_line) or SECTION_RE.search(next_line):
                    break
                block_lines.append((next_path, next_line))
                candidate = "\n".join(text for _, text in block_lines)
                if extract_braced_content(candidate, r"\captionof{figure}{"):
                    caption = clean_tex(extract_braced_content(candidate, r"\captionof{figure}{"))
                    images = extract_resolved_images(block_lines)
                    if images:
                        figures.append(
                            {
                                "section": current_section,
                                "caption": caption,
                                "images": images,
                            }
                        )
                    i = j + 1
                    break
                j += 1
        i += 1
    return figures


def pick_header_figure(figures: list[dict[str, object]]) -> int:
    keywords = (
        "architecture",
        "method",
        "overview",
        "memory",
        "mechanism",
        "framework",
        "recurrent",
        "simple",
    )
    best_index = 0
    best_score = -10**9
    for idx, figure in enumerate(figures):
        caption = str(figure.get("caption", "")).lower()
        includes = " ".join(
            image.get("include_target", "").lower() for image in figure.get("images", []) if isinstance(image, dict)
        )
        score = -idx
        if idx == 0:
            score += 20
        for kw in keywords:
            if kw in caption:
                score += 20
            if kw in includes:
                score += 15
        if "attention" in caption:
            score -= 5
        if score > best_score:
            best_score = score
            best_index = idx
    return best_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--paper-dir", required=True)
    parser.add_argument(
        "--figure-ids",
        nargs="*",
        default=None,
        help="Materialize only these figure IDs for use in the summary. If omitted, only the header image is materialized.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove previously generated summary figure assets before rebuilding.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entrypoint = Path(args.entrypoint).resolve()
    paper_dir = Path(args.paper_dir).resolve()
    figures_dir = paper_dir / "figures"
    selected_ids = set(args.figure_ids or [])

    if args.clean:
        clean_generated_assets(figures_dir)

    figure_blocks = parse_figures(entrypoint)
    header_block_index = pick_header_figure(figure_blocks) if figure_blocks else None
    header_source_path: Path | None = None
    header_figure_id: str | None = None
    prepared: list[dict[str, object]] = []

    for fig_idx, block in enumerate(figure_blocks, start=1):
        for img_idx, image in enumerate(block["images"], start=1):
            src = Path(str(image["source_path"])).resolve()
            figure_id = f"figure_{fig_idx:02d}_{img_idx:02d}"
            source_width, source_height = read_dimensions(src)
            is_header_candidate = header_block_index is not None and fig_idx == header_block_index + 1 and img_idx == 1
            if is_header_candidate:
                header_source_path = src
                header_figure_id = figure_id

            entry: dict[str, object] = {
                "figure_id": figure_id,
                "figure_index": fig_idx,
                "image_index": img_idx,
                "section": block["section"],
                "caption": block["caption"],
                "source_path": str(src),
                "source_suffix": src.suffix.lower(),
                "source_width": source_width,
                "source_height": source_height,
                "needs_conversion": src.suffix.lower() == ".pdf",
                "suggested_width_pct": choose_display_width_pct(source_width, source_height),
                "selected_for_summary": figure_id in selected_ids,
                "is_header_candidate": is_header_candidate,
                "materialized": False,
                "asset_path": None,
                "markdown_path": None,
            }

            if figure_id in selected_ids:
                asset = materialize_figure_asset(src, figures_dir, figure_id)
                entry["materialized"] = True
                entry["asset_path"] = str(asset)
                entry["markdown_path"] = f"./figures/{asset.name}"
                entry["materialization_reason"] = "selected"
            prepared.append(entry)

    header_markdown = None
    if header_source_path is not None:
        header_asset = materialize_header_image(header_source_path, figures_dir)
        header_markdown = f"./figures/{header_asset.name}"

    manifest = {
        "entrypoint": str(entrypoint),
        "paper_dir": str(paper_dir),
        "header_image": header_markdown,
        "header_figure_id": header_figure_id,
        "selected_figure_ids": sorted(selected_ids),
        "figures": prepared,
    }
    figures_dir.mkdir(parents=True, exist_ok=True)
    (figures_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
