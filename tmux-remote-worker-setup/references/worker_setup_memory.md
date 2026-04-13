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
