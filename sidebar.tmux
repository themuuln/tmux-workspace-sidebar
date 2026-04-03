#!/usr/bin/env bash

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$CURRENT_DIR/scripts"

source "$SCRIPTS_DIR/helpers.sh"

set_default_options() {
	tmux set-option -gq "@workspace_sidebar_plugin_dir" "$CURRENT_DIR"
	set_tmux_option_if_unset "@workspace_sidebar_width" "32"
	set_tmux_option_if_unset "@workspace_sidebar_position" "left"
	set_tmux_option_if_unset "@workspace_sidebar_toggle_key" "B"
	set_tmux_option_if_unset "@workspace_sidebar_focus_key" "b"
	set_tmux_option_if_unset "@workspace_sidebar_inbox_key" "m"
	set_tmux_option_if_unset "@workspace_sidebar_inbox_next_key" "M"
	set_tmux_option_if_unset "@workspace_sidebar_inbox_picker_key" "u"
	set_tmux_option_if_unset "@workspace_sidebar_inbox_picker_theme" ""
	set_tmux_option_if_unset "@workspace_sidebar_inbox_picker_selection_bg" "#264f78"
	set_tmux_option_if_unset "@workspace_sidebar_inbox_picker_selection_fg" "#ffffff"
	set_tmux_option_if_unset "@workspace_sidebar_python" "python3"
	set_tmux_option_if_unset "@workspace_sidebar_enabled" "0"
	set_tmux_option_if_unset "@workspace_sidebar_codex_command" "codex"
	set_tmux_option_if_unset "@workspace_sidebar_codex_window_name" "codex"
	set_tmux_option_if_unset "@workspace_sidebar_push_enabled" "0"
	set_tmux_option_if_unset "@workspace_sidebar_push_transport" "ntfy"
	set_tmux_option_if_unset "@workspace_sidebar_push_statuses" "needs-input,error,done"
	set_tmux_option_if_unset "@workspace_sidebar_push_ntfy_url" "https://ntfy.sh"
	set_tmux_option_if_unset "@workspace_sidebar_push_ntfy_topic" ""
	set_tmux_option_if_unset "@workspace_sidebar_push_ntfy_token" ""
	set_tmux_option_if_unset "@workspace_sidebar_push_command" ""
}

set_key_bindings() {
	local toggle_key
	local focus_key
	local inbox_key
	local inbox_next_key
	local inbox_picker_key

	toggle_key="$(tmux_option_or_default "@workspace_sidebar_toggle_key" "B")"
	focus_key="$(tmux_option_or_default "@workspace_sidebar_focus_key" "b")"
	inbox_key="$(tmux_option_or_default "@workspace_sidebar_inbox_key" "m")"
	inbox_next_key="$(tmux_option_or_default "@workspace_sidebar_inbox_next_key" "M")"
	inbox_picker_key="$(tmux_option_or_default "@workspace_sidebar_inbox_picker_key" "u")"

	tmux bind-key "$toggle_key" run-shell "$SCRIPTS_DIR/toggle.sh toggle '#{window_id}' '#{socket_path}'"
	tmux bind-key "$focus_key" run-shell "$SCRIPTS_DIR/toggle.sh focus '#{window_id}' '#{socket_path}'"
	tmux bind-key "$inbox_key" run-shell "$SCRIPTS_DIR/jump-actionable.sh oldest '#{socket_path}'"
	tmux bind-key "$inbox_next_key" run-shell "$SCRIPTS_DIR/jump-actionable.sh next '#{socket_path}'"
	tmux bind-key "$inbox_picker_key" run-shell "$SCRIPTS_DIR/open-actionable-picker.sh '#{pane_current_path}' '#{socket_path}'"
}

set_hooks() {
	local refresh_cmd="run-shell -b '$SCRIPTS_DIR/notify.sh refresh #{socket_path}'"
	local normalize_focus_cmd="run-shell -b '$SCRIPTS_DIR/notify.sh normalize-focus #{socket_path} #{window_id}'"
	local sync_cmd="run-shell -b '$SCRIPTS_DIR/notify.sh sync #{socket_path}'"
	local refresh_hooks=(
		after-select-pane
		session-renamed
		window-renamed
	)
	local focus_hooks=(
		after-select-window
		client-session-changed
	)
	local sync_hooks=(
		after-new-session
		after-new-window
		after-split-window
		pane-died
		pane-exited
		session-created
		session-closed
		window-layout-changed
		window-linked
		window-unlinked
	)

	for hook in "${refresh_hooks[@]}"; do
		tmux set-hook -g "$hook" "$refresh_cmd"
	done

	for hook in "${focus_hooks[@]}"; do
		tmux set-hook -g "$hook" "$normalize_focus_cmd"
	done

	for hook in "${sync_hooks[@]}"; do
		tmux set-hook -g "$hook" "$sync_cmd"
	done
}

main() {
	set_default_options
	set_key_bindings
	set_hooks
	return 0
}

main
