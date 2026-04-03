#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

pane_id=""
app=""
status=""
message=""
updated_at=""

while [ "$#" -gt 0 ]; do
	case "$1" in
		--pane)
			pane_id="${2:-}"
			shift 2
			;;
		--app)
			app="${2:-}"
			shift 2
			;;
		--status)
			status="${2:-}"
			shift 2
			;;
		--message)
			message="${2:-}"
			shift 2
			;;
		--updated-at)
			updated_at="${2:-}"
			shift 2
			;;
		--socket-path)
			set_socket_path_from_arg "${2:-}"
			shift 2
			;;
		*)
			printf 'unknown arg: %s\n' "$1" >&2
			exit 1
			;;
	esac
done

if [ -z "$pane_id" ]; then
	pane_id="$(tmux_cmd display-message -p '#{pane_id}' 2>/dev/null || true)"
fi

[ -n "$pane_id" ] || exit 0
[[ "$pane_id" =~ ^%[0-9]+$ ]] || {
	printf 'invalid pane_id: %s\n' "$pane_id" >&2
	exit 1
}

if [ -z "$updated_at" ]; then
	updated_at="$(date +%s)"
fi
[[ "$updated_at" =~ ^[0-9]+$ ]] || {
	printf 'invalid updated_at: %s\n' "$updated_at" >&2
	exit 1
}

dir="$(state_dir)"
mkdir -p "$dir"
state_file="$dir/pane-$pane_id.json"
notify_statuses="$(tmux_option_or_default "@workspace_sidebar_push_statuses" "needs-input,error,done")"

metadata="$(tmux_cmd display-message -p -t "$pane_id" '#{session_id}|#{window_id}|#{pane_title}|#{pane_current_command}|#{pane_current_path}' 2>/dev/null || true)"
session_id=""
window_id=""
pane_title=""
pane_current_command=""
pane_current_path=""
if [ -n "$metadata" ]; then
	IFS='|' read -r session_id window_id pane_title pane_current_command pane_current_path <<EOF
$metadata
EOF
fi

apply_result="$(
	run_sidebar_python_module tmux_workspace_sidebar.state apply-state-update \
		--state-file "$state_file" \
		--pane-id "$pane_id" \
		--app "$app" \
		--status "$status" \
		--message "$message" \
		--updated-at "$updated_at" \
		--session-id "$session_id" \
		--window-id "$window_id" \
		--pane-title "$pane_title" \
		--pane-current-command "$pane_current_command" \
		--pane-current-path "$pane_current_path" \
		--notify-statuses "$notify_statuses"
)"

write_result="$(printf '%s\n' "$apply_result" | sed -n '1p')"
notification_payload="$(printf '%s\n' "$apply_result" | sed '1d')"

if [ "$write_result" = "written" ]; then
	signal_sidebar_refresh
fi

if [ -n "$notification_payload" ]; then
	"$CURRENT_DIR/push-notify.sh" "$notification_payload" >/dev/null 2>&1 &
fi
