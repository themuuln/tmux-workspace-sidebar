from __future__ import annotations

import unittest

from tmux_workspace_sidebar.codex import infer_status_and_message


class CodexParserTests(unittest.TestCase):
    def test_running_event_is_normalized(self) -> None:
        status, message = infer_status_and_message(
            hook_payload='{"type":"agent-turn-start","message":"working"}'
        )
        self.assertEqual(status, "running")
        self.assertEqual(message, "working")

    def test_permission_like_events_need_input(self) -> None:
        status, _ = infer_status_and_message(
            hook_payload='{"type":"request-user-input","message":"approve"}'
        )
        self.assertEqual(status, "needs-input")

    def test_done_status_wins_without_explicit_event(self) -> None:
        status, message = infer_status_and_message(
            hook_payload='{"status":"completed","summary":"done"}'
        )
        self.assertEqual(status, "done")
        self.assertEqual(message, "done")

    def test_invalid_payload_falls_back_to_env_hints(self) -> None:
        status, message = infer_status_and_message(
            hook_payload="not-json",
            codex_status="working",
            codex_message="fallback",
        )
        self.assertEqual(status, "running")
        self.assertEqual(message, "fallback")


if __name__ == "__main__":
    unittest.main()
