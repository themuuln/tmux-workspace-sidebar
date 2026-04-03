from __future__ import annotations

import importlib.util
import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import Mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "tmux-workspace-sidebar"
LOADER = SourceFileLoader("tmux_workspace_sidebar_bin", str(MODULE_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load sidebar module from {MODULE_PATH}")
sidebar = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sidebar
SPEC.loader.exec_module(sidebar)


class FakeWindow:
    def __init__(self, height: int = 10, width: int = 40) -> None:
        self.height = height
        self.width = width

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def timeout(self, _value: int) -> None:
        return None


class FakeInputWindow(FakeWindow):
    def __init__(self, keys: list[int], height: int = 10, width: int = 40) -> None:
        super().__init__(height=height, width=width)
        self.keys = list(keys)
        self.timeout_calls: list[int] = []

    def getch(self) -> int:
        if not self.keys:
            return -1
        return self.keys.pop(0)

    def timeout(self, value: int) -> None:
        self.timeout_calls.append(value)


class FakeRenderWindow(FakeWindow):
    def __init__(self, height: int = 10, width: int = 40) -> None:
        super().__init__(height=height, width=width)
        self.draw_calls: list[tuple[int, int, str, int]] = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.draw_calls.append((y, x, text, attr))

    def erase(self) -> None:
        return None

    def move(self, _y: int, _x: int) -> None:
        return None

    def refresh(self) -> None:
        return None

    def keypad(self, _enabled: bool) -> None:
        return None

    def nodelay(self, _enabled: bool) -> None:
        return None


def make_row(**overrides: object) -> sidebar.Row:
    defaults = dict(
        kind="session",
        row_id="$1",
        depth=0,
        text="main",
        tree_prefix="",
        expandable=False,
        expanded=False,
        session_id="$1",
        window_id="@1",
    )
    defaults.update(overrides)
    return sidebar.Row(**defaults)


def make_app(rows: list[sidebar.Row], *, scroll: int = 0, cursor: int = 0) -> sidebar.SidebarApp:
    app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
    app.stdscr = FakeWindow()
    app.display_rows = rows
    app.scroll = scroll
    app.cursor = cursor
    app.status_message = "busy"
    app.ensure_cursor_visible = Mock()
    app.move_cursor = Mock()
    app.toggle_selected_expansion = Mock()
    app.activate_selected = Mock()
    return app


class SidebarKeyDecodeTests(unittest.TestCase):
    def test_decode_escape_sequence_maps_shift_left_and_right(self) -> None:
        self.assertEqual(sidebar.decode_escape_sequence("\x1b[1;2D"), sidebar.KEY_SHIFT_LEFT)
        self.assertEqual(sidebar.decode_escape_sequence("\x1b[1;2C"), sidebar.KEY_SHIFT_RIGHT)

    def test_read_key_translates_shift_arrow_sequence(self) -> None:
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.stdscr = FakeInputWindow([27, ord("["), ord("1"), ord(";"), ord("2"), ord("D")])

        self.assertEqual(app.read_key(), sidebar.KEY_SHIFT_LEFT)
        self.assertEqual(
            app.stdscr.timeout_calls,
            [sidebar.ESCAPE_SEQUENCE_TIMEOUT_MS, sidebar.INPUT_POLL_TIMEOUT_MS],
        )

    def test_read_key_keeps_plain_escape_when_no_sequence_follows(self) -> None:
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.stdscr = FakeInputWindow([27])

        self.assertEqual(app.read_key(), 27)

    def test_shift_up_and_down_fall_back_to_vertical_navigation(self) -> None:
        self.assertEqual(sidebar.decode_escape_sequence("\x1b[1;2A"), sidebar.curses.KEY_UP)
        self.assertEqual(sidebar.decode_escape_sequence("\x1b[1;2B"), sidebar.curses.KEY_DOWN)


class SidebarStatusRenderingTests(unittest.TestCase):
    def make_footer_app(self, row: sidebar.Row) -> sidebar.SidebarApp:
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.input_action = None
        app.pending_kill = None
        app.status_message = ""
        app.show_help = False
        app.filter_query = ""
        app.fit_footer = lambda text, _width: text
        app.selected_row = lambda: row
        app.context_actions = lambda _row: ""
        app.display_rows = [row]
        return app

    def test_header_text_summarizes_workspaces_and_inbox(self) -> None:
        session = make_row(kind="session", row_id="$1", session_id="$1")
        actionable = make_row(
            kind="pane",
            row_id="%1",
            depth=2,
            text="codex",
            tree_prefix="    ",
            status="needs-input",
            session_id="$1",
            window_id="@1",
        )
        running = make_row(
            kind="pane",
            row_id="%2",
            depth=2,
            text="runner",
            tree_prefix="    ",
            status="running",
            session_id="$1",
            window_id="@1",
        )
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.display_rows = [session, actionable, running]
        app.rows = [session, actionable, running]
        app.filter_query = ""

        self.assertEqual(app.header_text(80), "1 ws  •  1 inbox  •  1 run  •  3 shown")

    def test_status_badge_uses_checkmark_only_for_unread_done(self) -> None:
        self.assertEqual(sidebar.status_badge("done", True), "✓")
        self.assertEqual(sidebar.status_badge("done", False), "○")

    def test_row_indicator_uses_thick_bar_for_focused_and_current_rows(self) -> None:
        self.assertEqual(sidebar.render_row_indicator(make_row(current=True)), "▌")
        self.assertEqual(sidebar.render_row_indicator(make_row(), focused=True), "▌")

    def test_row_indicator_only_uses_alert_marker_for_urgent_statuses(self) -> None:
        self.assertEqual(sidebar.render_row_indicator(make_row(status="needs-input")), "!")
        self.assertEqual(sidebar.render_row_indicator(make_row(status="running", activity=True)), " ")

    def test_footer_text_shows_seen_done_with_circle_icon(self) -> None:
        row = make_row(status="done", status_message="ready", unread=False)
        app = self.make_footer_app(row)

        self.assertEqual(app.footer_text(80), "○ Done: ready")

    def test_footer_text_shows_unread_done_with_check_icon(self) -> None:
        row = make_row(status="done", status_message="ready", unread=True)
        app = self.make_footer_app(row)

        self.assertEqual(app.footer_text(80), "✓ Done: ready")

    def test_draw_keeps_status_badge_visible_on_narrow_width(self) -> None:
        row = make_row(kind="pane", row_id="%1", depth=2, text="codex", tree_prefix="    ", status="done", unread=False)
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.stdscr = FakeRenderWindow(height=4, width=15)
        app.display_rows = [row]
        app.scroll = 0
        app.cursor = 0
        app.status_message = ""
        app.input_action = None
        app.input_label = ""
        app.input_value = ""
        app.pending_kill = None
        app.show_help = False
        app.filter_query = ""
        app.sidebar_has_focus = False
        app.ensure_cursor_visible = Mock()
        app.publish_selected_key = Mock()
        app.draw_empty_state = Mock()
        app.context_actions = lambda _row: ""
        app.last_published_selected_key = ""

        with unittest.mock.patch.object(sidebar.curses, "color_pair", return_value=0), unittest.mock.patch.object(
            sidebar.curses, "curs_set", return_value=None
        ):
            app.draw()

        rendered_text = "".join(text for _y, _x, text, _attr in app.stdscr.draw_calls)
        self.assertIn("○", rendered_text)

    def test_draw_keeps_running_badge_visible_in_single_status_column(self) -> None:
        row = make_row(kind="pane", row_id="%1", depth=2, text="codex", tree_prefix="    ", status="running")
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.stdscr = FakeRenderWindow(height=3, width=20)
        app.display_rows = [row]
        app.scroll = 0
        app.cursor = 0
        app.status_message = ""
        app.input_action = None
        app.input_label = ""
        app.input_value = ""
        app.pending_kill = None
        app.show_help = False
        app.filter_query = ""
        app.sidebar_has_focus = False
        app.ensure_cursor_visible = Mock()
        app.publish_selected_key = Mock()
        app.draw_empty_state = Mock()
        app.footer_text = lambda _width: ""

        with unittest.mock.patch.object(sidebar.curses, "color_pair", return_value=0), unittest.mock.patch.object(
            sidebar.curses, "curs_set", return_value=None
        ), unittest.mock.patch.object(sidebar.time, "monotonic", return_value=0):
            app.draw()

        rendered_text = "".join(text for _y, _x, text, _attr in app.stdscr.draw_calls)
        self.assertIn("◐", rendered_text)

    def test_render_row_parts_preserves_pane_cli_prefix_when_truncated(self) -> None:
        row = make_row(
            kind="pane",
            row_id="%1",
            depth=2,
            text="1 codex codex :: very-long-project-name-for-testing",
            priority_text="1 codex",
            tree_prefix="    ",
        )
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)

        primary, meta = app.render_row_parts(row, 20)

        self.assertEqual(meta, "")
        self.assertTrue(primary.startswith("      1 codex "))
        self.assertIn("…", primary)

    def test_render_row_parts_preserves_window_cli_prefix_when_truncated(self) -> None:
        row = make_row(
            kind="window",
            row_id="@1",
            depth=1,
            text="1 zsh tmux-workspace-sidebar",
            priority_text="1 zsh",
            tree_prefix="  ",
        )
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)

        primary, meta = app.render_row_parts(row, 18)

        self.assertEqual(meta, "")
        self.assertTrue(primary.startswith("    1 zsh "))
        self.assertIn("…", primary)

    def test_session_row_uses_current_session_highlight_when_sidebar_not_focused(self) -> None:
        row = make_row(kind="session", row_id="$2", session_id="$2")
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.sidebar_has_focus = False
        app.current_session_id = "$2"
        app.filter_query = ""
        app.selected_row = lambda: make_row(kind="pane", row_id="%1", session_id="$1", window_id="@1")

        with unittest.mock.patch.object(sidebar.curses, "color_pair", return_value=40):
            attr = sidebar.render_row_attr(app, row)

        self.assertEqual(attr, 40 | sidebar.curses.A_BOLD)

    def test_session_row_uses_selected_session_highlight_when_sidebar_focused(self) -> None:
        row = make_row(kind="session", row_id="$1", session_id="$1")
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.sidebar_has_focus = True
        app.current_session_id = "$2"
        app.filter_query = ""
        app.selected_row = lambda: make_row(kind="pane", row_id="%1", session_id="$1", window_id="@1")

        with unittest.mock.patch.object(sidebar.curses, "color_pair", return_value=40):
            attr = sidebar.render_row_attr(app, row)

        self.assertEqual(attr, 40 | sidebar.curses.A_BOLD)


