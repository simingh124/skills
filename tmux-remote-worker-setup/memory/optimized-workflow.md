# Optimized Remote Worker Setup Workflow

## Start Here

- Read this file first.
- Read `references/worker_setup_memory.md`.
- Read the newest 3 logs in `memory/runs/` if they exist.
- Prefer the helper script over ad-hoc shell work so future runs stay consistent and comparable.

## Current Best Path

1. Resolve the tmux session to a worker replica from pane scrollback.
2. Use local `/kubebrain/brainctl` as the control path; do not depend on the remote tmux pane for setup steps.
3. Build a local payload for `node`, `npm`, `npx`, `codex`, `rg`, local Codex skills, `.env`, `AGENTS.md`, and `feishu_notify.py`.
4. Copy payload contents to the worker through the shared mount and install them remotely.
5. Run `/home/i-huangsiming/work/install.sh`, then patch `notify` and trusted project entries in `/root/.codex/config.toml`.
6. Install `nvitop` through `/mnt/step3-abla/siming/.venv/bin/python -m pip`.
7. Verify command availability, config entries, host mapping, `feishu_notify.py` syntax, and that `gpu_util.py` is still running.

## Stable Lessons

- Prefer payload copy over `brainctl exec -i` file streaming for unattended runs in this environment.
- Keep the local helper implementation in shell; reserve `/mnt/step3-abla/siming/.venv/bin/python` for remote-side Python and pip work.
- Treat tmux as a discovery source only; use `brainctl exec` for the actual worker configuration.

## Update Rule

- After each invocation, add a JSON run log with `scripts/log_run.py`.
- Rebuild this file with `scripts/update_workflow.py`.
- If the run exposed a new durable lesson or pitfall, update `references/worker_setup_memory.md`.
