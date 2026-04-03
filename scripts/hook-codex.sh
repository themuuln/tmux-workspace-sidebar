#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

looks_like_json() {
	case "${1:-}" in
		\{*|\[*)
			return 0
			;;
		*)
			return 1
			;;
	esac
}

read_ready_stdin() {
	local python_cmd
	python_cmd="$(sidebar_python)"
	"$python_cmd" -c 'from __future__ import annotations
import select
import sys

ready, _, _ = select.select([sys.stdin], [], [], 0.05)
if ready:
    sys.stdout.write(sys.stdin.read())'
}

resolve_hook_input() {
	local arg1="${1:-}"
	local arg2="${2:-}"

	HOOK_EVENT=""
	HOOK_PAYLOAD=""

	if looks_like_json "$arg1"; then
		HOOK_PAYLOAD="$arg1"
		HOOK_EVENT="$arg2"
		return
	fi

	if looks_like_json "$arg2"; then
		HOOK_PAYLOAD="$arg2"
		HOOK_EVENT="$arg1"
		return
	fi

	HOOK_EVENT="$arg1"
	if [ ! -t 0 ]; then
		HOOK_PAYLOAD="$(read_ready_stdin)"
	fi
}

resolve_hook_input "${1:-}" "${2:-}"
set_socket_path_from_arg "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}"

parsed="$(
	run_sidebar_python_module tmux_workspace_sidebar.codex parse-hook \
		--hook-event "$HOOK_EVENT" \
		--hook-payload "$HOOK_PAYLOAD" \
		--codex-event "${CODEX_EVENT:-}" \
		--codex-status "${CODEX_STATUS:-}" \
		--codex-message "${CODEX_MESSAGE:-}"
)"

hook_status="$(printf '%s\n' "$parsed" | sed -n '1p')"
hook_message="$(printf '%s\n' "$parsed" | sed '1d')"

[ -n "$hook_status" ] || exit 0

exec "$CURRENT_DIR/update-state.sh" \
	--socket-path "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}" \
	--pane "${TMUX_PANE:-}" \
	--app codex \
	--status "$hook_status" \
	--message "$hook_message"
