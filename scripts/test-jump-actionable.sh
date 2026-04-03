#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JUMP_SCRIPT="$CURRENT_DIR/jump-actionable.sh"
HELPERS_SCRIPT="$CURRENT_DIR/helpers.sh"

tmpdir="$(mktemp -d)"
socket="workspace-sidebar-jump-$$"
export XDG_CACHE_HOME="$tmpdir/cache"

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
	rm -rf "$tmpdir"
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s jump-test 'sleep 60'
socket_path="$(tmux -L "$socket" display-message -p -t jump-test:0 '#{socket_path}')"
export TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$socket_path"

tmux -S "$socket_path" split-window -d -t jump-test:0 'sleep 60'
tmux -S "$socket_path" split-window -d -t jump-test:0 'sleep 60'
tmux -S "$socket_path" select-layout -t jump-test:0 even-vertical >/dev/null

pane_ids=()
while IFS= read -r pane_id; do
	pane_ids+=("$pane_id")
done < <(tmux -S "$socket_path" list-panes -t jump-test:0 -F '#{pane_id}')

state_dir="$(
	source "$HELPERS_SCRIPT"
	state_dir
)"
mkdir -p "$state_dir"

PANE_ONE="${pane_ids[0]}" \
PANE_TWO="${pane_ids[1]}" \
PANE_THREE="${pane_ids[2]}" \
STATE_DIR="$state_dir" \
python3 - <<'PY'
import json
import os
from pathlib import Path

state_dir = Path(os.environ["STATE_DIR"])
payloads = [
    {"pane_id": os.environ["PANE_ONE"], "app": "codex", "status": "done", "message": "done", "updated_at": 30},
    {"pane_id": os.environ["PANE_TWO"], "app": "codex", "status": "error", "message": "error", "updated_at": 20},
    {"pane_id": os.environ["PANE_THREE"], "app": "codex", "status": "needs-input", "message": "input", "updated_at": 10},
]
for payload in payloads:
    path = state_dir / f"pane-{payload['pane_id']}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
PY

bash "$JUMP_SCRIPT" oldest "$socket_path"
selected_one="$(tmux -S "$socket_path" display-message -p '#{pane_id}')"
[ "$selected_one" = "${pane_ids[2]}" ] || {
	printf 'expected oldest actionable pane %s, got %s\n' "${pane_ids[2]}" "$selected_one" >&2
	exit 1
}

status_one="$(
	PANE_ID="${pane_ids[2]}" STATE_DIR="$state_dir" python3 - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["STATE_DIR"]) / f"pane-{os.environ['PANE_ID']}.json"
print(json.loads(path.read_text(encoding='utf-8')).get("status", ""))
PY
)"
[ "$status_one" = "idle" ] || {
	printf 'expected pane %s to clear to idle, got %s\n' "${pane_ids[2]}" "$status_one" >&2
	exit 1
}

bash "$JUMP_SCRIPT" next "$socket_path"
selected_two="$(tmux -S "$socket_path" display-message -p '#{pane_id}')"
[ "$selected_two" = "${pane_ids[1]}" ] || {
	printf 'expected next actionable pane %s, got %s\n' "${pane_ids[1]}" "$selected_two" >&2
	exit 1
}

printf 'jump actionable test passed\n'
