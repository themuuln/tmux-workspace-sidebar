#!/usr/bin/env bash

set -euo pipefail

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CURRENT_DIR/helpers.sh"

export TMUX_WORKSPACE_SIDEBAR_EVENT_FILE
TMUX_WORKSPACE_SIDEBAR_EVENT_FILE="$(event_file)"

# Hooks may signal the pane immediately after split-window.
# Ignore SIGUSR1 during bootstrap so the Python process can install its own handler.
trap '' USR1

exec "$(sidebar_python)" "$PLUGIN_DIR/bin/tmux-workspace-sidebar"
