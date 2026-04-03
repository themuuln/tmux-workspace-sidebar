#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CYCLE_SCRIPT="$CURRENT_DIR/cycle-window.sh"

socket="workspace-sidebar-cycle-$$"

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s s1 -n one 'sleep 60'
tmux -L "$socket" new-window -d -t s1: -n two 'sleep 60'
tmux -L "$socket" new-session -d -s s2 -n alpha 'sleep 60'
socket_path="$(tmux -L "$socket" display-message -p -t s1:0 '#{socket_path}')"
s2_session_id="$(tmux -S "$socket_path" display-message -p -t s2:0 '#{session_id}')"
s2_window_id="$(tmux -S "$socket_path" display-message -p -t s2:0 '#{window_id}')"
s1_session_id="$(tmux -S "$socket_path" display-message -p -t s1:1 '#{session_id}')"
s1_last_window_id="$(tmux -S "$socket_path" display-message -p -t s1:1 '#{window_id}')"

selection_prev="$(bash "$CYCLE_SCRIPT" prev "$socket_path" "$s2_session_id" "$s2_window_id" && tmux -S "$socket_path" display-message -p -t "$s1_last_window_id" '#{session_name}:#{window_index}')"
[ "$selection_prev" = "s1:1" ] || {
	printf 'expected previous wrap to s1:1, got %s\n' "$selection_prev" >&2
	exit 1
}

bash "$CYCLE_SCRIPT" next "$socket_path" "$s1_session_id" "$s1_last_window_id"
selection_next="$(tmux -S "$socket_path" display-message -p -t "$s2_window_id" '#{session_name}:#{window_index}')"
[ "$selection_next" = "s2:0" ] || {
	printf 'expected next wrap to s2:0, got %s\n' "$selection_next" >&2
	exit 1
}

printf 'cycle window test passed\n'
