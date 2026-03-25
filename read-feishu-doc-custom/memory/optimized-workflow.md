# Optimized Feishu Read Workflow

Last rebuilt: 2026-03-24T14:04:48Z

## Start Here

- Read this file first.
- Read the newest 3 logs in `memory/runs/` before starting a new task.
- Prefer direct in-session `mcp__lark_mcp__...` calls over terminal transport work.
- Keep secrets redacted by default unless the user explicitly wants a raw export.

## Current Best Path

1. Inspect the user input and decide whether it is a wiki URL, docx URL, or bare token.
2. If the input is a wiki token or wiki URL, resolve it with `wiki_v2_space_getNode` using `useUAT=true`.
3. When the resolved `obj_type` is `docx`, pass `obj_token` to `docx_v1_document_rawContent` with `useUAT=true`.
4. Treat `rawContent` as plaintext and convert it into a lossy Markdown export.
5. If the user asked for a Markdown file and did not provide a filename, default to a sanitized version of the Feishu document title plus `.md`.
6. Save the Markdown locally, verify the file exists, and tell the user if formatting is approximate.

## Dynamic Guardrails From History

- [1x] Tried non-MCP or OpenClaw-style routes first even though they were unnecessary for direct Codex Feishu reads.
- [1x] Built-in lark-mcp login hit redirect-url errors during OAuth.
- [1x] MCP discovery looked empty at one stage, which falsely suggested lark-mcp was unavailable.
- [1x] The wiki token was initially not interchangeable with the underlying docx document_id.
- [1x] docx rawContent returned plain text rather than faithful Markdown.
- [1x] A hand-rolled stdio MCP client was brittle and stalled during protocol debugging.
- [1x] rawContent returned plaintext so the export remains a lossy Markdown reconstruction

## Stable Lessons

- [1x] Prefer direct in-session lark-mcp tool calls over OpenClaw or non-MCP Feishu skills.
- [1x] Always resolve a wiki token to obj_token before calling rawContent.
- [1x] Prefer user-token mode and useUAT=true for private Feishu docs.
- [1x] Treat rawContent exports as lossy and tell the user when Markdown structure is approximate.
- [1x] the direct in-session lark-mcp path remains the fastest and most reliable route for Feishu reads in this environment
- [1x] for tutorial-style docs, a short structured summary plus a lossy Markdown export is usually enough

## Last 5 Runs

- 2026-03-24T00:00:00Z | success | bootstrap history from first successful lark-mcp read
- 2026-03-24T10:17:05.860244Z | success | summarize memory transformer training tutorial

## Update Rule

- After each invocation, add a JSON log with `scripts/log_run.py`.
- Rebuild this file with `scripts/update_workflow.py`.
- If a new failure mode appears, update `references/pitfalls.md` as well.
