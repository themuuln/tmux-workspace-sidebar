#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

payload="${1:-}"
[ -n "$payload" ] || exit 0

enabled="$(push_notifications_enabled)"
case "$enabled" in
	1|on|yes|true)
		;;
	*)
		exit 0
		;;
esac

eval "$(
	NOTIFY_JSON="$payload" "$(sidebar_python)" - <<'PY'
import json
import os
import shlex

data = json.loads(os.environ["NOTIFY_JSON"])
fields = {
    "WORKSPACE_SIDEBAR_PUSH_APP": data.get("app", ""),
    "WORKSPACE_SIDEBAR_PUSH_STATUS": data.get("status", ""),
    "WORKSPACE_SIDEBAR_PUSH_TITLE": data.get("title", ""),
    "WORKSPACE_SIDEBAR_PUSH_BODY": data.get("body", ""),
    "WORKSPACE_SIDEBAR_PUSH_PRIORITY": data.get("priority", ""),
    "WORKSPACE_SIDEBAR_PUSH_TAGS": data.get("tags", ""),
    "WORKSPACE_SIDEBAR_PUSH_PANE_ID": data.get("pane_id", ""),
    "WORKSPACE_SIDEBAR_PUSH_SESSION_ID": data.get("session_id", ""),
    "WORKSPACE_SIDEBAR_PUSH_WINDOW_ID": data.get("window_id", ""),
    "WORKSPACE_SIDEBAR_PUSH_PANE_TITLE": data.get("pane_title", ""),
    "WORKSPACE_SIDEBAR_PUSH_PANE_CURRENT_PATH": data.get("pane_current_path", ""),
    "WORKSPACE_SIDEBAR_PUSH_MESSAGE": data.get("message", ""),
}
for key, value in fields.items():
    print(f"export {key}={shlex.quote(str(value))}")
PY
)"

custom_command="$(tmux_option_or_default "@workspace_sidebar_push_command" "")"
if [ -n "$custom_command" ]; then
	exec bash -lc "$custom_command"
fi

transport="$(tmux_option_or_default "@workspace_sidebar_push_transport" "ntfy")"
case "$transport" in
	ntfy)
		url="$(tmux_option_or_default "@workspace_sidebar_push_ntfy_url" "https://ntfy.sh")"
		topic="$(tmux_option_or_default "@workspace_sidebar_push_ntfy_topic" "")"
		token="$(tmux_option_or_default "@workspace_sidebar_push_ntfy_token" "")"

		[ -n "$topic" ] || exit 0
		command -v curl >/dev/null 2>&1 || {
			printf 'tmux-workspace-sidebar: curl is required for @workspace_sidebar_push_transport=ntfy\n' >&2
			exit 0
		}

		curl_args=(
			-fsS
			--connect-timeout 3
			--max-time 10
			-H "Title: $WORKSPACE_SIDEBAR_PUSH_TITLE"
			-H "Priority: $WORKSPACE_SIDEBAR_PUSH_PRIORITY"
			-H "Tags: $WORKSPACE_SIDEBAR_PUSH_TAGS"
			-d "$WORKSPACE_SIDEBAR_PUSH_BODY"
		)
		if [ -n "$token" ]; then
			curl_args+=(-H "Authorization: Bearer $token")
		fi

		exec curl "${curl_args[@]}" "${url%/}/$topic"
		;;
	*)
		exit 0
		;;
esac
