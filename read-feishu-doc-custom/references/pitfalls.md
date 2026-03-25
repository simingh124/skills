# Feishu Read Pitfalls

Open this file when the normal read path fails or when the export looks suspicious.

## 1. Do not start with OpenClaw or non-MCP Feishu skills

- Earlier attempts through OpenClaw and non-MCP Feishu skills did not help direct Codex document reads.
- The proven path is `lark-mcp` plus a user access token.
- Use those older routes only if the user explicitly asks for them.

## 2. Built-in OAuth redirect can fail

Symptom:

- Feishu shows `重定向 URL 有误，请联系应用管理员...`

What this meant in practice:

- The application redirect configuration did not exactly match the callback used by the login flow.
- The built-in `lark-mcp login` flow was therefore unreliable in this setup.

Proven fix:

- Use a manual OAuth flow to obtain `access_token` plus `refresh_token`.
- Store the refreshable token locally.
- Feed `lark-mcp` with a valid user token, ideally through a helper that refreshes it before expiry.

Guardrail:

- Keep the configured redirect URL and the actual callback URL byte-for-byte identical.

## 3. MCP discovery can look empty even when the tools still work

Symptom:

- Discovery utilities or MCP resource listings looked empty, which suggested `lark-mcp` was not usable.

What actually happened:

- Direct session tool functions were still callable.

Proven fix:

- Check whether explicit `mcp__lark_mcp__...` functions are available before debugging protocol transport.
- Treat empty discovery as a signal to verify more carefully, not as proof that the MCP path is dead.

## 4. A wiki token is not a docx document ID

Symptom:

- `docx_v1_document_rawContent` failed when given the token copied from a `.../wiki/<token>` URL.

Cause:

- The wiki URL token identifies the wiki node, not the underlying docx resource.

Proven fix:

- Call `wiki_v2_space_getNode`.
- Use the returned `obj_token` as `document_id` when `obj_type == docx`.

## 5. `rawContent` is plain text, not rich Markdown

Symptom:

- Headings, lists, code fences, and rich structure were flattened.

Implication:

- The export is inherently lossy.

Proven fix:

- Tell the user that formatting is approximate.
- Reconstruct minimal Markdown structure by hand when the text clearly contains code, commands, or obvious headings.

## 6. Hand-rolled stdio MCP clients are brittle

Symptom:

- A custom terminal client hung during `initialize` or `tools/list`.

Proven fix:

- Prefer direct session MCP tools first.
- If terminal transport is needed, prefer official streamable HTTP mode over raw stdio experimentation.

## 7. Private docs generally need user-token mode

Symptom:

- Tenant-token reads or auto-token mode returned permission failures on documents the user could access interactively.

Proven fix:

- Use `useUAT=true` in direct tool calls.
- In terminal fallback mode, force `--token-mode user_access_token`.

## 8. Do not rewrite a working auth setup while debugging a read path

Symptom:

- A read failure triggers unnecessary changes to a working token helper, stored tokens, or MCP config.

Proven fix:

- Reuse any working auth setup first.
- Only rebuild OAuth or token plumbing when the actual failure is authentication-related.
