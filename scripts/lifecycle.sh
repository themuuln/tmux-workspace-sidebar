#!/usr/bin/env bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

sidebar_sync_lock_dir() {
	printf '%s/%s.sync.lock\n' "$(cache_dir)" "$(server_hash)"
}

with_sidebar_sync_lock() {
	local lock_dir
	local acquired=0
	local attempt
	lock_dir="$(sidebar_sync_lock_dir)"

	for attempt in $(seq 1 40); do
		if mkdir "$lock_dir" 2>/dev/null; then
			acquired=1
			break
		fi
		sleep 0.05
	done

	if [ "$acquired" -ne 1 ]; then
		return 75
	fi

	"$@"
	local status=$?
	rmdir "$lock_dir" 2>/dev/null || true
	return "$status"
}

ensure_sidebar_in_window() {
	local window_id="$1"
	local detached="${2:-1}"
	local sidebar_pane_id
	local non_sidebar_count

	sidebar_pane_id="$(sidebar_pane_in_window "$window_id")"
	if [ -n "$sidebar_pane_id" ]; then
		printf '%s\n' "$sidebar_pane_id"
		return 0
	fi

	non_sidebar_count="$(non_sidebar_pane_count_in_window "$window_id")"
	if [ "$non_sidebar_count" -le 0 ]; then
		return 0
	fi

	create_sidebar_in_window "$window_id" "$detached"
	sync_tmux_status_for_sidebar_presence
}

reconcile_sidebar_window() {
	local window_id="$1"
	local sidebar_pane_id
	local non_sidebar_count
	local configured_width
	local current_width

	sidebar_pane_id="$(sidebar_pane_in_window "$window_id")"
	non_sidebar_count="$(non_sidebar_pane_count_in_window "$window_id")"

	if [ -n "$sidebar_pane_id" ] && [ "$non_sidebar_count" -eq 0 ]; then
		tmux_cmd kill-pane -t "$sidebar_pane_id" 2>/dev/null || true
		sync_tmux_status_for_sidebar_presence
		return 0
	fi

	if [ "$non_sidebar_count" -le 0 ]; then
		return 0
	fi

	if [ -z "$sidebar_pane_id" ]; then
		sidebar_pane_id="$(create_sidebar_in_window "$window_id" "1")"
		sync_tmux_status_for_sidebar_presence
	fi

	configured_width="$(sidebar_width)"
	current_width="$(pane_width "$sidebar_pane_id")"
	if [ -n "$current_width" ] && [ "$current_width" != "$configured_width" ]; then
		tmux_cmd kill-pane -t "$sidebar_pane_id" 2>/dev/null || true
		sidebar_pane_id="$(create_sidebar_in_window "$window_id" "1")"
		sync_tmux_status_for_sidebar_presence
	fi

	resize_sidebar_pane_to_configured_width "$sidebar_pane_id"
}

reconcile_sidebar_state_impl() {
	local window_id
	local window_ids

	if [ "$(workspace_sidebar_enabled)" = "1" ]; then
		window_ids="$(all_window_ids)"
		while IFS= read -r window_id; do
			[ -n "$window_id" ] || continue
			reconcile_sidebar_window "$window_id"
		done <<< "$window_ids"
	fi

	sync_tmux_status_for_sidebar_presence
}

reconcile_sidebar_state() {
	local status

	if with_sidebar_sync_lock reconcile_sidebar_state_impl; then
		return 0
	fi

	status=$?
	# Hook-triggered syncs can overlap during rapid tmux events; if another
	# process already owns the sync lock, let that run complete without surfacing
	# a spurious error from this no-op attempt.
	if [ "$status" -eq 75 ]; then
		return 0
	fi

	return "$status"
}

enable_sidebar_global() {
	local window_id="$1"
	set_workspace_sidebar_enabled 1
	ensure_sidebar_in_window "$window_id" "1" >/dev/null
	reconcile_sidebar_state
}

disable_sidebar_global() {
	local pane_id
	local sidebar_pane_ids

	set_workspace_sidebar_enabled 0
	sidebar_pane_ids="$(all_sidebar_pane_ids)"
	while IFS= read -r pane_id; do
		[ -n "$pane_id" ] || continue
		tmux_cmd kill-pane -t "$pane_id"
	done <<< "$sidebar_pane_ids"
	sync_tmux_status_for_sidebar_presence
}

focus_sidebar_window() {
	local window_id="$1"
	local sidebar_pane_id

	if [ "$(workspace_sidebar_enabled)" != "1" ]; then
		set_workspace_sidebar_enabled 1
	fi
	sidebar_pane_id="$(ensure_sidebar_in_window "$window_id" "0")"
	reconcile_sidebar_state
	if [ -n "$sidebar_pane_id" ]; then
		tmux_cmd select-pane -t "$sidebar_pane_id"
	fi
}
