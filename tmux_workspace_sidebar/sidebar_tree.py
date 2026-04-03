from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from tmux_workspace_sidebar.apps import (
    infer_live_pane_state,
    label_for_cli_value,
    should_clear_stale_state,
)


GENERIC_LABELS = {
    "",
    "bash",
    "fish",
    "script",
    "sh",
    "shell",
    "tmux",
    "zsh",
}
STATUS_PRIORITY = {
    "": 0,
    "idle": 1,
    "done": 2,
    "running": 3,
    "error": 4,
    "needs-input": 5,
}


def path_leaf(path: str) -> str:
    expanded_home = os.path.expanduser("~")
    normalized = (path or "").strip()
    if not normalized:
        return ""
    if normalized == expanded_home:
        return "~"
    stripped = normalized.rstrip("/")
    if not stripped:
        return "/"
    return os.path.basename(stripped) or stripped


def is_generic_label(value: str) -> bool:
    return value.strip().lower() in GENERIC_LABELS

@dataclass
class Pane:
    session_id: str
    window_id: str
    pane_id: str
    index: int
    title: str
    command: str
    active: bool
    current_path: str
    app: str = ""
    status: str = ""
    status_message: str = ""
    unread: bool = False

    def cli_name(self) -> str:
        app = self.app.strip().lower()
        if app:
            return label_for_cli_value(app) or app

        command = (self.command.strip() or "shell").lower()
        title = self.title.strip().lower()

        for value in (command, title):
            label = label_for_cli_value(value)
            if label:
                return label

        return command or "shell"

    def label(self, display_index: Optional[int] = None) -> str:
        pane_index = display_index if display_index is not None else self.index
        title = self.title.strip()
        command = self.cli_name()
        location = path_leaf(self.current_path)

        if title and title.lower() != command.lower() and not is_generic_label(title):
            name = title
        elif location and location != "/":
            name = location
        else:
            name = command

        if command and name.lower() != command.lower():
            name = f"{command} {name}"

        return f"{pane_index} {name}"


@dataclass
class Window:
    session_id: str
    window_id: str
    index: int
    name: str
    active: bool
    activity: bool
    panes: List[Pane] = field(default_factory=list)

    def primary_cli_name(self) -> str:
        for pane in self.panes:
            if pane.active:
                return pane.cli_name()
        if self.panes:
            return self.panes[0].cli_name()
        return ""

    def label(self) -> str:
        cli_name = self.primary_cli_name()
        name = self.name.strip()
        if is_generic_label(name):
            fallback = path_leaf(self.preferred_path())
            if fallback and fallback != "/":
                name = fallback
            else:
                name = ""

        parts = [str(self.index)]
        if cli_name:
            parts.append(cli_name)
        if name and name.lower() != cli_name.lower():
            parts.append(name)
        if len(parts) == 1:
            parts.append("window")
        return " ".join(parts)

    def preferred_path(self) -> str:
        for pane in self.panes:
            if pane.active:
                return pane.current_path
        if self.panes:
            return self.panes[0].current_path
        return os.path.expanduser("~")

    def active_pane_id(self) -> str:
        for pane in self.panes:
            if pane.active:
                return pane.pane_id
        if self.panes:
            return self.panes[0].pane_id
        return ""


@dataclass
class Session:
    session_id: str
    name: str
    attached: int
    active: bool
    windows: List[Window] = field(default_factory=list)

    def label(self) -> str:
        suffix = f" ({self.attached})" if self.attached > 1 else ""
        return f"{self.name}{suffix}"

    def preferred_path(self) -> str:
        for window in self.windows:
            if window.active:
                return window.preferred_path()
        if self.windows:
            return self.windows[0].preferred_path()
        return os.path.expanduser("~")

    def active_window_id(self) -> str:
        for window in self.windows:
            if window.active:
                return window.window_id
        if self.windows:
            return self.windows[0].window_id
        return ""


@dataclass
class Row:
    kind: str
    row_id: str
    depth: int
    text: str
    priority_text: str = ""
    meta: str = ""
    tree_prefix: str = ""
    active: bool = False
    activity: bool = False
    expandable: bool = False
    expanded: bool = False
    session_id: str = ""
    window_id: str = ""
    path: str = ""
    status: str = ""
    status_message: str = ""
    unread: bool = False
    current: bool = False

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.row_id}"

    def render(self) -> str:
        if self.expandable:
            state = "▾ " if self.expanded else "▸ "
        else:
            state = "  "
        return f"{self.tree_prefix}{state}{self.text}"