class SidebarActivationTests(unittest.TestCase):
    def test_activate_selected_window_clears_sidebar_focus_before_switching(self) -> None:
        row = make_row(kind="window", row_id="@2", depth=1, text="window", session_id="$1", window_id="@2")
        app = sidebar.SidebarApp.__new__(sidebar.SidebarApp)
        app.selected_row = lambda: row
        app.find_window = lambda _window_id: sidebar.Window(
            session_id="$1",
            window_id="@2",
            index=1,
            name="window",
            active=False,
            activity=False,
            panes=[
                sidebar.Pane(
                    session_id="$1",
                    window_id="@2",
                    pane_id="%7",
                    index=0,
                    title="shell",
                    command="zsh",
                    active=True,
                    current_path="/tmp/project",
                )
            ],
        )
        app.preview_target = Mock()
        app.apply_optimistic_target = Mock()
        app.clear_filter = Mock()
        app.status_message = ""
        app.pending_reload = False

        call_order: list[str] = []

        with unittest.mock.patch.object(
            sidebar,
            "clear_sidebar_focus_everywhere",
            side_effect=lambda: call_order.append("clear"),
        ), unittest.mock.patch.object(
            sidebar,
            "tmux_run_multi",
            side_effect=lambda *args: call_order.append("run"),
        ):
            app.activate_selected()

        self.assertEqual(call_order, ["clear", "run"])
        app.preview_target.assert_called_once()
        app.apply_optimistic_target.assert_called_once()
        app.clear_filter.assert_called_once()
        self.assertEqual(app.status_message, "")
        self.assertTrue(app.pending_reload)

if __name__ == "__main__":
    unittest.main()
