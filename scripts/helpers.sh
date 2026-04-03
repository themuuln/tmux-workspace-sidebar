#!/usr/bin/env bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$CURRENT_DIR/.." && pwd)"

set_socket_path_from_arg() {
	if [ -n "${1:-}" ]; then
		export TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$1"
	fi
}

tmux_cmd() {
	if [ -n "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}" ]; then
		tmux -S "$TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH" "$@"
	else
		tmux "$@"
	fi
}

tmux_option() {
	tmux_cmd show-option -gqv "$1"
}

run_sidebar_python_module() {
	local module="$1"
	shift
	PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" "$(sidebar_python)" -m "$module" "$@"
}

tmux_option_or_default() {
	local value
	value="$(tmux_option "$1")"
	if [ -n "$value" ]; then
		printf '%s\n' "$value"
	else
		printf '%s\n' "$2"
	fi
}

set_tmux_option_if_unset() {
	if [ -z "$(tmux_option "$1")" ]; then
		tmux_cmd set-option -gq "$1" "$2"
	fi
}

cache_dir() {
	printf '%s\n' "${XDG_CACHE_HOME:-$HOME/.cache}/tmux-workspace-sidebar"
}

state_dir() {
	printf '%s/%s/state\n' "$(cache_dir)" "$(server_hash)"
}

server_hash() {
	if [ -n "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}" ]; then
		printf '%s\n' "$TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH" | shasum -a 256 | awk '{print $1}'
	else
		tmux_cmd display-message -p "#{socket_path}" | shasum -a 256 | awk '{print $1}'
	fi
}

event_file() {
	local dir
	dir="$(cache_dir)"
	mkdir -p "$dir"
	printf '%s/%s.event\n' "$dir" "$(server_hash)"
}

signal_sidebar_refresh() {
	local pids

	pids="$(
		tmux_cmd list-panes -a -F $'#{pane_pid}\t#{@workspace_sidebar}' |
			awk -F '\t' '$2 == "1" { print $1 }'
	)"

	touch "$(event_file)"

	while IFS= read -r pid; do
		if [ -n "$pid" ]; then
			kill -USR1 "$pid" 2>/dev/null || true
		fi
	done <<< "$pids"
}

sidebar_width() {
	tmux_option_or_default "@workspace_sidebar_width" "32"
}

sidebar_position() {
	tmux_option_or_default "@workspace_sidebar_position" "left"
}

sidebar_python() {
	tmux_option_or_default "@workspace_sidebar_python" "python3"
}

push_notifications_enabled() {
	tmux_option_or_default "@workspace_sidebar_push_enabled" "0"
}

workspace_sidebar_enabled() {
	tmux_option_or_default "@workspace_sidebar_enabled" "0"
}

set_workspace_sidebar_enabled() {
	tmux_cmd set-option -gq "@workspace_sidebar_enabled" "$1"
}

saved_tmux_status() {
	tmux_option "@workspace_sidebar_saved_status"
}

save_tmux_status_for_sidebar() {
	if [ -n "$(saved_tmux_status)" ]; then
		return 0
	fi

	tmux_cmd set-option -gq "@workspace_sidebar_saved_status" "$(tmux_option_or_default "status" "on")"
}

hide_tmux_status_for_sidebar() {
	save_tmux_status_for_sidebar
	tmux_cmd set-option -gq status off
}

restore_tmux_status_from_sidebar() {
	local saved_status

	saved_status="$(saved_tmux_status)"
	if [ -z "$saved_status" ]; then
		return 0
	fi

	tmux_cmd set-option -gq status "$saved_status"
	tmux_cmd set-option -gu "@workspace_sidebar_saved_status" 2>/dev/null || true
}

current_window_id() {
	tmux_cmd display-message -p "#{window_id}"
}

all_window_ids() {
	tmux_cmd list-windows -a -F "#{window_id}" | awk 'NF && !seen[$0]++'
}

all_sidebar_pane_ids() {
	tmux_cmd list-panes -a -F $'#{pane_id}\t#{@workspace_sidebar}' |
		awk -F '\t' '$2 == "1" { print $1 }'
}

sidebar_pane_count() {
	tmux_cmd list-panes -a -F "#{@workspace_sidebar}" 2>/dev/null |
		awk '$1 == "1" { count++ } END { print count + 0 }'
}

