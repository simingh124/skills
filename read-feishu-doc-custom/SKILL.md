---
name: read-feishu-doc-custom
description: "Read and export Feishu/Lark wiki or doc content with lark-mcp, especially when the input is a Feishu URL or token and Codex must resolve wiki tokens, use user-authenticated tools, fetch raw content, summarize content, and save a local Markdown export. Use when Codex needs to: (1) read Feishu wiki/docx content, (2) convert Feishu docs to local Markdown, using the Feishu document title as the default filename when the user did not specify one, (3) diagnose lark-mcp auth, redirect, token, or tool-availability issues, (4) recover from wiki-token vs docx-token confusion, or (5) maintain this skill's run-memory logs and optimized workflow."
---

# Read Feishu Doc Custom

## Overview

Use this skill to read Feishu wiki/doc content through `lark-mcp` and export it locally. Start from the optimized workflow, prefer direct MCP tool calls, and only open the detailed references when the normal path breaks.

## Mandatory Start

- Read `memory/optimized-workflow.md`.
- Read the newest 3 JSON files under `memory/runs/` if they exist.
- Prefer direct in-session MCP tool functions before any terminal fallback.
- Preserve secrets by default. If the source doc contains keys, tokens, or webhook URLs, ask before keeping them verbatim in the Markdown export unless the user explicitly requested a raw dump.

## Default Path

1. Identify the input type.
   - `https://.../wiki/<token>` means a wiki node token.
   - `https://.../docx/<token>` means a docx document token.
   - A bare token is ambiguous unless the user already established whether it is `wiki` or `docx`.
2. Prefer direct `lark-mcp` tool calls exposed in the session.
   - For wiki inputs, call `wiki_v2_space_getNode` with `token=<wiki_token>` and `useUAT=true`.
   - For direct docx inputs, skip wiki resolution.
   - For content reads, call `docx_v1_document_rawContent` with `document_id=<docx_token>` and `useUAT=true`.
3. Resolve wiki tokens before reading content.
   - Never send a wiki token directly to `docx_v1_document_rawContent`.
   - Extract `obj_type` and `obj_token` from `wiki_v2_space_getNode`.
   - Continue only when `obj_type` is `docx`.
4. Convert raw content to Markdown.
   - `docx_v1_document_rawContent` returns plain text, not faithful Markdown.
   - Build a lossy Markdown export: title, source URL, tool path used, then formatted body text.
   - Add fenced code blocks manually when the raw text clearly contains scripts, config, or commands.
   - Tell the user when formatting is approximate.
5. Save and verify.
   - Write a new local `.md` file in the requested directory when the user asked for a file export.
   - If the user did not specify a filename, default to `<Feishu document title>.md`.
   - Sanitize filesystem-unsafe characters conservatively. If the title becomes empty after sanitization, fall back to `feishu-doc.md`.
   - Verify the file exists.
   - If useful, preview the first lines back to the user.

## Tool Choice

- Use direct in-session MCP functions if present. Example names already observed in this environment:
  - `mcp__lark_mcp__wiki_v2_space_getNode`
  - `mcp__lark_mcp__docx_v1_document_rawContent`
- Open `references/terminal-fallback.md` only when direct MCP functions are missing or broken.

## Troubleshooting Triggers

Open `references/pitfalls.md` when any of these appear:

- login or callback redirect errors
- MCP discovery looks empty even though `lark-mcp` is configured
- `rawContent` fails on a wiki URL
- terminal stdio MCP handshake hangs
- the export loses too much structure
- permission errors appear on a document the user can read in Feishu

## Memory Protocol

At the start of every invocation:

- Read `memory/optimized-workflow.md`.
- Read the latest three logs in `memory/runs/`.

At the end of every invocation:

1. Create a new run log JSON with `scripts/log_run.py`.
2. Rebuild `memory/optimized-workflow.md` with `scripts/update_workflow.py`.
3. If the run introduced a new failure mode, add a concise note to `references/pitfalls.md`.

Use this log shape:

- `request`
- `source_url` or `token`
- `status`: `success`, `partial`, or `failed`
- `issues`
- `actions`
- `lessons`
- `outputs`
