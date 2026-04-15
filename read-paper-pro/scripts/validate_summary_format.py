#!/usr/bin/env python3
"""Validate structural formatting constraints for read-paper-pro summaries."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

IMG_BLOCK_RE = re.compile(r'<p align="center">.*?<img\b.*?</p>', re.S)
FENCED_CODE_BLOCK_RE = re.compile(r'```.*?```', re.S)
INLINE_CODE_RE = re.compile(r'`([^`\n]+)`')
HEADER_IMG_RE = re.compile(
    r'<p align="center">\s*<img\b[^>]*src="\./figures/header\.png"[^>]*>.*?</p>',
    re.S,
)
SECTION_RE = re.compile(r'^##\s+(\d+)\.\s+(.+?)\s*$', re.M)
INSIGHT_FORMAT_LINE_RE = re.compile(
    r'^\s*（格式：\*\*【创新点解决的问题】 -> 【受哪个 insight 启发】 -> 【设计了什么创新点】\*\*）\s*$',
    re.M,
)
LEGACY_INSIGHT_FORMAT_LINE_RE = re.compile(
    r'^\s*-\s*（格式：\*\*【创新点解决的问题】 -> 【受哪个 insight 启发】 -> 【设计了什么创新点】\*\*）\s*$',
    re.M,
)
INNOVATION_BULLET_RE = re.compile(r'^-\s+\*\*【.+?】\s*->\s*【.+?】\s*->\s*【.+?】\*\*\s*$', re.M)


class ValidationError(Exception):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def find_section(text: str, title: str) -> tuple[int, str, str] | None:
    matches = list(SECTION_RE.finditer(text))
    for index, match in enumerate(matches):
        if match.group(2).strip() != title:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return int(match.group(1)), match.group(0).strip(), text[start:end]
    return None


def iter_subsections(section_body: str, heading_re: re.Pattern[str]) -> list[tuple[str, str]]:
    matches = list(heading_re.finditer(section_body))
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_body)
        blocks.append((match.group(0).strip(), section_body[start:end]))
    return blocks


def line_number(text: str, offset: int) -> int:
    return text.count('\n', 0, offset) + 1


def ensure_no_bare_images(text: str, errors: list[str]) -> None:
    stripped = IMG_BLOCK_RE.sub('', text)
    for match in re.finditer(r'<img\b', stripped):
        errors.append(
            f'Found bare <img> outside a centered <p align="center"> wrapper at line {line_number(stripped, match.start())}.'
        )


def looks_like_math_code(content: str) -> bool:
    if re.search(r'\\[A-Za-z]+', content):
        return True
    if re.search(r'[A-Za-z0-9][_^]\{?[^`\s]+', content):
        return True
    if re.search(r'[A-Za-z0-9)\]}]\s*(?:=|<|>|<=|>=)\s*[A-Za-z0-9(\\{]', content):
        return True
    return False


def ensure_no_backticked_math(text: str, errors: list[str]) -> None:
    stripped = FENCED_CODE_BLOCK_RE.sub('', text)
    for match in INLINE_CODE_RE.finditer(stripped):
        content = match.group(1).strip()
        if not looks_like_math_code(content):
            continue
        errors.append(
            'Found math-like inline code '
            f'`{content}` at line {line_number(stripped, match.start())}; use $...$ or $$...$$ instead so Markdown can render LaTeX.'
        )


def ensure_header_image(summary_path: Path, text: str, errors: list[str]) -> None:
    header_path = summary_path.parent / 'figures' / 'header.png'
    if not header_path.exists():
        return
    if not HEADER_IMG_RE.search(text):
        errors.append('Missing centered header image block for ./figures/header.png.')


def ensure_method_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, '方法')
    if section is None:
        errors.append('Missing section: ## <n>. 方法')
        return

    section_number, _, section_body = section
    subheading_re = re.compile(rf'^###\s+{section_number}\.\d+\b.*$', re.M)
    blocks = iter_subsections(section_body, subheading_re)
    if not blocks:
        errors.append(
            f'Method section must contain subsections like ### {section_number}.1, ### {section_number}.2, ...'
        )
        return

    first_heading = f'### {section_number}.1'
    if not any(heading.startswith(first_heading) for heading, _ in blocks):
        errors.append(f'Method section must include a first subsection like {first_heading}.')


def ensure_experiment_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, '实验与评估')
    if section is None:
        errors.append('Missing section: ## <n>. 实验与评估')
        return

    section_number, _, section_body = section
    subheading_re = re.compile(rf'^###\s+{section_number}\.\d+\b.*$', re.M)
    blocks = iter_subsections(section_body, subheading_re)
    if not blocks:
        errors.append(
            f'Experiment section must contain subsections like ### {section_number}.1, ### {section_number}.2, ...'
        )
        return

    required_labels = ['- **研究问题**：', '- **设置**：', '- **结果**：']
    for heading, body in blocks:
        for label in required_labels:
            if label not in body:
                errors.append(f'{heading} is missing required label: {label}')


def ensure_training_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, '训练方法')
    if section is None:
        return

    _, _, section_body = section
    required_labels = [
        '- **模型与初始化**：',
        '- **优化器与训练调度**：',
        '- **数据与样本构造**：',
        '- **训练流程**：',
        '- **关键细节与训练技巧**：',
        '- **其他训练关键信息**：',
        '- **计算与实现**：',
    ]
    for label in required_labels:
        if label not in section_body:
            errors.append(f'Training section is missing required label: {label}')


def ensure_insight_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, '洞见与创新')
    if section is None:
        errors.append('Missing section: ## <n>. 洞见与创新')
        return

    section_number, _, section_body = section
    subsection_re = re.compile(rf'^###\s+{section_number}\.(\d+)\s+(.+?)\s*$', re.M)
    blocks = iter_subsections(section_body, subsection_re)
    if not blocks:
        errors.append(
            f'Insight section must contain subsections like ### {section_number}.1 Insight and ### {section_number}.2 创新点.'
        )
        return

    block_map = {heading: body for heading, body in blocks}
    insight_heading = f'### {section_number}.1 Insight'
    innovation_heading = f'### {section_number}.2 创新点'

    if insight_heading not in block_map:
        errors.append(f'Missing required subsection: {insight_heading}')
        return
    if innovation_heading not in block_map:
        errors.append(f'Missing required subsection: {innovation_heading}')
        return

    insight_body = block_map[insight_heading]
    insight_matches = re.findall(r'^-\s+\*\*Insight\s+\d+\*\*[：:].*$', insight_body, re.M)
    if len(insight_matches) < 2:
        errors.append(f'{insight_heading} must contain at least two bullets like - **Insight 1**：...')

    innovation_body = block_map[innovation_heading]
    if LEGACY_INSIGHT_FORMAT_LINE_RE.search(innovation_body):
        errors.append(
            f'{innovation_heading} must keep the format line as plain text, not as a list item.'
        )
    if not INSIGHT_FORMAT_LINE_RE.search(innovation_body):
        errors.append(
            f'{innovation_heading} must include the literal format line: （格式：**【创新点解决的问题】 -> 【受哪个 insight 启发】 -> 【设计了什么创新点】**）'
        )

    innovation_matches = INNOVATION_BULLET_RE.findall(innovation_body)
    if not innovation_matches:
        errors.append(
            f'{innovation_heading} must include at least one innovation bullet in the format - **【...】 -> 【...】 -> 【...】**'
        )


def ensure_risk_and_followup_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, '潜在问题与后续方向')
    if section is None:
        errors.append('Missing section: ## <n>. 潜在问题与后续方向')
        return

    section_number, _, section_body = section
    subsection_re = re.compile(rf'^###\s+{section_number}\.(\d+)\s+(.+?)\s*$', re.M)
    blocks = iter_subsections(section_body, subsection_re)
    if not blocks:
        errors.append(
            f'Risk/follow-up section must contain subsections like ### {section_number}.1 潜在问题 and ### {section_number}.2 后续方向.'
        )
        return

    block_map = {heading: body for heading, body in blocks}
    risk_heading = f'### {section_number}.1 潜在问题'
    followup_heading = f'### {section_number}.2 后续方向'

    if risk_heading not in block_map:
        errors.append(f'Missing required subsection: {risk_heading}')
        return
    if followup_heading not in block_map:
        errors.append(f'Missing required subsection: {followup_heading}')

    risk_body = block_map[risk_heading]
    subsubheading_re = re.compile(r'^####\s+(.+?)\s*$', re.M)
    risk_blocks = iter_subsections(risk_body, subsubheading_re)
    risk_block_map = {heading: body for heading, body in risk_blocks}
    explicit_heading = '#### 作者明确承认的局限'
    inferred_heading = '#### 基于论文证据可推导的潜在问题'

    if explicit_heading not in risk_block_map:
        errors.append(f'{risk_heading} must include {explicit_heading}')
    if inferred_heading not in risk_block_map:
        errors.append(f'{risk_heading} must include {inferred_heading}')
    elif 'Inference:' not in risk_block_map[inferred_heading]:
        errors.append(f'{inferred_heading} must include at least one explicit Inference: marker.')


def ensure_idea_structure(text: str, errors: list[str]) -> None:
    section = find_section(text, 'AI idea brainstorming')
    if section is None:
        errors.append('Missing section: ## <n>. AI idea brainstorming')
        return

    _, _, section_body = section
    blocks = iter_subsections(section_body, re.compile(r'^###\s+Idea\s+\d+[：:].*$', re.M))
    if not blocks:
        errors.append('Idea section must contain subsections like ### Idea 1：<title>.')
        return

    required_labels = [
        '- **要解决的问题**：',
        '- **继承的 insight / 机制 / 观察**：',
        '- **方法设计**：',
        '- **最小可行实验**：',
        '- **主要风险**：',
    ]
    for heading, body in blocks:
        for label in required_labels:
            if label not in body:
                errors.append(f'{heading} is missing required label: {label}')


def validate(summary_path: Path) -> None:
    text = read_text(summary_path)
    errors: list[str] = []

    ensure_no_bare_images(text, errors)
    ensure_no_backticked_math(text, errors)
    ensure_header_image(summary_path, text, errors)
    ensure_method_structure(text, errors)
    ensure_training_structure(text, errors)
    ensure_experiment_structure(text, errors)
    ensure_insight_structure(text, errors)
    ensure_risk_and_followup_structure(text, errors)
    ensure_idea_structure(text, errors)

    if errors:
        raise ValidationError('\n'.join(f'- {error}' for error in errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', required=True, type=Path, help='Path to the generated markdown summary.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate(args.summary)
    except FileNotFoundError as exc:
        print(f'Validation failed: {exc}', file=sys.stderr)
        return 1
    except ValidationError as exc:
        print('Validation failed:', file=sys.stderr)
        print(exc, file=sys.stderr)
        return 1

    print(f'Validation passed: {args.summary}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
