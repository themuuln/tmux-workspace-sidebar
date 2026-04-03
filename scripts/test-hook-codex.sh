#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$CURRENT_DIR/hook-codex.sh"

tmpdir="$(mktemp -d)"
socket="workspace-sidebar-hook-$$"
export XDG_CACHE_HOME="$tmpdir/cache"

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
	rm -rf "$tmpdir"
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s hook-test 'sleep 60'
export TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH
TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$(tmux -L "$socket" display-message -p -t hook-test:0 '#{socket_path}')"
export TMUX_PANE
TMUX_PANE="$(tmux -S "$TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH" list-panes -t hook-test:0 -F '#{pane_id}' | sed -n '1p')"

assert_status() {
	local payload="$1"
	local expected="$2"
	local actual

	bash "$HOOK_SCRIPT" "$payload"
	actual="$(
		python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["XDG_CACHE_HOME"]) / "tmux-workspace-sidebar"
pane_id = os.environ["TMUX_PANE"]
matches = sorted(root.glob(f"*/state/pane-{pane_id}.json"))
if not matches:
    print("")
    raise SystemExit(0)

with matches[-1].open("r", encoding="utf-8") as handle:
    data = json.load(handle)

print(data.get("status", ""))
PY
	)"

	if [ "$actual" != "$expected" ]; then
		printf 'expected status %s, got %s for payload %s\n' "$expected" "$actual" "$payload" >&2
		exit 1
	fi
}

assert_status '{"type":"agent-turn-start","message":"working"}' "running"
assert_status '{"status":"working","message":"working"}' "running"
assert_status '{"status":"in_progress","message":"working"}' "running"
assert_status '{"notification_type":"agent_turn_start","message":"working"}' "running"
assert_status '{"event":"agent.turn.progress","message":"working"}' "running"
assert_status '{"phase":"executing","message":"working"}' "running"
assert_status '{"hook_event_name":"SessionStart"}' "idle"
assert_status '{"hook_event_name":"UserPromptSubmit","prompt":"working"}' "running"
assert_status '{"type":"approval-requested","message":"approve"}' "needs-input"
assert_status '{"type":"blocked","message":"approve"}' "needs-input"
assert_status '{"type":"user-input-requested","message":"approve"}' "needs-input"
assert_status '{"hook_event_name":"Stop","last_assistant_message":"done"}' "done"
assert_status '{"type":"agent-turn-complete","message":"done"}' "done"

printf 'hook test passed\n'