def merge_snapshot_state(
    sessions: Sequence[Session],
    windows: Sequence[Window],
    panes: Sequence[Pane],
    pane_states: Dict[str, dict],
) -> List[Session]:
    windows_by_id = {window.window_id: window for window in windows}
    sessions_by_id = {session.session_id: session for session in sessions}

    for window in windows:
        window.panes = []
    for session in sessions:
        session.windows = []

    for pane in panes:
        state = pane_states.get(pane.pane_id)
        if state:
            pane.app = str(state.get("app") or "")
            pane.status = str(state.get("status") or "")
            pane.status_message = str(state.get("message") or "")
            pane.unread = bool(state.get("unread"))
            if should_clear_stale_state(pane.app, pane.command, pane.title):
                pane.app = ""
                pane.status = ""
                pane.status_message = ""
                pane.unread = False
        inferred_app, inferred_status = infer_live_pane_state(
            pane.command,
            pane.title,
            pane.app,
            pane.status,
        )
        if inferred_app and not pane.app:
            pane.app = inferred_app
        if inferred_status and pane.status not in {"needs-input", "error"}:
            pane.status = inferred_status
        window = windows_by_id.get(pane.window_id)
        if window is not None:
            window.panes.append(pane)

    for window in windows:
        session = sessions_by_id.get(window.session_id)
        if session is not None:
            session.windows.append(window)

    for session in sessions:
        session.windows.sort(key=lambda item: item.index)
        for window in session.windows:
            window.panes.sort(key=lambda item: item.index)

    return list(sessions)


def reconcile_expansion_state(
    sessions: Sequence[Session],
    expanded_sessions: set[str],
    expanded_windows: set[str],
    *,
    current_session_id: str,
    current_window_id: str,
    initialized: bool,
) -> bool:
    session_ids = {session.session_id for session in sessions}
    window_ids = {
        window.window_id
        for session in sessions
        for window in session.windows
    }
    new_session_ids = session_ids - expanded_sessions

    expanded_sessions &= session_ids
    expanded_windows &= window_ids

    if not initialized:
        expanded_sessions |= session_ids
        expanded_windows.add(current_window_id)
        return True

    expanded_sessions |= new_session_ids
    expanded_sessions.add(current_session_id)
    expanded_windows.add(current_window_id)
    return initialized


def ensure_selected_key_visible(
    selected_key: Optional[str],
    sessions: Sequence[Session],
    expanded_sessions: set[str],
    expanded_windows: set[str],
) -> None:
    if not selected_key or ":" not in selected_key:
        return

    kind, row_id = selected_key.split(":", 1)
    if kind == "session":
        expanded_sessions.add(row_id)
        return

    for session in sessions:
        for window in session.windows:
            if kind == "window" and window.window_id == row_id:
                expanded_sessions.add(session.session_id)
                if len(window.panes) > 1:
                    expanded_windows.add(window.window_id)
                return
            if kind == "pane" and any(pane.pane_id == row_id for pane in window.panes):
                expanded_sessions.add(session.session_id)
                if len(window.panes) > 1:
                    expanded_windows.add(window.window_id)
                return


def aggregate_status(panes: Sequence[Pane]) -> Tuple[str, str, bool]:
    best_status = ""
    best_message = ""
    best_priority = 0
    best_unread = False

    for pane in panes:
        priority = STATUS_PRIORITY.get(pane.status, 0)
        if priority > best_priority or (priority == best_priority and pane.unread and not best_unread):
            best_priority = priority
            best_status = pane.status
            best_message = pane.status_message
            best_unread = pane.unread

    return best_status, best_message, best_unread


def actionable_count(panes: Sequence[Pane]) -> int:
    return sum(1 for pane in panes if pane.status in {"needs-input", "error"} or (pane.status == "done" and pane.unread))


def running_count(panes: Sequence[Pane]) -> int:
    return sum(1 for pane in panes if pane.status == "running")


def summarize_counts(*, windows: int = 0, panes: int = 0, actionable: int = 0, running: int = 0, path: str = "") -> str:
    parts: List[str] = []
    if windows > 0:
        parts.append(f"{windows}w")
    if panes > 0:
        parts.append(f"{panes}p")
    if actionable > 0:
        parts.append(f"{actionable}!")
    if running > 0:
        parts.append(f"{running}r")
    location = path_leaf(path)
    if location and location not in {"", "/", "~"}:
        parts.append(f"@{location}")
    return " · ".join(parts)


