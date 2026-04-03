#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"
source "$CURRENT_DIR/lifecycle.sh"
set_socket_path_from_arg "${2:-}"

mode="${1:-refresh}"
window_id="${3:-}"

if [ "$mode" = "sync" ]; then
	reconcile_sidebar_state
elif [ "$mode" = "normalize-focus" ]; then
	normalize_current_window_focus "$window_id" || true
fi

signal_sidebar_refresh