sync_tmux_status_for_sidebar_presence() {
	local sidebar_count

	sidebar_count="$(sidebar_pane_count)"
	if [ "$sidebar_count" -gt 0 ]; then
		hide_tmux_status_for_sidebar
		return 0
	fi

	restore_tmux_status_from_sidebar
}

sidebar_pane_in_window() {
	local window_id="${1:-$(current_window_id)}"
	tmux_cmd list-panes -t "$window_id" -F $'#{pane_id}\t#{@workspace_sidebar}' |
		awk -F '\t' '$2 == "1" { print $1; exit }'
}

pane_width() {
	local pane_id="$1"
	tmux_cmd display-message -p -t "$pane_id" "#{pane_width}" 2>/dev/null || true
}

non_sidebar_pane_count_in_window() {
	local window_id="$1"
	local count

	count="$(
		tmux_cmd list-panes -t "$window_id" -F "#{@workspace_sidebar}" 2>/dev/null |
			awk '$1 != "1" { count++ } END { print count + 0 }'
	)"

	printf '%s\n' "${count:-0}"
}

non_sidebar_pane_in_window() {
	local window_id="${1:-$(current_window_id)}"

	tmux_cmd list-panes -t "$window_id" -F $'#{pane_id}\t#{pane_active}\t#{@workspace_sidebar}' |
		awk -F '\t' '
			$3 == "1" { next }
			$2 == "1" { print $1; found=1; exit }
			!fallback { fallback=$1 }
			END {
				if (!found && fallback) {
					print fallback
				}
			}
		'
}

normalize_current_window_focus() {
	local window_id="${1:-}"
	local is_sidebar
	local current_pane_id
	local target_pane_id
	local normalized=0

	if [ -z "$window_id" ]; then
		window_id="$(current_window_id 2>/dev/null || true)"
	fi
	[ -n "$window_id" ] || return 0

	current_pane_id="$(
		tmux_cmd list-panes -t "$window_id" -F $'#{pane_id}\t#{pane_active}' 2>/dev/null |
			awk -F '\t' '$2 == "1" { print $1; exit }'
	)"
	is_sidebar="$(
		tmux_cmd list-panes -t "$window_id" -F $'#{pane_active}\t#{@workspace_sidebar}' 2>/dev/null |
			awk -F '\t' '$1 == "1" { print $2; exit }'
	)"
	if [ "$is_sidebar" != "1" ]; then
		return 0
	fi

	tmux_cmd last-pane -t "$window_id" 2>/dev/null || true
	is_sidebar="$(
		tmux_cmd list-panes -t "$window_id" -F $'#{pane_active}\t#{@workspace_sidebar}' 2>/dev/null |
			awk -F '\t' '$1 == "1" { print $2; exit }'
	)"
	if [ "$is_sidebar" != "1" ]; then
		return 0
	fi

	target_pane_id="$(non_sidebar_pane_in_window "$window_id")"
	if [ -n "$target_pane_id" ] && [ "$target_pane_id" != "$current_pane_id" ]; then
		tmux_cmd select-pane -t "$target_pane_id"
		normalized=1
	fi

	return "$normalized"
}

create_sidebar_in_window() {
	local window_id="$1"
	local detached="${2:-1}"
	local position width launch_cmd
	local tmux_args
	local new_sidebar

	position="$(sidebar_position)"
	width="$(sidebar_width)"
	launch_cmd="$PLUGIN_DIR/scripts/launch.sh"

	tmux_args=(-t "$window_id" -h -f -l "$width" -P -F "#{pane_id}")

	if [ "$position" = "left" ]; then
		tmux_args=(-t "$window_id" -h -f -b -l "$width" -P -F "#{pane_id}")
	fi

	if [ "$detached" = "1" ]; then
		tmux_args=(-d "${tmux_args[@]}")
	fi

	new_sidebar="$(
		tmux_cmd split-window "${tmux_args[@]}" "$launch_cmd" </dev/null
	)"

	tmux_cmd set-option -pt "$new_sidebar" @workspace_sidebar 1
	printf '%s\n' "$new_sidebar"
}

resize_sidebar_pane_to_configured_width() {
	local pane_id="$1"
	local width

	[ -n "$pane_id" ] || return 0

	width="$(sidebar_width)"
	tmux_cmd resize-pane -t "$pane_id" -x "$width" 2>/dev/null || true
}
