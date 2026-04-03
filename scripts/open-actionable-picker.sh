#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

popup_dir="${1:-}"
set_socket_path_from_arg "${2:-}"

entries="$(bash "$CURRENT_DIR/list-actionable.sh" picker "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}")"
if [ -z "$entries" ]; then
	entries='No actionable Codex notifications  ||| __empty__'
fi

source_file="$(mktemp)"
printf '%s\n' "$entries" > "$source_file"

quoted_source_file="$(printf "%q" "$source_file")"
quoted_socket_path="$(printf "%q" "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}")"
quoted_script="$(printf "%q" "$CURRENT_DIR/pick-actionable.sh")"

popup_dir="${popup_dir:-$(tmux_cmd display-message -p '#{pane_current_path}' 2>/dev/null || printf '%s' "$HOME")}"

tmux_cmd display-popup \
	-d "$popup_dir" \
	-w '85%' \
	-h '75%' \
	-E "WORKSPACE_SIDEBAR_PICKER_SOURCE_FILE=$quoted_source_file $quoted_script $quoted_socket_path" 2>/dev/null || {
	rm -f "$source_file"
	exit 0
}
