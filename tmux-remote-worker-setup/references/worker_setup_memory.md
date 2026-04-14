# Worker Setup Memory

Use this file as the skill's reusable memory for remote worker setup.
Update it only when a run teaches a stable, high-value lesson that will likely help future worker configuration.

## Update rules

- Record only durable lessons: hidden dependencies, reliable fallbacks, failure signatures, or non-obvious verification strategy.
- Keep entries short and action-oriented.
- Do not record generic knowledge, routine success logs, or transient identifiers such as a single replica name.
- Rebuild `memory/optimized-workflow.md` after logging a run so the latest best path stays easy to reuse.
- If a run did not produce a meaningful new insight, leave this file unchanged.

## Current lessons

### 2026-04-13 - Prefer payload copy over stdin streaming for unattended runs

- Signal: `brainctl exec -i` could write the target file but the local process did not exit cleanly in this CLI environment.
- Lesson: for automated worker bootstrap, package `.env`, `AGENTS.md`, and `feishu_notify.py` into the shared payload and install them remotely instead of relying on stdin streaming.
- Why it matters: it avoids hung setup runs while keeping the resulting remote files identical.

### 2026-04-13 - Separate local automation constraints from remote worker constraints

- Signal: the local machine running Codex did not have `/mnt/step3-abla/siming/.venv/bin/python`, but the remote worker did.
- Lesson: keep the helper implementation local-side in `bash`, while continuing to enforce `/mnt/step3-abla/siming/.venv/bin/python` for remote-side Python and pip operations.
- Why it matters: it preserves the project rule for worker configuration without making the local skill runner brittle.

### 2026-04-14 - Keep helper payloads under the shared work tree

- Signal: payloads written under a skill install directory such as `~/.agents/skills/...` were not visible from the worker, even though `/home/i-huangsiming/work/...` was.
- Lesson: default helper workspaces to `/home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace` or another path under `/home/i-huangsiming/work`.
- Why it matters: it prevents false setup failures caused by an unreachable payload path.

### 2026-04-14 - Preload VS Code Server from a local cache or local download

- Signal: the worker's own VS Code Server download could stall at a few percent for minutes, while the same commit already existed in the local `~/.vscode-server` cache.
- Lesson: when the user provides a VS Code commit, stage that server locally first, then copy `/root/.vscode-server/cli/servers/<Quality>-<commit>/server` to the worker through the shared work tree.
- Why it matters: it removes the slow remote download from the critical path and keeps the remote server layout exactly where VS Code expects it.
