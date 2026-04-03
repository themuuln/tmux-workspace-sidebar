from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmux_workspace_sidebar.state import (
    build_notification_payload,
    clear_actionable_state_file,
    list_actionable_candidates,
    load_selection_key,
    load_state_file,
    resolve_actionable_pane_target,
    select_actionable_target,
    state_dir,
    update_selection_key,
    update_state_file,
)


class StateTests(unittest.TestCase):
    def test_state_dir_uses_event_file_hash_folder(self) -> None:
        path = state_dir(event_file="/tmp/sidebar/abc123.event")
        self.assertEqual(path, Path("/tmp/sidebar/abc123/state"))

    def test_update_state_skips_stale_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "pane-%1.json"
            first = update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="running",
                message="first",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            stale = update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="stale",
                updated_at=5,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            self.assertIsNotNone(first)
            self.assertIsNone(stale)
            self.assertEqual(load_state_file(state_file)["message"], "first")

    def test_clear_actionable_state_file_resets_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "pane-%1.json"
            update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            cleared = clear_actionable_state_file(state_file, updated_at=20)
            self.assertIsNotNone(cleared)
            self.assertEqual(cleared["status"], "done")
            self.assertFalse(cleared["unread"])
            self.assertEqual(cleared["message"], "done")
            self.assertEqual(cleared["updated_at"], 20)

    def test_clear_actionable_state_file_resets_non_done_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "pane-%1.json"
            update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="needs-input",
                message="approve",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            cleared = clear_actionable_state_file(state_file, updated_at=20)
            self.assertIsNotNone(cleared)
            self.assertEqual(cleared["status"], "idle")
            self.assertFalse(cleared["unread"])
            self.assertEqual(cleared["message"], "")
            self.assertEqual(cleared["updated_at"], 20)

    def test_selection_key_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            self.assertEqual(load_selection_key(states_dir), "")
            payload = update_selection_key(states_dir, selected_key="window:@1", updated_at=42)
            self.assertEqual(payload["selected_key"], "window:@1")
            self.assertEqual(payload["updated_at"], 42)
            self.assertEqual(load_selection_key(states_dir), "window:@1")

    def test_select_actionable_target_uses_priority_then_age(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            update_state_file(
                states_dir / "pane-%1.json",
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=30,
                session_id="$1",
                window_id="@1",
                pane_title="one",
                pane_current_command="codex",
                pane_current_path="/a",
            )
            update_state_file(
                states_dir / "pane-%2.json",
                pane_id="%2",
                app="codex",
                status="error",
                message="error",
                updated_at=20,
                session_id="$1",
                window_id="@1",
                pane_title="two",
                pane_current_command="codex",
                pane_current_path="/b",
            )
            update_state_file(
                states_dir / "pane-%3.json",
                pane_id="%3",
                app="codex",
                status="needs-input",
                message="input",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="three",
                pane_current_command="codex",
                pane_current_path="/c",
            )
            tmux_panes = "\n".join(
                [
                    "%1\t$1\t@1\t",
                    "%2\t$1\t@1\t",
                    "%3\t$1\t@1\t",
                ]
            )
            self.assertEqual(
                select_actionable_target(
                    action="oldest",
                    current_pane_id="",
                    tmux_panes=tmux_panes,
                    states_dir=states_dir,
                ),
                ("$1", "@1", "%3"),
            )
            self.assertEqual(
                select_actionable_target(
                    action="next",
                    current_pane_id="%3",
                    tmux_panes=tmux_panes,
                    states_dir=states_dir,
                ),
                ("$1", "@1", "%2"),
            )

    def test_list_actionable_candidates_filters_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            update_state_file(
                states_dir / "pane-%1.json",
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=30,
                session_id="$1",
                window_id="@1",
                pane_title="one",
                pane_current_command="codex",
                pane_current_path="/a",
            )
            update_state_file(
                states_dir / "pane-%2.json",
                pane_id="%2",
                app="shell",
                status="done",
                message="ignored",
                updated_at=5,
                session_id="$1",
                window_id="@1",
                pane_title="two",
                pane_current_command="bash",
                pane_current_path="/b",
            )
            tmux_panes = "\n".join(
                [
                    "%1\t$1\tsession\t@1\twindow\t/tmp/project\t",
                    "%2\t$1\tsession\t@1\twindow\t/tmp/project\t",
                ]
            )
            rows = list_actionable_candidates(states_dir=states_dir, tmux_panes=tmux_panes)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["pane_id"], "%1")
            self.assertEqual(rows[0]["session_name"], "session")

    def test_list_actionable_candidates_skips_seen_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            state_file = states_dir / "pane-%1.json"
            update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="one",
                pane_current_command="codex",
                pane_current_path="/a",
            )
            clear_actionable_state_file(state_file, updated_at=20)
            tmux_panes = "%1\t$1\tsession\t@1\twindow\t/tmp/project\t"
            rows = list_actionable_candidates(states_dir=states_dir, tmux_panes=tmux_panes)
            self.assertEqual(rows, [])

    def test_list_actionable_candidates_supports_flutter_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            update_state_file(
                states_dir / "pane-%9.json",
                pane_id="%9",
                app="flutter",
                status="error",
                message="Gradle task assembleDebug failed",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="flutter run",
                pane_current_command="flutter",
                pane_current_path="/tmp/flutter-app",
            )
            rows = list_actionable_candidates(
                states_dir=states_dir,
                tmux_panes="%9\t$1\tsession\t@1\twindow\t/tmp/flutter-app\t",
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["app"], "flutter")
            self.assertEqual(rows[0]["status"], "error")

    def test_update_state_file_preserves_seen_done_until_new_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "pane-%1.json"
            first = update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=10,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            self.assertIsNotNone(first)
            self.assertTrue(first["unread"])

            clear_actionable_state_file(state_file, updated_at=20)
            duplicate = update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="done",
                updated_at=30,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            self.assertIsNotNone(duplicate)
            self.assertFalse(duplicate["unread"])

            changed = update_state_file(
                state_file,
                pane_id="%1",
                app="codex",
                status="done",
                message="done again",
                updated_at=40,
                session_id="$1",
                window_id="@1",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/tmp",
            )
            self.assertIsNotNone(changed)
            self.assertTrue(changed["unread"])

    def test_resolve_actionable_pane_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            states_dir = Path(tmpdir)
            update_state_file(
                states_dir / "pane-%7.json",
                pane_id="%7",
                app="codex",
                status="error",
                message="boom",
                updated_at=7,
                session_id="$2",
                window_id="@3",
                pane_title="pane",
                pane_current_command="codex",
                pane_current_path="/repo",
            )
            tmux_panes = "%7\t$2\tsession\t@3\twindow\t/repo\t"
            self.assertEqual(
                resolve_actionable_pane_target(
                    pane_id="%7",
                    tmux_panes=tmux_panes,
                    states_dir=states_dir,
                ),
                ("$2", "@3", "%7"),
            )

    def test_build_notification_payload_for_actionable_transition(self) -> None:
        payload = build_notification_payload(
            {"app": "codex", "status": "running", "message": "working"},
            {
                "pane_id": "%9",
                "app": "codex",
                "status": "needs-input",
                "message": "Approve command",
                "updated_at": 10,
                "session_id": "$1",
                "window_id": "@2",
                "pane_title": "codex",
                "pane_current_command": "codex",
                "pane_current_path": "/Users/test/project",
            },
        )
        assert payload is not None
        self.assertEqual(payload["status"], "needs-input")
        self.assertEqual(payload["title"], "Codex needs input")
        self.assertIn("/Users/test/project", payload["body"])
        self.assertIn("Approve command", payload["body"])

    def test_build_notification_payload_uses_flutter_title(self) -> None:
        payload = build_notification_payload(
            {"app": "flutter", "status": "running", "message": "flutter run"},
            {
                "pane_id": "%9",
                "app": "flutter",
                "status": "error",
                "message": "Gradle task assembleDebug failed",
                "updated_at": 10,
                "session_id": "$1",
                "window_id": "@2",
                "pane_title": "flutter run",
                "pane_current_command": "flutter",
                "pane_current_path": "/tmp/flutter-app",
            },
        )
        assert payload is not None
        self.assertEqual(payload["app"], "flutter")
        self.assertEqual(payload["title"], "Flutter error")

    def test_build_notification_payload_skips_identical_status_and_message(self) -> None:
        payload = build_notification_payload(
            {"app": "codex", "status": "done", "message": "All set"},
            {
                "pane_id": "%9",
                "app": "codex",
                "status": "done",
                "message": "All set",
                "updated_at": 10,
                "session_id": "$1",
                "window_id": "@2",
                "pane_title": "codex",
                "pane_current_command": "codex",
                "pane_current_path": "/tmp/project",
            },
        )
        self.assertIsNone(payload)

    def test_build_notification_payload_respects_status_filter(self) -> None:
        payload = build_notification_payload(
            {"app": "codex", "status": "running", "message": "Working"},
            {
                "pane_id": "%9",
                "app": "codex",
                "status": "done",
                "message": "All set",
                "updated_at": 10,
                "session_id": "$1",
                "window_id": "@2",
                "pane_title": "codex",
                "pane_current_command": "codex",
                "pane_current_path": "/tmp/project",
            },
            notify_statuses={"needs-input"},
        )
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
