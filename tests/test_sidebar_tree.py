from __future__ import annotations

import unittest

from tmux_workspace_sidebar.sidebar_tree import (
    Pane,
    Session,
    Window,
    build_rows,
    ensure_selected_key_visible,
    filtered_rows,
    matching_row_indexes,
    merge_snapshot_state,
    reconcile_expansion_state,
)


class SidebarTreeTests(unittest.TestCase):
    def sample_snapshot(self) -> tuple[list[Session], list[Window], list[Pane]]:
        sessions = [Session(session_id="$1", name="alpha", attached=1, active=True)]
        windows = [
            Window(session_id="$1", window_id="@1", index=0, name="bash", active=True, activity=False),
            Window(session_id="$1", window_id="@2", index=1, name="codex", active=False, activity=True),
        ]
        panes = [
            Pane(session_id="$1", window_id="@1", pane_id="%1", index=0, title="shell", command="bash", active=True, current_path="/tmp/one"),
            Pane(session_id="$1", window_id="@2", pane_id="%2", index=0, title="⠋ solving", command="node", active=False, current_path="/tmp/two"),
            Pane(session_id="$1", window_id="@2", pane_id="%3", index=1, title="notes", command="bash", active=False, current_path="/tmp/three"),
        ]
        return sessions, windows, panes

    def test_merge_snapshot_state_applies_codex_inference(self) -> None:
        sessions, windows, panes = self.sample_snapshot()
        merged = merge_snapshot_state(sessions, windows, panes, pane_states={})
        second_window = merged[0].windows[1]
        self.assertEqual(second_window.panes[0].app, "codex")
        self.assertEqual(second_window.panes[0].status, "running")

    def test_merge_snapshot_state_applies_flutter_inference(self) -> None:
        sessions = [Session(session_id="$1", name="alpha", attached=1, active=True)]
        windows = [Window(session_id="$1", window_id="@1", index=0, name="flutter", active=True, activity=False)]
        panes = [
            Pane(
                session_id="$1",
                window_id="@1",
                pane_id="%1",
                index=0,
                title="flutter run",
                command="flutter",
                active=True,
                current_path="/tmp/flutter-app",
            )
        ]
        merged = merge_snapshot_state(sessions, windows, panes, pane_states={})
        pane = merged[0].windows[0].panes[0]
        self.assertEqual(pane.app, "flutter")
        self.assertEqual(pane.status, "running")

    def test_merge_snapshot_state_circle_spinner_overrides_stale_done(self) -> None:
        sessions = [Session(session_id="$1", name="alpha", attached=1, active=True)]
        windows = [Window(session_id="$1", window_id="@1", index=0, name="codex", active=True, activity=False)]
        panes = [
            Pane(
                session_id="$1",
                window_id="@1",
                pane_id="%1",
                index=0,
                title="◌ working",
                command="node",
                active=True,
                current_path="/tmp/one",
            )
        ]

        merged = merge_snapshot_state(
            sessions,
            windows,
            panes,
            pane_states={
                "%1": {
                    "pane_id": "%1",
                    "app": "codex",
                    "status": "done",
                    "message": "finished",
                    "unread": False,
                }
            },
        )

        pane = merged[0].windows[0].panes[0]
        self.assertEqual(pane.app, "codex")
        self.assertEqual(pane.status, "running")

    def test_merge_snapshot_state_keeps_done_for_open_codex_pane_without_spinner(self) -> None:
        sessions = [Session(session_id="$1", name="alpha", attached=1, active=True)]
        windows = [Window(session_id="$1", window_id="@1", index=0, name="codex", active=True, activity=False)]
        panes = [
            Pane(
                session_id="$1",
                window_id="@1",
                pane_id="%1",
                index=0,
                title="codex",
                command="codex",
                active=True,
                current_path="/tmp/one",
            )
        ]

        merged = merge_snapshot_state(
            sessions,
            windows,
            panes,
            pane_states={
                "%1": {
                    "pane_id": "%1",
                    "app": "codex",
                    "status": "done",
                    "message": "finished",
                    "unread": False,
                }
            },
        )

        pane = merged[0].windows[0].panes[0]
        self.assertEqual(pane.app, "codex")
        self.assertEqual(pane.status, "done")

    def test_merge_snapshot_state_clears_closed_codex_status(self) -> None:
        sessions = [Session(session_id="$1", name="alpha", attached=1, active=True)]
        windows = [Window(session_id="$1", window_id="@1", index=0, name="shell", active=True, activity=False)]
        panes = [
            Pane(
                session_id="$1",
                window_id="@1",
                pane_id="%1",
                index=0,
                title="shell",
                command="zsh",
                active=True,
                current_path="/tmp/one",
            )
        ]

        merged = merge_snapshot_state(
            sessions,
            windows,
            panes,
            pane_states={
                "%1": {
                    "pane_id": "%1",
                    "app": "codex",
                    "status": "done",
                    "message": "finished",
                    "unread": False,
                }
            },
        )

        pane = merged[0].windows[0].panes[0]
        self.assertEqual(pane.app, "")
        self.assertEqual(pane.status, "")
        self.assertEqual(pane.status_message, "")
        self.assertFalse(pane.unread)

    def test_pane_label_keeps_command_prefix_visible(self) -> None:
        pane = Pane(
            session_id="$1",
            window_id="@1",
            pane_id="%1",
            index=0,
            title="tmux-workspace-sidebar",
            command="codex",
            active=True,
            current_path="/tmp/tmux-workspace-sidebar",
        )
        self.assertEqual(pane.label(display_index=3), "3 codex tmux-workspace-sidebar")

    def test_window_label_keeps_cli_prefix_visible_when_name_uses_path(self) -> None:
        window = Window(session_id="$1", window_id="@1", index=1, name="zsh", active=True, activity=False)
        window.panes = [
            Pane(
                session_id="$1",
                window_id="@1",
                pane_id="%1",
                index=0,
                title="shell",
                command="zsh",
                active=True,
                current_path="/tmp/tmux-workspace-sidebar",
            )
        ]

        self.assertEqual(window.label(), "1 zsh tmux-workspace-sidebar")

    def test_reconcile_and_build_rows_expand_selected_pane(self) -> None:
        sessions, windows, panes = self.sample_snapshot()
        sessions = merge_snapshot_state(
            sessions,
            windows,
            panes,
            pane_states={"%3": {"pane_id": "%3", "status": "needs-input", "message": "reply"}},
        )
        expanded_sessions: set[str] = set()
        expanded_windows: set[str] = set()
        initialized = reconcile_expansion_state(
            sessions,
            expanded_sessions,
            expanded_windows,
            current_session_id="$1",
            current_window_id="@1",
            initialized=False,
        )
        self.assertTrue(initialized)
        ensure_selected_key_visible("pane:%3", sessions, expanded_sessions, expanded_windows)
        rows = build_rows(
            sessions,
            expanded_sessions,
            expanded_windows,
            current_session_id="$1",
            current_window_id="@1",
            current_pane_id="%1",
        )
        pane_rows = [row for row in rows if row.kind == "pane"]
        self.assertEqual([row.row_id for row in pane_rows], ["%2", "%3"])
        self.assertEqual(pane_rows[1].status, "needs-input")

    def test_filtering_keeps_parent_rows(self) -> None:
        sessions, windows, panes = self.sample_snapshot()
        sessions = merge_snapshot_state(sessions, windows, panes, pane_states={})
        rows = build_rows(
            sessions,
            expanded_sessions={"$1"},
            expanded_windows={"@2"},
            current_session_id="$1",
            current_window_id="@1",
            current_pane_id="%1",
        )
        filtered = filtered_rows(rows, "three")
        self.assertEqual([row.kind for row in filtered if row.kind != "spacer"], ["session", "window", "pane"])
        self.assertEqual(matching_row_indexes(filtered, "three"), [2])

    def test_session_label_is_explicit(self) -> None:
        session = Session(session_id="$1", name="alpha", attached=1, active=True)
        self.assertEqual(session.label(), "alpha")

    def test_session_row_meta_includes_counts(self) -> None:
        sessions, windows, panes = self.sample_snapshot()
        sessions = merge_snapshot_state(sessions, windows, panes, pane_states={})
        rows = build_rows(
            sessions,
            expanded_sessions={"$1"},
            expanded_windows={"@2"},
            current_session_id="$1",
            current_window_id="@1",
            current_pane_id="%1",
        )
        session_row = next(row for row in rows if row.kind == "session")
        self.assertIn("2w", session_row.meta)
        self.assertIn("3p", session_row.meta)
        self.assertIn("1r", session_row.meta)


if __name__ == "__main__":
    unittest.main()
