#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

set_socket_path_from_arg "${1:-}"

source_file="${WORKSPACE_SIDEBAR_PICKER_SOURCE_FILE:-}"
[ -n "$source_file" ] || exit 0
[ -f "$source_file" ] || exit 0

picker_flags="${WORKSPACE_SIDEBAR_PICKER_FLAGS:-}"
picker_theme="$(tmux_option_or_default "@workspace_sidebar_inbox_picker_theme" "")"
picker_selection_bg="$(tmux_option_or_default "@workspace_sidebar_inbox_picker_selection_bg" "#264f78")"
picker_selection_fg="$(tmux_option_or_default "@workspace_sidebar_inbox_picker_selection_fg" "#ffffff")"
picker_config_file="$(mktemp)"

cleanup() {
	rm -f "$source_file" "$picker_config_file"
}

trap cleanup EXIT

build_picker_config() {
	local base_config_file="${XDG_CONFIG_HOME:-$HOME/.config}/television/config.toml"

	"$(sidebar_python)" - "$base_config_file" "$picker_config_file" "$picker_theme" "$picker_selection_bg" "$picker_selection_fg" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

base_config_path = Path(sys.argv[1])
target_config_path = Path(sys.argv[2])
picker_theme = sys.argv[3]
selection_bg = sys.argv[4]
selection_fg = sys.argv[5]

if base_config_path.is_file():
    lines = base_config_path.read_text(encoding="utf-8").splitlines()
else:
    lines = []


def find_section(section_name: str) -> tuple[int | None, int | None]:
    header_re = re.compile(r"\s*\[([^\]]+)\]\s*$")
    start = None
    for index, line in enumerate(lines):
        match = header_re.match(line)
        if not match:
            continue
        current_section = match.group(1).strip()
        if start is not None:
            return start, index
        if current_section == section_name:
            start = index
    if start is not None:
        return start, len(lines)
    return None, None


def upsert_key(section_name: str, key: str, value: str) -> None:
    if value == "":
        return

    rendered = f'{key} = "{value}"'
    start, end = find_section(section_name)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"[{section_name}]")
        lines.append(rendered)
        return

    key_re = re.compile(rf"\s*{re.escape(key)}\s*=")
    for index in range(start + 1, end):
        if key_re.match(lines[index]):
            lines[index] = rendered
            return

    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, rendered)


upsert_key("ui", "theme", picker_theme)
upsert_key("ui.theme_overrides", "selection_bg", selection_bg)
upsert_key("ui.theme_overrides", "selection_fg", selection_fg)

target_config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

build_picker_config

picker_cmd=(
	tv
	--config-file "$picker_config_file"
	--source-command "cat '$source_file'"
	--source-display '{split:|||:0}'
	--source-output '{split:|||:1}'
	--input-header 'Codex Inbox'
	--input-prompt 'jump > '
	--input-position top
	--no-preview
	--hide-help-panel
	--hide-status-bar
	--results-border none
)

if [ -n "$picker_flags" ]; then
	# Deliberately preserve shell-style flag splitting for tmux/env configured arguments.
	# shellcheck disable=SC2206
	extra_picker_flags=($picker_flags)
	picker_cmd+=("${extra_picker_flags[@]}")
fi

selection="$(
	"${picker_cmd[@]}"
)"

target_pane_id="$(printf '%s' "$selection" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
[ -n "$target_pane_id" ] || exit 0
if [ "$target_pane_id" = "__empty__" ]; then
	exit 0
fi
[[ "$target_pane_id" =~ ^%[0-9]+$ ]] || exit 0

selection="$(
	run_sidebar_python_module tmux_workspace_sidebar.state resolve-actionable-pane \
		--pane-id "$target_pane_id" \
		--tmux-panes "$(
			tmux_cmd list-panes -a -F $'#{pane_id}\t#{session_id}\t#{session_name}\t#{window_id}\t#{window_name}\t#{pane_current_path}\t#{@workspace_sidebar}' 2>/dev/null || true
		)" \
		--state-dir "$(state_dir)"
)"

[ -n "$selection" ] || exit 0

target_session_id="$(printf '%s\n' "$selection" | sed -n '1p')"
target_window_id="$(printf '%s\n' "$selection" | sed -n '2p')"
target_pane_id="$(printf '%s\n' "$selection" | sed -n '3p')"

tmux_cmd switch-client -t "$target_session_id" 2>/dev/null || true
tmux_cmd select-window -t "$target_window_id"
tmux_cmd select-pane -t "$target_pane_id"

"$CURRENT_DIR/clear-state.sh" "$target_pane_id" "${TMUX_WORKSPACE_SIDEBAR_SOCKET_PATH:-}"
