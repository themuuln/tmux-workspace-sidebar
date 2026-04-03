#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$CURRENT_DIR/.." && pwd)"

socket="workspace-sidebar-smoke-$$"

wait_for_sidebar_count() {
	local socket_path="$1"
	local window_id="$2"
	local expected="$3"
	local count=""

	for _ in $(seq 1 30); do
		count="$(
			tmux -S "$socket_path" list-panes -t "$window_id" -F '#{@workspace_sidebar}' 2>/dev/null |
				awk '$1 == "1" {count++} END {print count + 0}'
		)"
		if [ "$count" -eq "$expected" ]; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected %s sidebar in window %s, got %s\n' "$expected" "$window_id" "$count" >&2
	return 1
}

wait_for_window_closed() {
	local socket_path="$1"
	local window_id="$2"

	for _ in $(seq 1 30); do
		if ! tmux -S "$socket_path" list-panes -t "$window_id" >/dev/null 2>&1; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected original window %s to disappear after orphan cleanup\n' "$window_id" >&2
	return 1
}

wait_for_total_sidebars() {
	local socket_path="$1"
	local expected="$2"
	local count=""

	for _ in $(seq 1 30); do
		count="$(
			tmux -S "$socket_path" list-panes -a -F '#{@workspace_sidebar}' 2>/dev/null |
				awk '$1 == "1" {count++} END {print count + 0}'
		)"
		if [ "$count" -eq "$expected" ]; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected %s total sidebars, got %s\n' "$expected" "$count" >&2
	return 1
}

wait_for_status_value() {
	local socket_path="$1"
	local expected="$2"
	local actual=""

	for _ in $(seq 1 30); do
		actual="$(tmux -S "$socket_path" show-option -gqv status 2>/dev/null || true)"
		if [ "$actual" = "$expected" ]; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected tmux status %s, got %s\n' "$expected" "$actual" >&2
	return 1
}

wait_for_active_sidebar_flag() {
	local socket_path="$1"
	local window_id="$2"
	local expected="$3"
	local actual=""

	for _ in $(seq 1 30); do
		actual="$(
			tmux -S "$socket_path" list-panes -t "$window_id" -F $'#{pane_active}\t#{@workspace_sidebar}' 2>/dev/null |
				awk -F '\t' '$1 == "1" { print $2; exit }'
		)"
		if [ "${actual:-0}" = "$expected" ]; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected active pane sidebar flag %s in window %s, got %s\n' "$expected" "$window_id" "${actual:-}" >&2
	return 1
}

wait_for_sidebar_width() {
	local socket_path="$1"
	local window_id="$2"
	local expected="$3"
	local actual=""

	for _ in $(seq 1 30); do
		actual="$(
			tmux -S "$socket_path" list-panes -t "$window_id" -F $'#{pane_width}\t#{@workspace_sidebar}' 2>/dev/null |
				awk -F '\t' '$2 == "1" { print $1; exit }'
		)"
		if [ "$actual" = "$expected" ]; then
			return 0
		fi
		sleep 0.2
	done

	printf 'expected sidebar width %s in window %s, got %s\n' "$expected" "$window_id" "${actual:-}" >&2
	return 1
}

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s s1 'sleep 60'
tmux -L "$socket" new-window -d -t s1: -n second 'sleep 60'
tmux -L "$socket" new-session -d -s s2 'sleep 60'
tmux -L "$socket" run-shell "$PLUGIN_DIR/sidebar.tmux"
tmux -L "$socket" set-option -gq status on
tmux -L "$socket" set-option -gq @workspace_sidebar_width 32

window_id="$(tmux -L "$socket" display-message -p -t s1:0 '#{window_id}')"
socket_path="$(tmux -L "$socket" display-message -p -t s1:0 '#{socket_path}')"

"$CURRENT_DIR/toggle.sh" toggle "$window_id" "$socket_path"
wait_for_status_value "$socket_path" "off" || exit 1

for wid in $(tmux -S "$socket_path" list-windows -a -F '#{window_id}' | awk '!seen[$0]++'); do
	wait_for_sidebar_count "$socket_path" "$wid" 1 || exit 1
done
wait_for_sidebar_width "$socket_path" "$window_id" "32" || exit 1

primary_pane="$(tmux -S "$socket_path" list-panes -t "$window_id" -F '#{pane_id} #{@workspace_sidebar}' | awk '$2 != 1 {print $1; exit}')"
tmux -S "$socket_path" split-window -d -h -t "$primary_pane" 'sleep 60'
tmux -S "$socket_path" select-layout -t "$window_id" even-vertical >/dev/null
wait_for_sidebar_width "$socket_path" "$window_id" "32" || exit 1

secondary_pane="$(tmux -S "$socket_path" list-panes -t "$window_id" -F '#{pane_id} #{@workspace_sidebar}' | awk '$2 != 1 {print $1}' | sed -n '2p')"
tmux -S "$socket_path" kill-pane -t "$secondary_pane"
wait_for_sidebar_width "$socket_path" "$window_id" "32" || exit 1

tmux -S "$socket_path" new-window -d -t s2: -n third 'sleep 60'

new_window_id="$(tmux -S "$socket_path" display-message -p -t s2:1 '#{window_id}')"
wait_for_sidebar_count "$socket_path" "$new_window_id" 1 || exit 1

"$CURRENT_DIR/toggle.sh" focus "$new_window_id" "$socket_path"
wait_for_active_sidebar_flag "$socket_path" "$new_window_id" 1 || exit 1
"$CURRENT_DIR/notify.sh" normalize-focus "$socket_path" "$new_window_id"
wait_for_active_sidebar_flag "$socket_path" "$new_window_id" 0 || exit 1

main_pane="$(tmux -S "$socket_path" list-panes -t "$window_id" -F '#{pane_id} #{@workspace_sidebar}' | awk '$2 != 1 {print $1; exit}')"
tmux -S "$socket_path" kill-pane -t "$main_pane"
wait_for_window_closed "$socket_path" "$window_id" || exit 1

"$CURRENT_DIR/toggle.sh" toggle "$new_window_id" "$socket_path"

wait_for_total_sidebars "$socket_path" 0 || exit 1
wait_for_status_value "$socket_path" "on" || exit 1

printf 'smoke test passed\n'
