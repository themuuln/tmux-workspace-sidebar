#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/lifecycle.sh"

mode="${1:-toggle}"
set_socket_path_from_arg "${3:-}"
window_id="${2:-$(current_window_id)}"

if [ "$mode" = "focus" ]; then
	focus_sidebar_window "$window_id"
	exit 0
fi

if [ "$(workspace_sidebar_enabled)" = "1" ]; then
	disable_sidebar_global
	exit 0
fi

enable_sidebar_global "$window_id"
