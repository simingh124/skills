# Optimized Remote Worker Setup Workflow

Last rebuilt: 2026-04-14T16:13:31Z

## Start Here

- Read this file first.
- Read `references/worker_setup_memory.md`.
- Read the newest 3 logs in `memory/runs/` if they exist.
- Prefer the helper script over ad-hoc shell work so future runs stay consistent and comparable.
- Keep helper payloads under `/home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace` so the worker can read them through the shared mount.

## Current Best Path

1. Resolve the tmux session to a worker replica from pane scrollback.
2. Use local `/kubebrain/brainctl` as the control path; do not depend on the remote tmux pane for setup steps.
3. Build the payload under `/home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace`.
4. Package `node`, `npm`, `npx`, `codex`, `rg`, local Codex skills, `.env`, `AGENTS.md`, and `feishu_notify.py` into that payload.
5. Copy payload contents to the worker through the shared mount and install them remotely.
6. Run `/home/i-huangsiming/work/install.sh`, then patch `notify` and trusted project entries in `/root/.codex/config.toml`.
7. Install the remote Codex skill bundle through `npx skills add ... --global`: `read-paper-pro`, `find-skills`, `skill-creator`, `pdf`, `academic-researcher`, and `arxiv-search`.
8. Install `nvitop` through `/mnt/step3-abla/siming/.venv/bin/python -m pip`.
9. Verify command availability, config entries, host mapping, `feishu_notify.py` syntax, the required skill installations, and that `gpu_util.py` is still running.

## Optional VS Code Remote Preload Path

1. Extract the exact VS Code commit from the user's local Remote log or reuse a matching local `~/.vscode-server` cache entry.
2. Stage the VS Code server under `/home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace` by reusing the local cache or downloading the tarball locally.
3. Copy the staged `server/` tree to `/root/.vscode-server/cli/servers/<Quality>-<commit>/server` on the worker.
4. Verify that `server/bin/code-server` exists before asking the user to reconnect from VS Code.

## Dynamic Guardrails From Runs

- [1x] Workspace under the skill directory was not visible on the worker; rerun with --workspace-dir on /home/i-huangsiming/work.
- [1x] Remote VS Code Server download was slow enough to stall around 2%.

## Stable Lessons

- [1x] Use an absolute --workspace-dir under /home/i-huangsiming/work so the worker can read the generated payload.
- [1x] Default helper workspaces to /home/i-huangsiming/work/codex_assets/.tmux_remote_worker_setup_workspace so payloads stay visible to the worker.
- [1x] Preload VS Code Server from the local cache or a local download, then copy it through the shared work tree.

## Last 5 Runs

- 2026-04-14T15-30-48Z | success | gpu | success
- 2026-04-14T15-53-51Z | success | gpu | install vscode server | success

## Update Rule

- After each invocation, add a JSON run log with `scripts/log_run.py`.
- Rebuild this file with `scripts/update_workflow.py`.
- If the run exposed a new durable lesson or pitfall, update `references/worker_setup_memory.md`.