def build_rows(
    sessions: Sequence[Session],
    expanded_sessions: set[str],
    expanded_windows: set[str],
    *,
    current_session_id: str,
    current_window_id: str,
    current_pane_id: str,
) -> List[Row]:
    rows: List[Row] = []
    for session_index, session in enumerate(sessions):
        if session_index > 0:
            rows.append(Row(kind="spacer", row_id=f"spacer-{session_index}", depth=-1, text=""))
        session_expanded = session.session_id in expanded_sessions
        session_panes = [pane for window in session.windows for pane in window.panes]
        session_has_active_descendant = any(
            pane.pane_id == current_pane_id for pane in session_panes
        )
        session_status, session_message, session_unread = aggregate_status(session_panes)
        rows.append(
            Row(
                kind="session",
                row_id=session.session_id,
                depth=0,
                text=session.label(),
                meta=summarize_counts(
                    windows=len(session.windows),
                    panes=len(session_panes),
                    actionable=actionable_count(session_panes),
                    running=running_count(session_panes),
                ),
                tree_prefix="",
                active=session.session_id == current_session_id and not session_has_active_descendant,
                expandable=bool(session.windows),
                expanded=session_expanded,
                session_id=session.session_id,
                path=session.preferred_path(),
                status=session_status,
                status_message=session_message,
                unread=session_unread,
                current=session.session_id == current_session_id,
            )
        )

        if not session_expanded:
            continue

        for window in session.windows:
            show_panes = len(window.panes) > 1
            window_expanded = window.window_id in expanded_windows
            window_status, window_message, window_unread = aggregate_status(window.panes)
            window_has_active_descendant = show_panes and any(
                pane.pane_id == current_pane_id for pane in window.panes
            )
            rows.append(
                Row(
                    kind="window",
                    row_id=window.window_id,
                    depth=1,
                    text=window.label(),
                    priority_text=f"{window.index} {window.primary_cli_name()}".strip(),
                    meta=summarize_counts(path=window.preferred_path()),
                    tree_prefix="  ",
                    active=window.window_id == current_window_id and not window_has_active_descendant,
                    activity=window.activity,
                    expandable=show_panes,
                    expanded=show_panes and window_expanded,
                    session_id=session.session_id,
                    window_id=window.window_id,
                    path=window.preferred_path(),
                    status=window_status,
                    status_message=window_message,
                    unread=window_unread,
                    current=window.window_id == current_window_id,
                )
            )

            if not show_panes or not window_expanded:
                continue

            for pane_position, pane in enumerate(window.panes, start=1):
                rows.append(
                    Row(
                        kind="pane",
                        row_id=pane.pane_id,
                        depth=2,
                        text=pane.label(display_index=pane_position),
                        priority_text=f"{pane_position} {pane.cli_name()}".strip(),
                        meta="",
                        tree_prefix="    ",
                        active=pane.pane_id == current_pane_id,
                        session_id=session.session_id,
                        window_id=window.window_id,
                        path=pane.current_path,
                        status=pane.status,
                        status_message=pane.status_message,
                        unread=pane.unread,
                        current=pane.pane_id == current_pane_id,
                    )
                )
    return rows


def row_matches_filter(row: Row, query: str) -> bool:
    haystack = " ".join(
        [
            row.text,
            row.meta,
            row.path,
            row.status,
            row.status_message,
            row.kind,
        ]
    ).lower()
    return query in haystack


def filtered_rows(rows: Sequence[Row], query: str) -> List[Row]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return list(rows)

    filtered: List[Row] = []
    group: List[Row] = []

    def flush_group() -> None:
        nonlocal filtered, group
        if not group:
            return

        session_row = group[0]
        descendants = group[1:]
        visible_group: List[Row] = []

        if row_matches_filter(session_row, normalized_query):
            visible_group = list(group)
        else:
            matching_window_ids = set()
            matching_pane_ids = set()

            for row in descendants:
                if row.kind == "window" and row_matches_filter(row, normalized_query):
                    matching_window_ids.add(row.row_id)
                elif row.kind == "pane" and row_matches_filter(row, normalized_query):
                    matching_pane_ids.add(row.row_id)
                    matching_window_ids.add(row.window_id)

            if matching_window_ids or matching_pane_ids:
                visible_group.append(session_row)
                for row in descendants:
                    if row.kind == "window" and row.row_id in matching_window_ids:
                        visible_group.append(row)
                    elif row.kind == "pane" and row.row_id in matching_pane_ids:
                        visible_group.append(row)

        if visible_group:
            if filtered:
                filtered.append(Row(kind="spacer", row_id=f"filter-spacer-{len(filtered)}", depth=-1, text=""))
            filtered.extend(visible_group)

        group = []

    for row in rows:
        if row.kind == "spacer":
            flush_group()
            continue
        group.append(row)
    flush_group()

    return filtered


def matching_row_indexes(rows: Sequence[Row], query: str) -> List[int]:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []
    return [
        index
        for index, row in enumerate(rows)
        if row.kind != "spacer" and row_matches_filter(row, normalized_query)
    ]
