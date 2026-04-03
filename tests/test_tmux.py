from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from tmux_workspace_sidebar.tmux import CurrentTarget, TmuxClient


class TmuxClientTests(unittest.TestCase):
    @patch("tmux_workspace_sidebar.tmux.uuid.uuid4")
    @patch("tmux_workspace_sidebar.tmux.subprocess.run")
    def test_capture_multi_batches_commands_and_splits_output(self, run_mock: object, uuid_mock: object) -> None:
        uuid_mock.return_value.hex = "fixed"
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                "first line\n"
                "__tmux_workspace_sidebar__fixed__0__\n"
                "second line\n"
                "third line\n"
                "__tmux_workspace_sidebar__fixed__1__\n"
            ),
            stderr="",
        )

        client = TmuxClient("/tmp/tmux.sock")
        result = client.capture_multi(
            ("display-message", "-p", "one"),
            ("list-sessions", "-F", "#{session_id}"),
        )

        self.assertEqual(result, ["first line", "second line\nthird line"])
        run_mock.assert_called_once()
        argv = run_mock.call_args.args[0]
        self.assertEqual(
            argv,
            [
                "tmux",
                "-S",
                "/tmp/tmux.sock",
                "display-message",
                "-p",
                "one",
                ";",
                "display-message",
                "-p",
                "__tmux_workspace_sidebar__fixed__0__",
                ";",
                "list-sessions",
                "-F",
                "#{session_id}",
                ";",
                "display-message",
                "-p",
                "__tmux_workspace_sidebar__fixed__1__",
            ],
        )

    @patch("tmux_workspace_sidebar.tmux.uuid.uuid4")
    @patch("tmux_workspace_sidebar.tmux.subprocess.run")
    def test_capture_multi_raises_when_marker_missing(self, run_mock: object, uuid_mock: object) -> None:
        uuid_mock.return_value.hex = "fixed"
        run_mock.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="first line\n",
            stderr="",
        )

        client = TmuxClient()
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            client.capture_multi(("display-message", "-p", "one"))

    def test_snapshot_returns_structured_tmux_models(self) -> None:
        client = TmuxClient()
        with patch.object(
            client,
            "capture_multi",
            return_value=[
                "$1\t@2\t%3",
                "$1\tmain\t1\n$4\tother\t0",
                "$1\t@2\t0\teditor\t1\t0\n$4\t@5\t1\tlogs\t0\t1",
                (
                    "$1\t@2\t%3\t0\ttitle\tzsh\t/tmp/project\t1\t0\n"
                    "$1\t@2\t%4\t1\tsidebar\tpython\t/tmp/project\t0\t1\n"
                    "$4\t@5\t%6\t0\tbuild\tbash\t/tmp/build\t0\t0"
                ),
            ],
        ):
            snapshot = client.snapshot()

        self.assertEqual(snapshot.current, CurrentTarget(session_id="$1", window_id="@2", pane_id="%3"))
        self.assertEqual([session.session_id for session in snapshot.sessions], ["$1", "$4"])
        self.assertTrue(snapshot.sessions[0].active)
        self.assertFalse(snapshot.sessions[1].active)
        self.assertEqual([window.window_id for window in snapshot.windows], ["@2", "@5"])
        self.assertEqual([pane.pane_id for pane in snapshot.panes], ["%3", "%6"])
        self.assertEqual(snapshot.panes[0].current_path, "/tmp/project")
        self.assertEqual(snapshot.panes[1].title, "build")


if __name__ == "__main__":
    unittest.main()
