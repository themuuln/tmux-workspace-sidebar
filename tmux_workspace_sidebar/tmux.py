from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from tmux_workspace_sidebar.sidebar_tree import Pane, Session, Window


FIELD_SEP = "\t"
SIDEBAR_MARK = "1"


@dataclass(frozen=True)
class CurrentTarget:
    session_id: str
    window_id: str
    pane_id: str


@dataclass(frozen=True)
class TmuxSnapshot:
    current: CurrentTarget
    sessions: list[Session]
    windows: list[Window]
    panes: list[Pane]


def parse_current_target(line: str) -> CurrentTarget:
    parts = line.strip().split(FIELD_SEP)
    if len(parts) != 3:
        raise RuntimeError("Unable to read current tmux target")
    return CurrentTarget(
        session_id=parts[0],
        window_id=parts[1],
        pane_id=parts[2],
    )


def parse_sessions(snapshot: str, current_session_id: str) -> list[Session]:
    sessions: list[Session] = []
    for line in snapshot.splitlines():
        session_id, name, attached = line.split(FIELD_SEP, 2)
        sessions.append(
            Session(
                session_id=session_id,
                name=name,
                attached=int(attached or 0),
                active=session_id == current_session_id,
            )
        )
    return sessions


def parse_windows(snapshot: str) -> list[Window]:
    windows: list[Window] = []
    for line in snapshot.splitlines():
        session_id, window_id, index, name, active, activity = line.split(FIELD_SEP, 5)
        windows.append(
            Window(
                session_id=session_id,
                window_id=window_id,
                index=int(index),
                name=name,
                active=active == "1",
                activity=activity == "1",
            )
        )
    return windows


def parse_panes(snapshot: str) -> list[Pane]:
    panes: list[Pane] = []
    for line in snapshot.splitlines():
        (
            session_id,
            window_id,
            pane_id,
            index,
            title,
            command,
            current_path,
            active,
            is_sidebar,
        ) = line.split(FIELD_SEP, 8)

        if is_sidebar == SIDEBAR_MARK:
            continue

        panes.append(
            Pane(
                session_id=session_id,
                window_id=window_id,
                pane_id=pane_id,
                index=int(index),
                title=title,
                command=command,
                active=active == "1",
                current_path=current_path,
            )
        )
    return panes


class TmuxClient:
    def __init__(self, socket_path: str = "") -> None:
        self.socket_path = socket_path

    def _command(self, *args: str) -> list[str]:
        if self.socket_path:
            return ["tmux", "-S", self.socket_path, *args]
        return ["tmux", *args]

    def capture(self, *args: str) -> str:
        result = subprocess.run(
            self._command(*args),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"tmux {' '.join(args)} failed")
        return result.stdout

    def capture_multi(self, *commands: Tuple[str, ...]) -> list[str]:
        if not commands:
            return []

        marker_prefix = f"__tmux_workspace_sidebar__{uuid.uuid4().hex}__"
        argv: list[str] = self._command()
        markers: list[str] = []
        has_command = False
        for index, command in enumerate(commands):
            if not command:
                continue
            marker = f"{marker_prefix}{index}__"
            markers.append(marker)
            if has_command:
                argv.append(";")
            argv.extend(command)
            argv.append(";")
            argv.extend(("display-message", "-p", marker))
            has_command = True

        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "tmux multi-capture failed")

        parts: list[str] = []
        chunk: list[str] = []
        remaining_markers = set(markers)
        for line in result.stdout.splitlines():
            if line in remaining_markers:
                parts.append("\n".join(chunk))
                chunk = []
                remaining_markers.remove(line)
                continue
            chunk.append(line)

        if remaining_markers:
            raise RuntimeError("tmux multi-capture output was incomplete")
        return parts

    def run(self, *args: str) -> None:
        result = subprocess.run(
            self._command(*args),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"tmux {' '.join(args)} failed")

    def run_multi(self, *commands: Tuple[str, ...]) -> None:
        argv: list[str] = self._command()
        for index, command in enumerate(commands):
            if not command:
                continue
            if index > 0:
                argv.append(";")
            argv.extend(command)

        result = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "tmux multi-command failed")

    def option(self, name: str, default: str = "") -> str:
        result = subprocess.run(
            self._command("show-option", "-gqv", name),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return default
        value = result.stdout.strip()
        return value or default

    def current_target_ids(self) -> Tuple[str, str, str]:
        current = self.current_target()
        return current.session_id, current.window_id, current.pane_id

    def current_target(self) -> CurrentTarget:
        line = self.capture(
            "display-message",
            "-p",
            "#{session_id}\t#{window_id}\t#{pane_id}",
        )
        return parse_current_target(line)

    def snapshot(self) -> TmuxSnapshot:
        parts = self.capture_multi(
            (
                "display-message",
                "-p",
                "#{session_id}\t#{window_id}\t#{pane_id}",
            ),
            (
                "list-sessions",
                "-F",
                "#{session_id}\t#{session_name}\t#{session_attached}",
            ),
            (
                "list-windows",
                "-a",
                "-F",
                "#{session_id}\t#{window_id}\t#{window_index}\t#{window_name}\t"
                "#{window_active}\t#{window_activity_flag}",
            ),
            (
                "list-panes",
                "-a",
                "-F",
                "#{session_id}\t#{window_id}\t#{pane_id}\t#{pane_index}\t"
                "#{pane_title}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_active}\t"
                "#{@workspace_sidebar}",
            ),
        )
        if len(parts) != 4:
            raise RuntimeError("Unable to load tmux snapshot")

        current = parse_current_target(parts[0])
        return TmuxSnapshot(
            current=current,
            sessions=parse_sessions(parts[1], current.session_id),
            windows=parse_windows(parts[2]),
            panes=parse_panes(parts[3]),
        )

    def non_sidebar_pane(self, window_id: str) -> Tuple[str, bool]:
        lines = self.capture(
            "list-panes",
            "-t",
            window_id,
            "-F",
            "#{pane_id}\t#{pane_active}\t#{@workspace_sidebar}",
        ).splitlines()

        fallback = ""
        for line in lines:
            pane_id, active, is_sidebar = line.split(FIELD_SEP, 2)
            if is_sidebar == SIDEBAR_MARK:
                continue
            if active == "1":
                return pane_id, True
            if not fallback:
                fallback = pane_id

        return fallback, False

    def clear_sidebar_focus_everywhere(self) -> None:
        lines = self.capture(
            "list-panes",
            "-a",
            "-F",
            "#{window_id}\t#{pane_active}\t#{@workspace_sidebar}",
        ).splitlines()

        window_ids: list[str] = []
        seen = set()
        for line in lines:
            window_id, active, is_sidebar = line.split(FIELD_SEP, 2)
            if active != "1" or is_sidebar != SIDEBAR_MARK or window_id in seen:
                continue
            seen.add(window_id)
            window_ids.append(window_id)

        for window_id in window_ids:
            target_pane_id, _ = self.non_sidebar_pane(window_id)
            if target_pane_id:
                self.run("select-pane", "-t", target_pane_id)


def default_client() -> TmuxClient:
    return TmuxClient()
