from __future__ import annotations

import unittest

from tmux_workspace_sidebar.flutter import infer_status_and_message


class FlutterTests(unittest.TestCase):
    def test_start_event_maps_to_running(self) -> None:
        status, message = infer_status_and_message(event="start", task="run")
        self.assertEqual(status, "running")
        self.assertEqual(message, "flutter run")

    def test_ready_line_maps_to_idle(self) -> None:
        status, message = infer_status_and_message(line="Flutter run key commands.", task="run")
        self.assertEqual(status, "idle")
        self.assertEqual(message, "Flutter run key commands.")

    def test_error_line_maps_to_error(self) -> None:
        status, message = infer_status_and_message(line="Gradle task assembleDebug failed with exit code 1", task="run")
        self.assertEqual(status, "error")
        self.assertIn("failed", message.lower())


if __name__ == "__main__":
    unittest.main()
