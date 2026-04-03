from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Tuple

from tmux_workspace_sidebar.navigation import select_wrapped_window_target
from tmux_workspace_sidebar.sidebar_tree import Row


TmuxCapture = Callable[..., str]
TmuxOption = Callable[[str, str], str]
TmuxRun = Callable[..., None]
TmuxRunMulti = Callable[..., None]
PaneResolver = Callable[[str], tuple[str, bool]]
FocusReset = Callable[[], None]


@dataclass(frozen=True)
class SidebarTarget:
    session_id: str
    window_id: str = ""
    pane_id: str = ""
    selected_key: str = ""


class SidebarActionHost(Protocol):
    current_session_id: str
    current_window_id: str
    status_message: str
    pending_reload: bool

    def selected_row(self) -> Optional[Row]: ...
    def preview_target(
        self,
        *,
        session_id: str = "",
        window_id: str = "",
        pane_id: str = "",
        sidebar_has_focus: bool = False,
        selected_key: Optional[str] = None,
    ) -> None: ...
    def apply_optimistic_target(
        self,
        *,
        session_id: str = "",
        window_id: str = "",
        pane_id: str = "",
        sidebar_has_focus: bool = False,
        selected_key: Optional[str] = None,
    ) -> None: ...
    def clear_filter(self) -> None: ...
    def signal_refresh(self) -> None: ...
    def window_targets(self) -> List[Tuple[str, str]]: ...
    def find_session(self, session_id: str): ...
    def find_window(self, window_id: str): ...


class SidebarActionService:
    def __init__(
        self,
        *,
        tmux_capture: TmuxCapture,
        tmux_option: TmuxOption,
        tmux_run: TmuxRun,
        tmux_run_multi: TmuxRunMulti,
        non_sidebar_pane: PaneResolver,
        clear_sidebar_focus_everywhere: FocusReset,
    ) -> None:
        self.tmux_capture = tmux_capture
        self.tmux_option = tmux_option
        self.tmux_run = tmux_run
        self.tmux_run_multi = tmux_run_multi
        self.non_sidebar_pane = non_sidebar_pane
        self.clear_sidebar_focus_everywhere = clear_sidebar_focus_everywhere

    def cycle_window(self, app: SidebarActionHost, step: int) -> None:
        target_ref = select_wrapped_window_target(
            app.window_targets(),
            app.current_session_id,
            app.current_window_id,
            step,
        )
        if not target_ref or target_ref == (app.current_session_id, app.current_window_id):
            return

        target_session_id, target_window_id = target_ref
        try:
            target_window = app.find_window(target_window_id)
            target = SidebarTarget(
                session_id=target_session_id,
                window_id=target_window_id,
                pane_id=target_window.active_pane_id(),
                selected_key=f"window:{target_window_id}",
            )
            self._switch_to_target(app, target)
            app.signal_refresh()
        except Exception as exc:
            app.status_message = str(exc)

    def activate_selected(self, app: SidebarActionHost) -> None:
        row = app.selected_row()
        if row is None:
            return

        try:
            target = self._target_for_row(app, row)
            if target is None:
                return
            self._switch_to_target(app, target)
            app.clear_filter()
        except Exception as exc:
            app.status_message = str(exc)

    def kill_selected(self, app: SidebarActionHost) -> None:
        row = app.selected_row()
        if row is None:
            return
        try:
            if row.kind == "session":
                self.tmux_run("kill-session", "-t", row.row_id)
            elif row.kind == "window":
                self.tmux_run("kill-window", "-t", row.row_id)
            elif row.kind == "pane":
                self.tmux_run("kill-pane", "-t", row.row_id)
            app.pending_reload = True
        except Exception as exc:
            app.status_message = str(exc)

    def launch_codex(self, app: SidebarActionHost) -> None:
        row = app.selected_row()
        if row is None:
            return

        command = self.tmux_option("@workspace_sidebar_codex_command", "codex").strip()
        window_name = self.tmux_option("@workspace_sidebar_codex_window_name", "codex").strip() or "codex"
        if not command:
            app.status_message = "Codex command is empty"
            return

        try:
            new_window_id = self.tmux_capture(
                "new-window",
                "-P",
                "-F",
                "#{window_id}",
                "-t",
                row.session_id,
                "-n",
                window_name,
                "-c",
                row.path or os.path.expanduser("~"),
                command,
            ).strip()
            target = SidebarTarget(
                session_id=row.session_id,
                window_id=new_window_id,
                selected_key=row.key,
            )
            app.preview_target(
                session_id=target.session_id,
                window_id=target.window_id,
                pane_id=target.pane_id,
                sidebar_has_focus=False,
                selected_key=target.selected_key,
            )
            self.tmux_run_multi(
                ("switch-client", "-t", target.session_id),
                ("select-window", "-t", target.window_id),
            )
            target_pane_id, _ = self.non_sidebar_pane(new_window_id)
            if target_pane_id:
                self.tmux_run("select-pane", "-t", target_pane_id)
            app.apply_optimistic_target(
                session_id=target.session_id,
                window_id=target.window_id,
                pane_id=target_pane_id,
                sidebar_has_focus=False,
                selected_key=target.selected_key,
            )
            app.pending_reload = True
            app.status_message = ""
        except Exception as exc:
            app.status_message = str(exc)

    def _switch_to_target(self, app: SidebarActionHost, target: SidebarTarget) -> None:
        app.preview_target(
            session_id=target.session_id,
            window_id=target.window_id,
            pane_id=target.pane_id,
            sidebar_has_focus=False,
            selected_key=target.selected_key,
        )
        self.clear_sidebar_focus_everywhere()
        self.tmux_run_multi(*self._commands_for_target(target))
        app.apply_optimistic_target(
            session_id=target.session_id,
            window_id=target.window_id,
            pane_id=target.pane_id,
            sidebar_has_focus=False,
            selected_key=target.selected_key,
        )
        app.status_message = ""
        app.pending_reload = True

    def _target_for_row(self, app: SidebarActionHost, row: Row) -> Optional[SidebarTarget]:
        if row.kind == "session":
            session = app.find_session(row.row_id)
            target_window_id = session.active_window_id()
            target_pane_id = app.find_window(target_window_id).active_pane_id() if target_window_id else ""
            return SidebarTarget(
                session_id=row.row_id,
                window_id=target_window_id,
                pane_id=target_pane_id,
                selected_key=row.key,
            )

        if row.kind == "window":
            target_window = app.find_window(row.row_id)
            return SidebarTarget(
                session_id=row.session_id,
                window_id=row.row_id,
                pane_id=target_window.active_pane_id(),
                selected_key=row.key,
            )

        if row.kind == "pane":
            return SidebarTarget(
                session_id=row.session_id,
                window_id=row.window_id,
                pane_id=row.row_id,
                selected_key=row.key,
            )

        return None

    def _commands_for_target(self, target: SidebarTarget) -> List[Tuple[str, ...]]:
        commands: List[Tuple[str, ...]] = []
        if target.session_id:
            commands.append(("switch-client", "-t", target.session_id))
        if target.window_id:
            commands.append(("select-window", "-t", target.window_id))
        if target.pane_id:
            commands.append(("select-pane", "-t", target.pane_id))
        return commands
