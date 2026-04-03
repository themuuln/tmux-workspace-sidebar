#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PICK_SCRIPT="$CURRENT_DIR/pick-actionable.sh"
OPEN_SCRIPT="$CURRENT_DIR/open-actionable-picker.sh"
HELPERS_SCRIPT="$CURRENT_DIR/helpers.sh"

tmpdir="$(mktemp -d)"
socket="workspace-sidebar-pick-$$"
export XDG_CACHE_HOME="$tmpdir/cache"

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
	rm -rf "$tmpdir"
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s pick-test 'sleep 60'
socket_path="$(tmux -L "$socket" display-message -p -t pick-test:0 '#{socket_path}')"
export TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$socket_path"

tmux -S "$socket_path" split-window -d -t pick-test:0 'sleep 60'
tmux -S "$socket_path" split-window -d -t pick-test:0 'sleep 60'
tmux -S "$socket_path" select-layout -t pick-test:0 even-vertical >/dev/null

pane_ids=()
while IFS= read -r pane_id; do
	pane_ids+=("$pane_id")
done < <(tmux -S "$socket_path" list-panes -t pick-test:0 -F '#{pane_id}')

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

picker_source="$(mktemp)"
trap 'rm -f "$picker_source"; cleanup' EXIT
TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$socket_path" bash "$CURRENT_DIR/list-actionable.sh" picker "$socket_path" > "$picker_source"
WORKSPACE_SIDEBAR_PICKER_FLAGS='--take-1' WORKSPACE_SIDEBAR_PICKER_SOURCE_FILE="$picker_source" bash "$PICK_SCRIPT" "$socket_path"
selected="$(tmux -S "$socket_path" display-message -p '#{pane_id}')"
[ "$selected" = "${pane_ids[2]}" ] || {
	printf 'expected picker to select pane %s, got %s\n' "${pane_ids[2]}" "$selected" >&2
	exit 1
}

empty_source="$(mktemp)"
trap 'rm -f "$empty_source" "$picker_source"; cleanup' EXIT
printf 'No actionable Codex notifications  ||| __empty__\n' > "$empty_source"
WORKSPACE_SIDEBAR_PICKER_FLAGS='--take-1' WORKSPACE_SIDEBAR_PICKER_SOURCE_FILE="$empty_source" bash "$PICK_SCRIPT" "$socket_path"

mock_bin_dir="$(mktemp -d)"
mock_tv="$mock_bin_dir/tv"
themed_picker_source="$(mktemp)"
trap 'rm -rf "$mock_bin_dir"; rm -f "$themed_picker_source" "$empty_source" "$picker_source"; cleanup' EXIT
TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$socket_path" bash "$CURRENT_DIR/list-actionable.sh" picker "$socket_path" > "$themed_picker_source"
cat > "$mock_tv" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

config_file=""
while [ "$#" -gt 0 ]; do
	case "$1" in
		--config-file)
			config_file="${2:-}"
			shift 2
			;;
		*)
			shift
			;;
	esac
done

[ -n "$config_file" ] || {
	printf 'expected --config-file\n' >&2
	exit 1
}

grep -q 'theme = "mystic"' "$config_file" || {
	printf 'expected picker theme override in %s\n' "$config_file" >&2
	exit 1
}
grep -q 'selection_bg = "#112233"' "$config_file" || {
	printf 'expected selection_bg override in %s\n' "$config_file" >&2
	exit 1
}
grep -q 'selection_fg = "#ddeeff"' "$config_file" || {
	printf 'expected selection_fg override in %s\n' "$config_file" >&2
	exit 1
}

printf '%s\n' "$MOCK_TV_SELECTION"
EOF
chmod +x "$mock_tv"

tmux -S "$socket_path" set-option -gq @workspace_sidebar_inbox_picker_theme 'mystic'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_inbox_picker_selection_bg '#112233'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_inbox_picker_selection_fg '#ddeeff'
MOCK_TV_SELECTION="${pane_ids[1]}" PATH="$mock_bin_dir:$PATH" WORKSPACE_SIDEBAR_PICKER_SOURCE_FILE="$themed_picker_source" bash "$PICK_SCRIPT" "$socket_path"
selected_with_theme="$(tmux -S "$socket_path" display-message -p '#{pane_id}')"
[ "$selected_with_theme" = "${pane_ids[1]}" ] || {
	printf 'expected themed picker to select pane %s, got %s\n' "${pane_ids[1]}" "$selected_with_theme" >&2
	exit 1
}

printf 'pick actionable test passed\n'
