#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

pane_id="${WORKSPACE_SIDEBAR_PUSH_PANE_ID:-}"
[ -n "$pane_id" ] || exit 0

status="${WORKSPACE_SIDEBAR_PUSH_STATUS:-codex}"
title="${WORKSPACE_SIDEBAR_PUSH_TITLE:-Codex update}"
message="${WORKSPACE_SIDEBAR_PUSH_MESSAGE:-}"
body="$(printf '%s' "$message" | tr '\n' ' ' | tr '\t' ' ' | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
[ -n "$body" ] || body="Codex $status"

client_pid="$(
	tmux_cmd list-clients -F '#{client_pid}' 2>/dev/null | awk 'NF { print; exit }'
)"

sender_bundle_id_for_process() {
	case "${1:-}" in
		ghostty)
			printf '%s\n' 'com.mitchellh.ghostty'
			;;
		iTerm2)
			printf '%s\n' 'com.googlecode.iterm2'
			;;
		Apple_Terminal)
			printf '%s\n' 'com.apple.Terminal'
			;;
		wezterm)
			printf '%s\n' 'com.github.wez.wezterm'
			;;
		kitty)
			printf '%s\n' 'net.kovidgoyal.kitty'
			;;
		alacritty)
			printf '%s\n' 'org.alacritty'
			;;
		*)
			return 1
			;;
	esac
}

resolve_sender_bundle_id() {
	local pid="${1:-}"
	local command_name=""

	while [ -n "$pid" ] && [ "$pid" -gt 1 ] 2>/dev/null; do
		command_name="$(ps -p "$pid" -o comm= 2>/dev/null | awk 'NF { print $1; exit }')"
		command_name="${command_name##*/}"
		command_name="${command_name#-}"
		if bundle_id="$(sender_bundle_id_for_process "$command_name")"; then
			printf '%s\n' "$bundle_id"
			return 0
		fi
		pid="$(ps -p "$pid" -o ppid= 2>/dev/null | tr -d ' ')"
	done

	return 1
}

send_terminal_notification() {
	terminal-notifier "$@" >/dev/null 2>&1 &
}

# Ghostty supports desktop notifications through OSC 9.
# tmux requires passthrough wrapping and `allow-passthrough` enabled.
client_tty="$(
	tmux_cmd list-clients -F '#{client_tty}' 2>/dev/null | awk 'NF { print; exit }'
)"

ghostty_sent="0"
if [ -n "$client_tty" ] && [ -w "$client_tty" ]; then
	printf '\033]9;%s\033\\' "$title" > "$client_tty" 2>/dev/null || true
	ghostty_sent="1"
fi

# On macOS, notifications from the foreground app can be suppressed from showing
# as a banner even when Ghostty accepts OSC 9. Prefer terminal-notifier so the
# visible alert is attributed to the terminal app instead of Script Editor.
if command -v terminal-notifier >/dev/null 2>&1; then
	if bundle_id="$(resolve_sender_bundle_id "$client_pid")"; then
		send_terminal_notification \
			-sender "$bundle_id" \
			-activate "$bundle_id" \
			-title "$title" \
			-message "$body" \
			-group "tmux-workspace-sidebar:$pane_id"
	else
		send_terminal_notification \
			-title "$title" \
			-message "$body" \
			-group "tmux-workspace-sidebar:$pane_id"
	fi
elif command -v osascript >/dev/null 2>&1; then
	osascript -e "display notification \"${body//\"/\\\"}\" with title \"${title//\"/\\\"}\"" >/dev/null 2>&1 || true
fi

exit 0
