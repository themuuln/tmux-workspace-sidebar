#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

set_socket_path_from_arg "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}"

flutter_bin="${FLUTTER_BIN:-flutter}"
task="${1:-run}"

if [ "$#" -gt 0 ]; then
	shift
fi

last_status=""
last_message=""

emit_state() {
	local status="${1:-}"
	local message="${2:-}"
	[ -n "$status" ] || return 0
	if [ "$status" = "$last_status" ] && [ "$message" = "$last_message" ]; then
		return 0
	fi

	last_status="$status"
	last_message="$message"

	"$CURRENT_DIR/update-state.sh" \
		--socket-path "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}" \
		--pane "${TMUX_PANE:-}" \
		--app flutter \
		--status "$status" \
		--message "$message" >/dev/null
}

parse_flutter_line() {
	local line="${1:-}"
	local parsed
	parsed="$(
		run_sidebar_python_module tmux_workspace_sidebar.flutter parse-line \
			--line "$line" \
			--task "$task"
	)"
	printf '%s\n' "$parsed" | sed -n '1p'
	printf '%s\n' "$parsed" | sed '1d'
}

initial="$(
	run_sidebar_python_module tmux_workspace_sidebar.flutter parse-line \
		--event start \
		--task "$task"
)"
emit_state "$(printf '%s\n' "$initial" | sed -n '1p')" "$(printf '%s\n' "$initial" | sed '1d')"

set +e
"$flutter_bin" "$task" "$@" 2>&1 | while IFS= read -r line || [ -n "$line" ]; do
	printf '%s\n' "$line"
	parsed="$(parse_flutter_line "$line")"
	emit_state "$(printf '%s\n' "$parsed" | sed -n '1p')" "$(printf '%s\n' "$parsed" | sed '1d')"
done
command_status=${PIPESTATUS[0]}
set -e

if [ "$command_status" -eq 0 ]; then
	final="$(
		run_sidebar_python_module tmux_workspace_sidebar.flutter parse-line \
			--event done \
			--task "$task"
	)"
else
	final="$(
		run_sidebar_python_module tmux_workspace_sidebar.flutter parse-line \
			--event error \
			--task "$task"
	)"
fi

emit_state "$(printf '%s\n' "$final" | sed -n '1p')" "$(printf '%s\n' "$final" | sed '1d')"
exit "$command_status"
