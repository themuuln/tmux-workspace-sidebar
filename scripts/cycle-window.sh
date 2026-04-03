#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

direction="${1:-next}"
set_socket_path_from_arg "${2:-}"
current_session_id="${3:-}"
current_window_id="${4:-}"

case "$direction" in
	prev)
		step=-1
		;;
	next)
		step=1
		;;
	*)
		printf 'unsupported direction: %s\n' "$direction" >&2
		exit 1
		;;
esac

selection="$(
	CURRENT_SESSION_ID="${current_session_id:-$(tmux_cmd display-message -p '#{session_id}' 2>/dev/null || true)}" \
	CURRENT_WINDOW_ID="${current_window_id:-$(tmux_cmd display-message -p '#{window_id}' 2>/dev/null || true)}" \
	SESSION_ROWS="$(tmux_cmd list-sessions -F '#{session_id}' 2>/dev/null || true)" \
	WINDOW_ROWS="$(tmux_cmd list-windows -a -F '#{session_id}\t#{window_id}\t#{window_index}' 2>/dev/null || true)" \
	STEP="$step" \
	PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" \
	"$(sidebar_python)" - <<'PY'
from __future__ import annotations

import os

from tmux_workspace_sidebar.navigation import flatten_window_targets, select_wrapped_window_target


session_order = [line.strip() for line in os.environ.get("SESSION_ROWS", "").splitlines() if line.strip()]
window_rows = []
for line in os.environ.get("WINDOW_ROWS", "").splitlines():
    parts = line.split("\t")
    if len(parts) != 3:
        continue
    session_id, window_id, window_index = parts
    try:
        window_rows.append((session_id, window_id, int(window_index)))
    except ValueError:
        continue

target = select_wrapped_window_target(
    flatten_window_targets(session_order, window_rows),
    os.environ.get("CURRENT_SESSION_ID", ""),
    os.environ.get("CURRENT_WINDOW_ID", ""),
    int(os.environ.get("STEP", "1")),
)
if target:
    print(target[0])
    print(target[1])
PY
)"

[ -n "$selection" ] || exit 0

target_session_id="$(printf '%s\n' "$selection" | sed -n '1p')"
target_window_id="$(printf '%s\n' "$selection" | sed -n '2p')"

[ -n "$target_session_id" ] || exit 0
[ -n "$target_window_id" ] || exit 0

tmux_cmd switch-client -t "$target_session_id" 2>/dev/null || true
tmux_cmd select-window -t "$target_window_id"
