#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

action="${1:-oldest}"
set_socket_path_from_arg "${2:-}"

case "$action" in
	oldest|next)
		;;
	*)
		printf 'unsupported action: %s\n' "$action" >&2
		exit 1
		;;
esac

selection="$(
	run_sidebar_python_module tmux_workspace_sidebar.state select-actionable \
		--action "$action" \
		--current-pane-id "$(tmux_cmd display-message -p '#{pane_id}' 2>/dev/null || true)" \
		--tmux-panes "$(
			tmux_cmd list-panes -a -F $'#{pane_id}\t#{session_id}\t#{session_name}\t#{window_id}\t#{window_name}\t#{pane_current_path}\t#{@workspace_sidebar}' 2>/dev/null || true
		)" \
		--state-dir "$(state_dir)"
)"

[ -n "$selection" ] || {
	tmux_cmd display-message "No actionable Codex notifications"
	exit 0
}

target_session_id="$(printf '%s\n' "$selection" | sed -n '1p')"
target_window_id="$(printf '%s\n' "$selection" | sed -n '2p')"
target_pane_id="$(printf '%s\n' "$selection" | sed -n '3p')"

[ -n "$target_pane_id" ] || exit 0

tmux_cmd switch-client -t "$target_session_id" 2>/dev/null || true
tmux_cmd select-window -t "$target_window_id"
tmux_cmd select-pane -t "$target_pane_id"

"$CURRENT_DIR/clear-state.sh" "$target_pane_id" "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}"
