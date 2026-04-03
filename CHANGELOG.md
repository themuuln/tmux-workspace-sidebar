# Changelog

## 0.1.0

- Initial publishable release
- Persistent global sidebar pane for tmux sessions, windows, and panes
- Fast refresh hooks and structural sync hooks
- Global open and close behavior across sessions
- Orphan-sidebar cleanup when the last real pane is removed
- Optional Codex launch and Codex status integration

## Unreleased

- Add configurable push notifications for actionable Codex pane updates
- Expose the resolved plugin root as `@workspace_sidebar_plugin_dir`
- Rewrite installation and integration docs around standalone TPM/manual use
- Add CI for unit tests and shell integration tests
- Replace install placeholders with the public `themuuln/tmux-workspace-sidebar` slug
- Document optional `tv` and `curl` dependencies explicitly
- Add regression coverage for the built-in `ntfy` push transport
