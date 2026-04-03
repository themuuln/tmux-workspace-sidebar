from __future__ import annotations

import unittest

from tmux_workspace_sidebar.navigation import (
    flatten_window_targets,
    select_wrapped_window_target,
)


class NavigationTests(unittest.TestCase):
    def test_flatten_window_targets_keeps_session_order_and_window_index(self) -> None:
        self.assertEqual(
            flatten_window_targets(
                ["$2", "$1"],
                [
                    ("$1", "@2", 1),
                    ("$2", "@9", 0),
                    ("$1", "@1", 0),
                ],
            ),
            [("$2", "@9"), ("$1", "@1"), ("$1", "@2")],
        )

    def test_select_wrapped_window_target_wraps_across_sessions(self) -> None:
        window_targets = [
            ("$1", "@1"),
            ("$1", "@2"),
            ("$2", "@3"),
        ]
        self.assertEqual(
            select_wrapped_window_target(window_targets, "$2", "@3", 1),
            ("$1", "@1"),
        )
        self.assertEqual(
            select_wrapped_window_target(window_targets, "$1", "@1", -1),
            ("$2", "@3"),
        )


if __name__ == "__main__":
    unittest.main()
