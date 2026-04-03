# Options

## `@workspace_sidebar_width`

Sidebar width in columns.

The configured width is reapplied during sidebar lifecycle syncs, so pane layout
changes such as killing a sibling pane do not leave the sidebar expanded.

Default:

```tmux
set -g @workspace_sidebar_width '32'
```

## `@workspace_sidebar_position`

Sidebar position. Supported values:

- `left`
- `right`

Default:

```tmux
set -g @workspace_sidebar_position 'left'
```

## `@workspace_sidebar_toggle_key`

Prefix key for global toggle.

Default:

```tmux
set -g @workspace_sidebar_toggle_key 'B'
```

## `@workspace_sidebar_focus_key`

Prefix key for focusing the sidebar in the current window.

Default:

```tmux
set -g @workspace_sidebar_focus_key 'b'
```

## `@workspace_sidebar_inbox_key`

Prefix key for jumping to the oldest actionable pane.

Actionable means `needs-input`, `error`, or unread `done` for supported app providers.

Default:

```tmux
set -g @workspace_sidebar_inbox_key 'm'
```

## `@workspace_sidebar_inbox_next_key`

Prefix key for jumping to the next actionable pane.

Default:

```tmux
set -g @workspace_sidebar_inbox_next_key 'M'
```

## `@workspace_sidebar_inbox_picker_key`

Prefix key for opening the actionable inbox picker in a tmux popup powered by `tv`.

This feature requires `tv` to be installed and available on `PATH`.

Default:

```tmux
set -g @workspace_sidebar_inbox_picker_key 'u'
```

## `@workspace_sidebar_inbox_picker_theme`

Optional `tv` theme name used only for the actionable inbox picker popup.

When empty, the picker inherits your normal `tv` configuration and only applies the explicit selection color overrides below.

Default:

```tmux
set -g @workspace_sidebar_inbox_picker_theme ''
```

## `@workspace_sidebar_inbox_picker_selection_bg`

Background color for the selected row in the actionable inbox picker.

This maps to `tv`'s `selection_bg` theme override and exists to keep the cursor line readable even when your global `tv` theme uses a low-contrast selection color.

Default:

```tmux
set -g @workspace_sidebar_inbox_picker_selection_bg '#264f78'
```

## `@workspace_sidebar_inbox_picker_selection_fg`

Foreground color for the selected row in the actionable inbox picker.

This maps to `tv`'s `selection_fg` theme override.

Default:

```tmux
set -g @workspace_sidebar_inbox_picker_selection_fg '#ffffff'
```

## `@workspace_sidebar_python`

Python executable used by the curses app and helper scripts.

Default:

```tmux
set -g @workspace_sidebar_python 'python3'
```

## `@workspace_sidebar_plugin_dir`

Resolved absolute path to the plugin root directory.

The plugin sets this automatically when `sidebar.tmux` loads. It is useful for external hook commands that need to locate bundled scripts without hardcoding a machine-specific path.

Example:

```bash
tmux show-option -gqv @workspace_sidebar_plugin_dir
```

## `@workspace_sidebar_codex_command`

Command launched by the `C` action inside the sidebar.

Default:

```tmux
set -g @workspace_sidebar_codex_command 'codex'
```

Example:

```tmux
set -g @workspace_sidebar_codex_command 'codex --profile work'
```

## `@workspace_sidebar_codex_window_name`

Window name used when the sidebar launches Codex.

Default:

```tmux
set -g @workspace_sidebar_codex_window_name 'codex'
```

## `@workspace_sidebar_push_enabled`

Enable push notifications for qualifying supported-app pane updates.

Default:

```tmux
set -g @workspace_sidebar_push_enabled '0'
```

## `@workspace_sidebar_push_transport`

Push delivery backend. Supported values:

- `ntfy`

The built-in `ntfy` transport requires `curl` on `PATH`.

Default:

```tmux
set -g @workspace_sidebar_push_transport 'ntfy'
```

If `@workspace_sidebar_push_command` is set, that command is used instead of the built-in transport.

## `@workspace_sidebar_push_statuses`

Comma-separated pane statuses that should trigger a push notification when they change.

Default:

```tmux
set -g @workspace_sidebar_push_statuses 'needs-input,error,done'
```

## `@workspace_sidebar_push_ntfy_url`

Base URL for the built-in `ntfy` transport.

This path uses `curl` under the hood.

Default:

```tmux
set -g @workspace_sidebar_push_ntfy_url 'https://ntfy.sh'
```

## `@workspace_sidebar_push_ntfy_topic`

Topic name for the built-in `ntfy` transport. When this is empty, no built-in push is sent.

Default:

```tmux
set -g @workspace_sidebar_push_ntfy_topic ''
```

## `@workspace_sidebar_push_ntfy_token`

Optional bearer token for authenticated `ntfy` topics.

Default:

```tmux
set -g @workspace_sidebar_push_ntfy_token ''
```

## `@workspace_sidebar_push_command`

Optional shell command for custom delivery. When set, the plugin exports notification fields and runs this command instead of the built-in transport.

The exported fields include `WORKSPACE_SIDEBAR_PUSH_APP`, `WORKSPACE_SIDEBAR_PUSH_STATUS`, `WORKSPACE_SIDEBAR_PUSH_TITLE`, `WORKSPACE_SIDEBAR_PUSH_BODY`, and the pane metadata fields.

Available environment variables:

- `WORKSPACE_SIDEBAR_PUSH_STATUS`
- `WORKSPACE_SIDEBAR_PUSH_TITLE`
- `WORKSPACE_SIDEBAR_PUSH_BODY`
- `WORKSPACE_SIDEBAR_PUSH_PRIORITY`
- `WORKSPACE_SIDEBAR_PUSH_TAGS`
- `WORKSPACE_SIDEBAR_PUSH_PANE_ID`
- `WORKSPACE_SIDEBAR_PUSH_SESSION_ID`
- `WORKSPACE_SIDEBAR_PUSH_WINDOW_ID`
- `WORKSPACE_SIDEBAR_PUSH_PANE_TITLE`
- `WORKSPACE_SIDEBAR_PUSH_PANE_CURRENT_PATH`
- `WORKSPACE_SIDEBAR_PUSH_MESSAGE`

Default:

```tmux
set -g @workspace_sidebar_push_command ''
```
