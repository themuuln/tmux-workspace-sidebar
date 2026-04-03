#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

pane_id="${1:-}"
set_socket_path_from_arg "${2:-}"

if [ -z "$pane_id" ]; then
	pane_id="$(tmux_cmd display-message -p '#{pane_id}' 2>/dev/null || true)"
fi

[ -n "$pane_id" ] || exit 0
[[ "$pane_id" =~ ^%[0-9]+$ ]] || exit 0

state_file="$(state_dir)/pane-$pane_id.json"
[ -f "$state_file" ] || exit 0

clear_result="$(
	run_sidebar_python_module tmux_workspace_sidebar.state clear-actionable \
		--state-file "$state_file"
)"

if [ "$clear_result" != "cleared" ]; then
	exit 0
fi

signal_sidebar_refresh
