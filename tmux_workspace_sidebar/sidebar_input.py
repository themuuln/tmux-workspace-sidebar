from __future__ import annotations

import curses
from typing import Callable


def handle_key(app: object, key: int, *, key_shift_left: int, key_shift_right: int) -> None:
    if app.input_action:
        app.handle_input_key(key)
        return

    if app.pending_kill:
        if key in (ord("y"), ord("Y")):
            app.kill_selected()
        app.pending_kill = None
        return

    if key in (ord("q"), 3):
        app.close_sidebar()
    elif key == ord("?"):
        app.show_help = not app.show_help
    elif key == ord("/"):
        app.start_input("filter", "Filter", app.filter_query)
    elif key in (ord("j"), curses.KEY_DOWN):
        app.move_cursor(1)
    elif key in (ord("k"), curses.KEY_UP):
        app.move_cursor(-1)
    elif key == 9:
        if app.filter_query:
            app.jump_filter_result(1)
    elif key == curses.KEY_BTAB:
        if app.filter_query:
            app.jump_filter_result(-1)
    elif key == 4:
        app.page_move(1)
    elif key == 21:
        app.page_move(-1)
    elif key == curses.KEY_NPAGE:
        app.page_move(1, full_page=True)
    elif key == curses.KEY_PPAGE:
        app.page_move(-1, full_page=True)
    elif key in (ord("g"), curses.KEY_HOME):
        app.cursor = 0
        app.ensure_cursor_visible()
    elif key in (ord("G"), curses.KEY_END):
        if app.display_rows:
            app.cursor = len(app.display_rows) - 1
            app.ensure_cursor_visible()
    elif key == ord("["):
        app.jump_to_kind("session", -1)
    elif key == ord("]"):
        app.jump_to_kind("session", 1)
    elif key == ord("{"):
        app.jump_to_kind("window", -1)
    elif key == ord("}"):
        app.jump_to_kind("window", 1)
    elif key == ord("a"):
        app.jump_to_active_row()
    elif key == key_shift_left:
        app.cycle_window(-1)
    elif key == key_shift_right:
        app.cycle_window(1)
    elif key in (ord("h"), curses.KEY_LEFT):
        app.collapse_selected()
    elif key in (ord("l"), curses.KEY_RIGHT, ord(" ")):
        app.expand_or_activate_selected()
    elif key == ord("o"):
        app.toggle_selected_expansion()
    elif key in (10, 13, curses.KEY_ENTER):
        app.activate_selected()
    elif key == ord("C"):
        app.launch_codex()
    elif key == ord("n"):
        if app.filter_query:
            app.jump_filter_result(1)
        else:
            app.start_input("new_session", "New session", "")
    elif key == ord("N"):
        if app.filter_query:
            app.jump_filter_result(-1)
    elif key == ord("r"):
        app.start_rename()
    elif key == ord("x"):
        if app.selected_row() is not None:
            app.pending_kill = app.selected_row()
            app.status_message = ""
    elif key == curses.KEY_RESIZE:
        app.ensure_cursor_visible()
    elif key == ord("z"):
        app.center_cursor()


def handle_input_key(app: object, key: int) -> None:
    if key in (27,):
        if app.input_action == "filter":
            app.filter_query = ""
            app.refresh_display_rows()
            app.restore_cursor(None)
        app.reset_input()
        return
    if key in (10, 13, curses.KEY_ENTER):
        app.submit_input()
        return
    if key in (curses.KEY_BACKSPACE, 127, 8):
        app.input_value = app.input_value[:-1]
        if app.input_action == "filter":
            app.filter_query = app.input_value
            app.refresh_display_rows()
            app.restore_cursor(None)
        return
    if 32 <= key <= 126:
        app.input_value += chr(key)
        if app.input_action == "filter":
            app.filter_query = app.input_value
            app.refresh_display_rows()
            app.restore_cursor(None)


def start_input(app: object, action: str, label: str, initial_value: str) -> None:
    app.input_action = action
    app.input_label = label
    app.input_value = initial_value
    app.status_message = ""


def start_rename(app: object) -> None:
    row = app.selected_row()
    if row is None:
        return

    if row.kind == "session":
        initial = app.find_session(row.row_id).name
        app.input_target = row
        app.start_input("rename_session", "Rename session", initial)
    elif row.kind == "window":
        initial = app.find_window(row.row_id).name
        app.input_target = row
        app.start_input("rename_window", "Rename window", initial)
    elif row.kind == "pane":
        pane = app.find_pane(row.row_id)
        initial = pane.title or pane.command
        app.input_target = row
        app.start_input("rename_pane", "Rename pane", initial)


def submit_input(
    app: object,
    *,
    tmux_run: Callable[..., None],
    tmux_capture: Callable[..., str],
    non_sidebar_pane: Callable[[str], tuple[str, bool]],
) -> None:
    value = app.input_value.strip()
    if app.input_action == "filter":
        app.filter_query = value
        app.refresh_display_rows()
        matches = app.matching_row_indexes()
        if matches:
            app.cursor = matches[0]
            app.ensure_cursor_visible()
        app.reset_input()
        return

    if not value:
        app.reset_input()
        return

    try:
        if app.input_action == "new_session":
            tmux_run("new-session", "-d", "-s", value, "-c", app.session_creation_path())
            tmux_run("switch-client", "-t", value)
            target_window_id = tmux_capture(
                "display-message",
                "-p",
                "-t",
                value,
                "#{window_id}",
            ).strip()
            target_pane_id, _ = non_sidebar_pane(target_window_id) if target_window_id else ("", False)
            if target_pane_id:
                tmux_run("select-pane", "-t", target_pane_id)
            app.apply_optimistic_target(
                session_id=value,
                window_id=target_window_id,
                pane_id=target_pane_id,
                sidebar_has_focus=False,
            )
        elif app.input_action == "rename_session" and app.input_target:
            tmux_run("rename-session", "-t", app.input_target.row_id, value)
        elif app.input_action == "rename_window" and app.input_target:
            tmux_run("rename-window", "-t", app.input_target.row_id, value)
        elif app.input_action == "rename_pane" and app.input_target:
            tmux_run("select-pane", "-t", app.input_target.row_id, "-T", value)
        app.pending_reload = True
        app.status_message = ""
    except Exception as exc:
        app.status_message = str(exc)
    finally:
        app.reset_input()


def reset_input(app: object) -> None:
    app.input_action = None
    app.input_target = None
    app.input_label = ""
    app.input_value = ""
