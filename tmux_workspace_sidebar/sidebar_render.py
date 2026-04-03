from __future__ import annotations

import curses

from tmux_workspace_sidebar.sidebar_tree import row_matches_filter


def draw(app: object, *, status_badge_fn) -> None:
    app.stdscr.erase()
    height, width = app.stdscr.getmaxyx()

    header_height = 1 if height >= 3 else 0
    body_y = header_height
    body_height = max(1, height - 1 - header_height)
    app.ensure_cursor_visible()
    app.publish_selected_key()
    show_cursor = app.sidebar_has_focus
    visible_row_count = 0

    if header_height:
        app.safe_addstr(0, 0, app.header_text(width), width, curses.color_pair(7) | curses.A_BOLD)

    for visible_index in range(body_height):
        row_index = app.scroll + visible_index
        if row_index >= len(app.display_rows):
            break

        row = app.display_rows[row_index]
        if row.kind == "spacer":
            if width > 10:
                divider = "┈" * max(0, width - 3)
                app.safe_addstr(body_y + visible_index, 1, divider, width - 1, curses.A_DIM, pad=False)
            continue
        visible_row_count += 1
        cursor_row = show_cursor and row_index == app.cursor
        attr = app.row_attr(row, focused=cursor_row)
        indicator = app.row_indicator(row, width, focused=cursor_row)
        indicator_attr = app.indicator_attr(row, focused=cursor_row)

        badge = status_badge_fn(row.status, row.unread)
        status_width = app.status_column_width(width)
        text_x = len(indicator)
        text_width = max(0, width - text_x - status_width)
        primary_text, meta_text = app.render_row_parts(row, text_width)

        app.safe_addstr(body_y + visible_index, 0, indicator, text_x + 1, indicator_attr, pad=False)
        app.draw_row_text(body_y + visible_index, text_x, text_width, primary_text, meta_text, attr)

        if status_width > 0:
            badge_x = max(text_x, width - status_width)
            app.safe_addstr(body_y + visible_index, badge_x, " " * status_width, status_width + 1, curses.A_NORMAL, pad=False)
        if badge and status_width > 0:
            badge_x = max(text_x, width - status_width + max(0, (status_width - len(badge)) // 2))
            app.safe_addstr(
                body_y + visible_index,
                badge_x,
                badge,
                min(status_width + 1, len(badge) + 1),
                app.status_attr(row.status),
                pad=False,
            )

    if visible_row_count == 0 and not app.input_action:
        app.draw_empty_state(height, width)

    footer = app.footer_text(width)
    footer_attr = curses.A_DIM
    if app.input_action:
        footer_attr = curses.A_BOLD
    app.safe_addstr(height - 1, 0, footer, width, footer_attr)

    if app.pending_kill:
        app.draw_kill_overlay(height, width)

    if app.input_action:
        cursor_x = min(width - 1, len(app.footer_prefix()) + len(app.input_value))
        curses.curs_set(1)
        app.stdscr.move(height - 1, cursor_x)
    else:
        curses.curs_set(0)

    app.stdscr.refresh()


def footer_prefix(app: object) -> str:
    if app.input_action == "filter":
        return "/"
    return f"{app.input_label}: "


def footer_text(app: object, width: int, *, status_badge_fn, status_labels: dict[str, str]) -> str:
    if app.input_action:
        return app.fit_footer(app.footer_prefix() + app.input_value, width)
    if app.pending_kill:
        return app.fit_footer("Confirm with y  cancel with any other key", width)
    if app.status_message:
        return app.fit_footer(app.status_message, width)
    if app.show_help:
        return app.fit_footer(
            "j/k move  h/l fold  enter open  / filter  tab next-match  [ ] session  { } win  shift←/→ cycle  q close",
            width,
        )

    row = app.selected_row()
    actions = app.context_actions(row)

    if app.filter_query:
        match_count = len(app.matching_row_indexes())
        if match_count == 0:
            return app.fit_footer(f"/{app.filter_query}  no matches  esc clear", width)
        prefix = f"/{app.filter_query}  {match_count} matches  tab next  shift-tab prev  esc clear"
        if actions:
            return app.fit_footer(f"{prefix}  |  {actions}", width)
        return app.fit_footer(prefix, width)

    if row is not None and row.status:
        badge = status_badge_fn(row.status, row.unread)
        label = status_labels.get(row.status, row.status)
        prefix = f"{badge} {label}".strip()
        if row.status_message:
            prefix = f"{prefix}: {row.status_message}" if prefix else row.status_message
        if actions:
            return app.fit_footer(f"{prefix}  |  {actions}", width)
        return app.fit_footer(prefix, width)

    if actions:
        return app.fit_footer(actions, width)

    count = len([row for row in app.display_rows if row.kind != "spacer"])
    return app.fit_footer(f"{count} items  / filter  enter open  n new  r rename  x kill  ? help  q close", width)


def status_attr(status: str) -> int:
    if status == "idle":
        return curses.color_pair(4) | curses.A_BOLD
    if status == "running":
        return curses.color_pair(3) | curses.A_BOLD
    if status == "needs-input":
        return curses.color_pair(5) | curses.A_BOLD
    if status == "done":
        return curses.color_pair(2) | curses.A_BOLD
    if status == "error":
        return curses.color_pair(6) | curses.A_BOLD
    return curses.A_NORMAL


def row_indicator(row: object, focused: bool = False) -> str:
    if focused:
        return "▌"
    if row.current:
        return "▌"
    if row.status in {"needs-input", "error"}:
        return "!"
    return " "


def indicator_attr(row: object, *, status_attr_fn, focused: bool = False) -> int:
    attr = curses.A_DIM
    if row.current:
        attr = curses.color_pair(4) | curses.A_BOLD
    elif row.status in {"needs-input", "error"}:
        attr = status_attr_fn(row.status)
    elif row.activity:
        attr = curses.color_pair(3) | curses.A_BOLD
    elif row.active:
        attr = curses.color_pair(2) | curses.A_BOLD

    if focused:
        attr |= curses.A_REVERSE

    return attr


def row_attr(app: object, row: object, focused: bool = False) -> int:
    if row.kind == "spacer":
        return curses.A_NORMAL

    selected_row = app.selected_row()
    if getattr(app, "sidebar_has_focus", False):
        highlighted_session_id = selected_row.session_id if selected_row else ""
    else:
        highlighted_session_id = getattr(app, "current_session_id", "")

    if row.kind == "session" and row.row_id == highlighted_session_id:
        attr = curses.color_pair(4) | curses.A_BOLD
    elif row.kind == "session":
        attr = curses.color_pair(1) | curses.A_BOLD
    elif row.active:
        attr = curses.color_pair(2) | curses.A_BOLD
    elif row.status in {"needs-input", "error"}:
        attr = status_attr(row.status)
    elif row.activity:
        attr = curses.color_pair(3) | curses.A_BOLD
    elif row.kind == "window":
        attr = curses.color_pair(7)
    elif row.kind == "pane":
        attr = curses.A_NORMAL if row.status else curses.A_DIM
    else:
        attr = curses.A_NORMAL

    query = app.filter_query.strip().lower()
    if query and row_matches_filter(row, query):
        attr |= curses.A_UNDERLINE

    if focused:
        attr = (attr & ~curses.A_DIM) | curses.A_BOLD | curses.A_REVERSE

    return attr


def safe_addstr(app: object, y: int, x: int, text: str, width: int, attr: int, pad: bool = True) -> None:
    if width <= 0:
        return
    clip_width = max(0, width - 1) if pad else max(0, width)
    clipped = text[:clip_width]
    rendered = clipped.ljust(max(0, width - 1)) if pad else clipped
    try:
        app.stdscr.addstr(y, x, rendered, attr)
    except curses.error:
        pass
