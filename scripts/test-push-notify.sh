#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_SCRIPT="$CURRENT_DIR/push-notify.sh"

tmpdir="$(mktemp -d)"
socket="workspace-sidebar-push-$$"

cleanup() {
	tmux -L "$socket" kill-server >/dev/null 2>&1 || true
	rm -rf "$tmpdir"
}

trap cleanup EXIT

tmux -L "$socket" -f /dev/null new-session -d -s push-test 'sleep 60'
socket_path="$(tmux -L "$socket" display-message -p -t push-test:0 '#{socket_path}')"
export TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH="$socket_path"

tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_enabled '1'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_transport 'ntfy'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_ntfy_url 'https://ntfy.example.com'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_ntfy_topic 'codex'
tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_ntfy_token 'secret-token'

mock_bin_dir="$tmpdir/bin"
mkdir -p "$mock_bin_dir"
mock_curl_log="$tmpdir/curl.log"

cat > "$mock_bin_dir/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "$MOCK_CURL_LOG"
EOF
chmod +x "$mock_bin_dir/curl"

payload='{"app":"codex","status":"done","title":"Codex finished","body":"project ready","priority":"default","tags":"white_check_mark","pane_id":"%1","session_id":"$1","window_id":"@1","pane_title":"codex","pane_current_path":"/tmp/project","message":"done"}'

PATH="$mock_bin_dir:$PATH" MOCK_CURL_LOG="$mock_curl_log" bash "$PUSH_SCRIPT" "$payload"

[ -f "$mock_curl_log" ] || {
	printf 'expected mock curl to be called\n' >&2
	exit 1
}

for expected in \
	'-fsS' \
	'--connect-timeout' \
	'3' \
	'--max-time' \
	'10' \
	'Title: Codex finished' \
	'Priority: default' \
	'Tags: white_check_mark' \
	'Authorization: Bearer secret-token' \
	'project ready' \
	'https://ntfy.example.com/codex'
do
	grep -Fx -- "$expected" "$mock_curl_log" >/dev/null || {
		printf 'expected curl arg %s\n' "$expected" >&2
		exit 1
	}
done

rm -f "$mock_curl_log"
tmux -S "$socket_path" set-option -gq @workspace_sidebar_push_enabled '0'
PATH="$mock_bin_dir:$PATH" MOCK_CURL_LOG="$mock_curl_log" bash "$PUSH_SCRIPT" "$payload"
[ ! -e "$mock_curl_log" ] || {
	printf 'expected disabled push notifications to skip curl\n' >&2
	exit 1
}

printf 'push notify test passed\n'
