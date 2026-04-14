---
name: tmux-remote-worker-setup
description: Configure a Codex-ready remote GPU worker when the user gives a local tmux session name such as `gpu`, `gpu2`, or another session that already maps to a launched worker. Use this whenever the user wants to set up, repair, or verify the remote server behind a tmux session for Codex, `brainctl`, Node/Codex binaries, `rg`, `nvitop`, or remote worker environment bootstrap, even if they only mention the tmux session name and not the replica. Also use it when the user wants to accumulate reusable worker-setup lessons, harden the workflow against newly observed pitfalls, or keep improving the skill's remote-worker robustness over time.
---

# Tmux Remote Worker Setup

Use this skill when the user points at an existing local tmux session and wants the matching remote worker configured for Codex.

## What this skill does

- Reads `memory/optimized-workflow.md` and recent run logs before acting so the latest proven workflow is reused.
- Reads `references/worker_setup_memory.md` before acting so prior pitfalls and proven fixes are reused.
- Reads tmux pane metadata and scrollback to resolve the worker replica tied to the named session.
- Uses local `/kubebrain/brainctl` as the primary control path; the tmux session is only used to discover the worker.
- Builds a local offline payload for `node`, `npm`, `npx`, `codex`, `rg`, and local Codex skills, then installs them onto the remote worker.
- Installs a remote Codex bootstrap skill set during setup so the worker can use `read-paper-pro`, `find-skills`, `skill-creator`, `pdf`, `academic-researcher`, and `arxiv-search` immediately after bootstrap.
- Copies `~/.codex/.env`, `~/.codex/AGENTS.md`, and `~/.codex/feishu_notify.py` through the local payload so the worker gets the same Codex config without manual paste.
- Verifies the final remote environment and checks that `python /home/i-huangsiming/work/tools/gpu_util.py` is still running.

## Important rules

- Use the exact tmux session name the user gave you. If they did not provide one, ask for it.
- Do not guess the replica. The helper script extracts the latest `replica=` / `pod=` / `JOB_ID=` evidence from tmux history. If that evidence is missing, stop and ask the user for a session with preserved scrollback or for the explicit replica name.
- Always use the absolute brainctl path `/kubebrain/brainctl`.
- Keep Python execution inside `/mnt/step3-abla/siming/.venv/bin/python`.
- Do not interrupt the tmux pane or kill `gpu_util.py` unless the user explicitly asks. This workflow configures the worker through local `brainctl exec`, so the foreground process in tmux can stay untouched.

## Self-evolution loop

Before running the helper:

1. Read `memory/optimized-workflow.md`.
2. Read `references/worker_setup_memory.md`.
3. Read the newest 3 logs in `memory/runs/` if they exist.
4. Reuse any existing workaround or validation step that matches the current failure mode or environment.

After each configure or repair run:

1. Inspect the current run artifacts in the workspace, especially:
   - `.../session_context.json`
   - `.../access_check.txt`
   - `.../remote_setup.stdout.txt`
   - `.../remote_setup.stderr.txt`
   - `.../verification.txt`
   - `.../verification.stderr.txt`
2. Decide whether the run produced a new durable lesson:
   - a non-obvious failure signature
   - a more reliable fallback
   - a hidden dependency
   - a better verification technique
3. Record the run with `python3 scripts/log_run.py ...`.
4. Rebuild `memory/optimized-workflow.md` with `python3 scripts/update_workflow.py`.
5. If the run produced a new durable lesson, add a concise entry to `references/worker_setup_memory.md`.
6. If the run only repeated known behavior, keep `references/worker_setup_memory.md` unchanged.

When updating memory, prefer this shape:

- `Signal:` what was observed
- `Lesson:` the reusable decision or workaround
- `Why it matters:` how it improves future robustness

The goal is to make future worker setup more reliable, not to create a run log.

## Default workflow

1. Run the helper wrapper from this skill directory:

```bash
scripts/setup_remote_worker_from_tmux.sh configure <tmux-session-name> \
  --workspace-dir workspace
```

2. Read these generated files before replying:

- `memory/optimized-workflow.md`
- `references/worker_setup_memory.md`
- `workspace/.../session_context.json`
- `workspace/.../access_check.txt`
- `workspace/.../verification.txt`
- `workspace/.../summary.json`

3. Report back:

- resolved tmux session -> replica mapping
- whether setup finished successfully
- versions found for `codex`, `node`, `npm`, `rg`, and `nvitop`
- confirmation that the required remote skills were installed: `read-paper-pro`, `find-skills`, `skill-creator`, `pdf`, `academic-researcher`, and `arxiv-search`
- confirmation that `notify` and trusted-project config were written
- confirmation that `gpu_util.py` is still running

## Run log shape

Use `scripts/log_run.py` with fields such as:

- `request`
- `status`
- `session_name`
- `replica`
- `issues`
- `lessons`
- `actions`
- `outputs`
- `notes`

Keep logs concise and durable. Avoid secrets and transient noise.

## If proxy/bootstrap fails

The helper script first runs networked commands with:

```bash
eval $(curl -s http://deploy.i.shaipower.com/httpproxy)
```

If that attempt fails, it retries once after:

```bash
unset https_proxy http_proxy all_proxy
```

If both attempts fail, surface the error instead of inventing a workaround.

## Example prompts that should trigger this skill

- "帮我把 tmux 里的 gpu2 对应远端机器配成能跑 codex 的环境"
- "tmux session 名叫 gpu，帮我修一下对应 worker 的 codex / node / nvitop 配置"
- "我只知道 tmux session 是 gpu2，你直接把那台远端服务器环境配置好"
