# Terminal Fallback

Open this file only when direct in-session `mcp__lark_mcp__...` tool functions are unavailable or broken.

## Goal

Recover the ability to read a Feishu wiki or doc without reintroducing the older OpenClaw detour.

## Fallback Order

1. Verify local MCP configuration.
2. Reuse any existing user-token helper or stored OAuth setup if the environment already has one.
3. Prefer streamable HTTP fallback over raw stdio experiments.
4. Only revisit OAuth if the refreshable user token is truly invalid.

## Existing Setup

- Reuse any working `lark-mcp` config, token helper, or stored OAuth tokens that already exist in the current environment.
- Do not assume fixed paths for those files.
- Do not rewrite working auth infrastructure unless the read path is actually broken.

## Quick Checks

Confirm that Codex still sees the configured MCP server:

```bash
codex mcp list
```

Confirm the CLI transport modes if you need to run the server manually:

```bash
npx -y @larksuiteoapi/lark-mcp mcp --help
```

## Preferred Manual Launch Shape

Use an existing helper or other valid token source to fetch a fresh user token, then start `lark-mcp` in streamable mode with doc tools enabled.

Pseudo-shape:

```bash
FEISHU_USER_ACCESS_TOKEN="$(get_or_refresh_user_token_somehow)"
npx -y @larksuiteoapi/lark-mcp mcp \
  -a "$FEISHU_APP_ID" \
  -s "$FEISHU_APP_SECRET" \
  -u "$FEISHU_USER_ACCESS_TOKEN" \
  --token-mode user_access_token \
  -t preset.doc.default \
  -m streamable \
  --host localhost \
  -p 3000
```

## Read Sequence After the Server Is Up

1. Resolve a wiki URL token with `wiki_v2_space_getNode`.
2. Read the resolved `obj_token` through `docx_v1_document_rawContent`.
3. Convert the plaintext result into a local Markdown file.
4. If the user asked for a Markdown file and did not give a filename, use the Feishu document title as the default filename.

## When to Revisit OAuth

Only revisit OAuth when all of the following are true:

- the helper cannot refresh a valid user token
- direct MCP calls fail with auth errors
- the stored token file is missing or unusable

If redirect errors reappear, revisit the redirect URL first before changing anything else.
