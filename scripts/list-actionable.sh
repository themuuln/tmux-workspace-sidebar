#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

mode="${1:-tsv}"
set_socket_path_from_arg "${2:-}"

case "$mode" in
	tsv|picker)
		;;
	*)
		printf 'unsupported mode: %s\n' "$mode" >&2
		exit 1
		;;
esac

run_sidebar_python_module tmux_workspace_sidebar.state list-actionable \
	--mode "$mode" \
	--tmux-panes "$(
		tmux_cmd list-panes -a -F $'#{pane_id}\t#{session_id}\t#{session_name}\t#{window_id}\t#{window_name}\t#{pane_current_path}\t#{@workspace_sidebar}' 2>/dev/null || true
	)" \
	--state-dir "$(state_dir)"
