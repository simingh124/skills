#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_WORKSPACE_DIR="$SKILL_DIR/workspace"

BRAINCTL="/kubebrain/brainctl"
PROXY_BOOTSTRAP='eval $(curl -s http://deploy.i.shaipower.com/httpproxy)'
DIRECT_PROXY_RESET='unset https_proxy http_proxy all_proxy'
REPLICA_RE='ws-[a-z0-9]+-jlaunch-[a-z0-9]+-cfcd2084'
JOB_RE='ws-[a-z0-9]+-jlaunch-[a-z0-9]+'
NODE_ROOT="$HOME/.nvm/versions/node/v22.16.0"
CODEX_HOME="$HOME/.codex"

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e ':a;N;$!ba;s/\n/\\n/g'
}

write_json_kv() {
  local path="$1"
  shift
  mkdir -p "$(dirname "$path")"
  {
    printf '{\n'
    local first=1
    while (($#)); do
      local key="$1"
      local value="$2"
      shift 2
      if ((first)); then
        first=0
      else
        printf ',\n'
      fi
      printf '  "%s": "%s"' "$(json_escape "$key")" "$(json_escape "$value")"
    done
    printf '\n}\n'
  } > "$path"
}

run_network_bash() {
  local body="$1"
  local stdin_file="${2:-}"
  if [[ -n "$stdin_file" ]]; then
    if bash -lc "set -euo pipefail; ${PROXY_BOOTSTRAP}; ${body}" < "$stdin_file"; then
      return 0
    fi
    echo "Proxy attempt failed, retrying once with direct network access." >&2
    bash -lc "set -euo pipefail; ${DIRECT_PROXY_RESET}; ${body}" < "$stdin_file"
    return 0
  fi

  if bash -lc "set -euo pipefail; ${PROXY_BOOTSTRAP}; ${body}"; then
    return 0
  fi

  echo "Proxy attempt failed, retrying once with direct network access." >&2
  bash -lc "set -euo pipefail; ${DIRECT_PROXY_RESET}; ${body}"
}

remote_exec_body() {
  local replica="$1"
  local remote_script="$2"
  local target="replicas.rjob.brainpp.cn/${replica}"
  printf '%s -n shai-core exec %q -- bash -lc %q' "$BRAINCTL" "$target" "$remote_script"
}

resolve_session() {
  local session_name="$1"
  local probe_lines="$2"
  local pane_line
  local active_line
  pane_line="$(tmux list-panes -t "$session_name" -F '#{pane_active}|#{session_name}:#{window_index}.#{pane_index}|#{pane_title}|#{pane_current_command}|#{pane_current_path}' | head -n 1)"
  active_line="$(tmux list-panes -t "$session_name" -F '#{pane_active}|#{session_name}:#{window_index}.#{pane_index}|#{pane_title}|#{pane_current_command}|#{pane_current_path}' | awk -F '|' '$1=="1" {print; exit}')"
  if [[ -n "$active_line" ]]; then
    pane_line="$active_line"
  fi

  local pane_target pane_title pane_command pane_path
  IFS='|' read -r _ pane_target pane_title pane_command pane_path <<< "$pane_line"

  local capture
  capture="$(tmux capture-pane -p -t "$pane_target" -S "-${probe_lines}")"
  local replica job_id derived_from_job_id=0
  replica="$(printf '%s\n' "$capture" | grep -oE "$REPLICA_RE" | tail -n 1 || true)"
  job_id="$(printf '%s\n' "$capture" | grep -oE "$JOB_RE" | tail -n 1 || true)"
  if [[ -z "$replica" && -n "$job_id" ]]; then
    replica="${job_id}-cfcd2084"
    derived_from_job_id=1
  fi

  if [[ -z "$replica" ]]; then
    echo "Could not resolve a replica from tmux scrollback. Preserve the launch logs in the pane history or provide the replica explicitly." >&2
    return 1
  fi

  local replica_line job_line
  replica_line="$(printf '%s\n' "$capture" | grep -F "$replica" | tail -n 1 || true)"
  job_line=""
  if [[ -n "$job_id" ]]; then
    job_line="$(printf '%s\n' "$capture" | grep -F "$job_id" | tail -n 1 || true)"
  fi

  RESOLVED_SESSION_NAME="$session_name"
  RESOLVED_PANE_TARGET="$pane_target"
  RESOLVED_PANE_TITLE="$pane_title"
  RESOLVED_PANE_COMMAND="$pane_command"
  RESOLVED_PANE_PATH="$pane_path"
  RESOLVED_REPLICA="$replica"
  RESOLVED_JOB_ID="$job_id"
  RESOLVED_DERIVED_FROM_JOB_ID="$derived_from_job_id"
  RESOLVED_REPLICA_LINE="$replica_line"
  RESOLVED_JOB_LINE="$job_line"

  printf '{\n'
  printf '  "session_name": "%s",\n' "$(json_escape "$RESOLVED_SESSION_NAME")"
  printf '  "pane_target": "%s",\n' "$(json_escape "$RESOLVED_PANE_TARGET")"
  printf '  "pane_title": "%s",\n' "$(json_escape "$RESOLVED_PANE_TITLE")"
  printf '  "pane_current_command": "%s",\n' "$(json_escape "$RESOLVED_PANE_COMMAND")"
  printf '  "pane_current_path": "%s",\n' "$(json_escape "$RESOLVED_PANE_PATH")"
  printf '  "replica": "%s",\n' "$(json_escape "$RESOLVED_REPLICA")"
  printf '  "job_id": "%s",\n' "$(json_escape "$RESOLVED_JOB_ID")"
  printf '  "derived_from_job_id": "%s",\n' "$RESOLVED_DERIVED_FROM_JOB_ID"
  printf '  "replica_line": "%s",\n' "$(json_escape "$RESOLVED_REPLICA_LINE")"
  printf '  "job_id_line": "%s"\n' "$(json_escape "$RESOLVED_JOB_LINE")"
  printf '}\n'
}

build_payload() {
  local payload_dir="$1"
  rm -rf "$payload_dir"
  mkdir -p \
    "$payload_dir/node-v22.16.0/bin" \
    "$payload_dir/node-v22.16.0/lib/node_modules/@openai" \
    "$payload_dir/bin" \
    "$payload_dir/codex_home"

  cp -a "$NODE_ROOT/bin/node" "$payload_dir/node-v22.16.0/bin/"
  cp -a "$NODE_ROOT/bin/npm" "$payload_dir/node-v22.16.0/bin/"
  cp -a "$NODE_ROOT/bin/npx" "$payload_dir/node-v22.16.0/bin/"
  cp -a "$NODE_ROOT/bin/codex" "$payload_dir/node-v22.16.0/bin/"
  cp -a "$NODE_ROOT/lib/node_modules/npm" "$payload_dir/node-v22.16.0/lib/node_modules/"
  cp -a "$NODE_ROOT/lib/node_modules/@openai/codex" "$payload_dir/node-v22.16.0/lib/node_modules/@openai/"
  cp -a /usr/bin/rg "$payload_dir/bin/"
  cp -a "$CODEX_HOME/skills" "$payload_dir/codex_home/"
  cp -a "$CODEX_HOME/.env" "$payload_dir/codex_home/.env"
  cp -a "$CODEX_HOME/AGENTS.md" "$payload_dir/codex_home/AGENTS.md"
  cp -a "$CODEX_HOME/feishu_notify.py" "$payload_dir/codex_home/feishu_notify.py"
}

configure_session() {
  local session_name="$1"
  local probe_lines="$2"
  local workspace_dir="$3"
  local timestamp run_dir payload_dir
  timestamp="$(date +%Y%m%d-%H%M%S)"
  run_dir="$workspace_dir/runs/${timestamp}-${session_name}"
  payload_dir="$workspace_dir/runtime/payloads/${session_name}-${timestamp}"
  mkdir -p "$run_dir"

  resolve_session "$session_name" "$probe_lines" > "$run_dir/session_context.json"
  build_payload "$payload_dir"
  write_json_kv "$run_dir/payload_manifest.json" \
    "payload_dir" "$payload_dir" \
    "node_root" "$NODE_ROOT" \
    "codex_home" "$CODEX_HOME"

  run_network_bash "$(remote_exec_body "$RESOLVED_REPLICA" $'set -euo pipefail\nhostname\nwhoami\npwd\ntest -x /mnt/step3-abla/siming/.venv/bin/python\necho python_venv_ok')" \
    > "$run_dir/access_check.txt" \
    2> "$run_dir/access_check.stderr.txt"

  local remote_setup_script
  remote_setup_script="$(cat <<EOF
set -euo pipefail
PAYLOAD=$(printf '%q' "$payload_dir")

test -d "\$PAYLOAD"
mkdir -p /root/.local /root/.codex /root/.ssh /usr/local/bin
rm -rf /root/.local/node-v22.16.0 /root/.codex/skills

tar -C "\$PAYLOAD" -cf - node-v22.16.0 | tar -C /root/.local -xf -
tar -C "\$PAYLOAD/codex_home" -cf - skills | tar -C /root/.codex -xf -

install -m 755 "\$PAYLOAD/bin/rg" /usr/local/bin/rg
ln -sfn /root/.local/node-v22.16.0/bin/node /usr/local/bin/node
ln -sfn /root/.local/node-v22.16.0/bin/npm /usr/local/bin/npm
ln -sfn /root/.local/node-v22.16.0/bin/npx /usr/local/bin/npx
ln -sfn /root/.local/node-v22.16.0/bin/codex /usr/local/bin/codex

chmod 700 /root/.codex /root/.ssh
grep -qxF "64.23.143.133 crs.us.bestony.com" /etc/hosts || echo "64.23.143.133 crs.us.bestony.com" >> /etc/hosts

bash /home/i-huangsiming/work/install.sh

CONFIG=/root/.codex/config.toml
if grep -q '^notify = ' "\$CONFIG"; then
  sed -i 's#^notify = .*#notify = ["python3", "/root/.codex/feishu_notify.py"]#' "\$CONFIG"
else
  printf '\nnotify = ["python3", "/root/.codex/feishu_notify.py"]\n' >> "\$CONFIG"
fi

grep -q '^\[projects\."\/workspace"\]' "\$CONFIG" || cat <<'CFG' >> "\$CONFIG"

[projects."/workspace"]
trust_level = "trusted"
CFG

grep -q '^\[projects\."\/home\/i-huangsiming\/work"\]' "\$CONFIG" || cat <<'CFG' >> "\$CONFIG"

[projects."/home/i-huangsiming/work"]
trust_level = "trusted"
CFG

install -m 600 "\$PAYLOAD/codex_home/.env" /root/.codex/.env
install -m 644 "\$PAYLOAD/codex_home/AGENTS.md" /root/.codex/AGENTS.md
install -m 755 "\$PAYLOAD/codex_home/feishu_notify.py" /root/.codex/feishu_notify.py

/mnt/step3-abla/siming/.venv/bin/python -m pip install \
  -i https://artifactory.stepfun-inc.com/artifactory/api/pypi/pypi-public/simple/ \
  --trusted-host artifactory.stepfun-inc.com \
  nvitop
ln -sfn /mnt/step3-abla/siming/.venv/bin/nvitop /usr/local/bin/nvitop
EOF
)"

  run_network_bash "$(remote_exec_body "$RESOLVED_REPLICA" "$remote_setup_script")" \
    > "$run_dir/remote_setup.stdout.txt" \
    2> "$run_dir/remote_setup.stderr.txt"

  local verification_script
  verification_script="$(cat <<'EOF'
set -euo pipefail
command -v node npm npx codex rg nvitop
node -v
npm -v
codex --version
rg --version | head -n 1
nvitop --version | head -n 1
grep -n 'notify = ' /root/.codex/config.toml
grep -n '\[projects."/workspace"\]' /root/.codex/config.toml
grep -n '\[projects."/home/i-huangsiming/work"\]' /root/.codex/config.toml
grep -n 'crs\.us\.bestony\.com' /etc/hosts
/mnt/step3-abla/siming/.venv/bin/python -c 'from pathlib import Path; compile(Path("/root/.codex/feishu_notify.py").read_text(encoding="utf-8"), "/root/.codex/feishu_notify.py", "exec"); print("notify_py_ok")'
pgrep -af "/home/i-huangsiming/work/tools/gpu_util.py"
EOF
)"

  run_network_bash "$(remote_exec_body "$RESOLVED_REPLICA" "$verification_script")" \
    > "$run_dir/verification.txt" \
    2> "$run_dir/verification.stderr.txt"

  write_json_kv "$run_dir/summary.json" \
    "session_name" "$RESOLVED_SESSION_NAME" \
    "replica" "$RESOLVED_REPLICA" \
    "run_dir" "$run_dir" \
    "payload_dir" "$payload_dir" \
    "pane_target" "$RESOLVED_PANE_TARGET" \
    "pane_title" "$RESOLVED_PANE_TITLE" \
    "verification_file" "$run_dir/verification.txt" \
    "session_context_file" "$run_dir/session_context.json"

  cat "$run_dir/summary.json"
}

usage() {
  cat <<'EOF'
Usage:
  setup_remote_worker_from_tmux.sh resolve <tmux-session-name> [--probe-lines N]
  setup_remote_worker_from_tmux.sh configure <tmux-session-name> [--probe-lines N] [--workspace-dir DIR]
EOF
}

if (($# < 2)); then
  usage >&2
  exit 1
fi

command="$1"
shift
session_name="$1"
shift
probe_lines=4000
workspace_dir="$DEFAULT_WORKSPACE_DIR"

while (($#)); do
  case "$1" in
    --probe-lines)
      probe_lines="$2"
      shift 2
      ;;
    --workspace-dir)
      workspace_dir="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

case "$command" in
  resolve)
    resolve_session "$session_name" "$probe_lines"
    ;;
  configure)
    configure_session "$session_name" "$probe_lines" "$workspace_dir"
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
