# skills

This repository hosts reusable Codex skills.

## Install

Install a specific skill from this repository with:

```bash
npx skills add https://github.com/simingh124/skills --skill read-paper-pro
```

List the skills available in this repository with:

```bash
npx skills add https://github.com/simingh124/skills --list
```

## Skills

### `tmux-remote-worker-setup`

Resolve a local tmux session such as `gpu` or `gpu2` to the matching remote worker replica, configure that worker into a Codex-ready environment through `brainctl`, verify the final setup, and keep improving the workflow over time through run logs plus reusable pitfall memory.

### `read-feishu-doc-custom`

Read and export Feishu/Lark wiki or doc content with `lark-mcp`, summarize documents, convert them to local Markdown, diagnose common wiki/doc token and auth issues, and maintain run-memory plus optimized workflow notes.

### `read-paper-pro`

Read an arXiv paper from a title, arXiv ID, or arXiv URL by resolving to the `src` tarball, analyzing the TeX source, and producing a precise Chinese research note with linked prior work, inline figures/tables, training details, experiment breakdowns, and concrete AI follow-up ideas.
