from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tmux_workspace_sidebar.apps import (
    actionable_sort_order_for_app,
    actionable_statuses_for_app,
    notification_priority_for_app,
    notification_tag_for_app,
    notification_title_for_app,
)

STATUS_LABELS = {
    "needs-input": "ASK",
    "error": "ERR",
    "done": "DONE",
}
SELECTION_STATE_FILE = "selection.json"


@dataclass(frozen=True)
class ActionableCandidate:
    app: str
    status: str
    unread: bool
    updated_at: int
    pane_id: str
    session_id: str
    session_name: str
    window_id: str
    window_name: str
    path: str
    message: str

    def target(self) -> tuple[str, str, str]:
        return self.session_id, self.window_id, self.pane_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaneStateService:
    def update(
        self,
        state_file: Path,
        *,
        pane_id: str,
        app: str,
        status: str,
        message: str,
        updated_at: int,
        session_id: str,
        window_id: str,
        pane_title: str,
        pane_current_command: str,
        pane_current_path: str,
    ) -> dict[str, Any] | None:
        existing = load_state_file(state_file)
        if existing:
            existing_updated_at = existing.get("updated_at")
            if isinstance(existing_updated_at, int) and existing_updated_at > updated_at:
                return None
        previous_status = str((existing or {}).get("status") or "")
        previous_message = str((existing or {}).get("message") or "")
        previous_unread = bool((existing or {}).get("unread"))
        unread = False
        if status in actionable_statuses_for_app(app):
            unread = previous_unread
            if previous_status != status or previous_message != message:
                unread = True

        payload: dict[str, Any] = {
            "pane_id": pane_id,
            "app": app,
            "status": status,
            "unread": unread,
            "message": message,
            "updated_at": updated_at,
            "session_id": session_id,
            "window_id": window_id,
            "pane_title": pane_title,
            "pane_current_command": pane_current_command,
            "pane_current_path": pane_current_path,
        }
        write_json_atomic(state_file, payload)
        return payload

    def clear_actionable(self, state_file: Path, *, updated_at: int | None = None) -> dict[str, Any] | None:
        state = load_state_file(state_file)
        if not state:
            return None
        status = str(state.get("status") or "")
        app = str(state.get("app") or "")
        if status not in actionable_statuses_for_app(app):
            return None
        if status == "done":
            if not bool(state.get("unread")):
                return None
            state["unread"] = False
            state["updated_at"] = int(updated_at if updated_at is not None else time.time())
            write_json_atomic(state_file, state)
            return state

        state["status"] = "idle"
        state["unread"] = False
        state["message"] = ""
        state["updated_at"] = int(updated_at if updated_at is not None else time.time())
        write_json_atomic(state_file, state)
        return state

    def actionable_candidates(self, *, states_dir: Path, tmux_panes: str) -> list[ActionableCandidate]:
        live_panes = parse_live_pane_metadata(tmux_panes)
        candidates: list[ActionableCandidate] = []

        if states_dir.is_dir():
            for path in sorted(states_dir.glob("pane-*.json")):
                data = load_state_file(path)
                if not data:
                    continue
                pane_id = str(data.get("pane_id") or "")
                status = str(data.get("status") or "")
                unread = bool(data.get("unread"))
                app = str(data.get("app") or "").strip().lower()
                if not pane_id or pane_id not in live_panes:
                    continue
                if status not in actionable_statuses_for_app(app):
                    continue
                if status == "done" and not unread:
                    continue
                updated_at = data.get("updated_at")
                if not isinstance(updated_at, int):
                    updated_at = 0
                message = " ".join(str(data.get("message") or "").split())
                meta = live_panes[pane_id]
                candidates.append(
                    ActionableCandidate(
                        app=app,
                        status=status,
                        unread=unread,
                        updated_at=updated_at,
                        pane_id=pane_id,
                        session_id=meta["session_id"],
                        session_name=meta["session_name"],
                        window_id=meta["window_id"],
                        window_name=meta["window_name"],
                        path=meta["path"],
                        message=message,
                    )
                )

        candidates.sort(
            key=lambda item: (
                actionable_sort_order_for_app(item.app, item.status),
                item.updated_at,
                item.pane_id,
            )
        )
        return candidates

    def build_notification_payload(
        self,
        previous_state: dict[str, Any] | None,
        current_state: dict[str, Any],
        *,
        notify_statuses: set[str] | None = None,
    ) -> dict[str, str] | None:
        if notify_statuses is None:
            notify_statuses = {"done", "needs-input", "error"}

        app = str(current_state.get("app") or "").strip().lower()
        status = str(current_state.get("status") or "").strip().lower()
        message = " ".join(str(current_state.get("message") or "").split())

        if status not in notify_statuses:
            return None

        previous_app = str((previous_state or {}).get("app") or "").strip().lower()
        previous_status = str((previous_state or {}).get("status") or "").strip().lower()
        previous_message = " ".join(str((previous_state or {}).get("message") or "").split())

        if previous_app == app and previous_status == status and previous_message == message:
            return None

        pane_path = str(current_state.get("pane_current_path") or "").strip()
        pane_title = str(current_state.get("pane_title") or "").strip()
        location = short_path(pane_path) or pane_title or str(current_state.get("pane_id") or "").strip()
        body_parts = [part for part in (location, truncate(message, limit=180)) if part]
        body = "\n".join(body_parts).strip()

        return {
            "app": app,
            "status": status,
            "title": notification_title_for_app(app, status),
            "body": body or notification_title_for_app(app, status),
            "priority": notification_priority_for_app(app, status),
            "tags": notification_tag_for_app(app, status),
            "pane_id": str(current_state.get("pane_id") or ""),
            "session_id": str(current_state.get("session_id") or ""),
            "window_id": str(current_state.get("window_id") or ""),
            "pane_title": pane_title,
            "pane_current_path": pane_path,
            "message": message,
        }

    def select_actionable_target(
        self,
        *,
        action: str,
        current_pane_id: str,
        tmux_panes: str,
        states_dir: Path,
    ) -> tuple[str, str, str] | None:
        candidates = self.actionable_candidates(states_dir=states_dir, tmux_panes=tmux_panes)
        if not candidates:
            return None

        index = 0
        if action == "next":
            pane_ids = [item.pane_id for item in candidates]
            if current_pane_id in pane_ids:
                index = (pane_ids.index(current_pane_id) + 1) % len(candidates)

        return candidates[index].target()

    def resolve_actionable_pane_target(
        self,
        *,
        pane_id: str,
        tmux_panes: str,
        states_dir: Path,
    ) -> tuple[str, str, str] | None:
        for candidate in self.actionable_candidates(states_dir=states_dir, tmux_panes=tmux_panes):
            if candidate.pane_id == pane_id:
                return candidate.target()
        return None


DEFAULT_PANE_STATE_SERVICE = PaneStateService()


def sidebar_cache_dir(cache_home: str | None = None) -> Path:
    root = cache_home or os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(root) / "tmux-workspace-sidebar"


def server_hash(socket_path: str) -> str:
    return hashlib.sha256(socket_path.encode("utf-8")).hexdigest()


def event_file_for_socket(socket_path: str, cache_home: str | None = None) -> Path:
    return sidebar_cache_dir(cache_home) / f"{server_hash(socket_path)}.event"


def state_dir(*, cache_home: str | None = None, socket_path: str = "", event_file: str = "") -> Path:
    if event_file and event_file.endswith(".event"):
        event_path = Path(event_file)
        return event_path.parent / event_path.name[: -len(".event")] / "state"
    if socket_path:
        return sidebar_cache_dir(cache_home) / server_hash(socket_path) / "state"
    return sidebar_cache_dir(cache_home) / "state"


def load_state_file(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def load_pane_states(directory: Path) -> dict[str, dict[str, Any]]:
    if not directory.is_dir():
        return {}

    states: dict[str, dict[str, Any]] = {}
    for path in directory.iterdir():
        if not path.name.startswith("pane-") or path.suffix != ".json":
            continue
        state = load_state_file(path)
        if not state:
            continue
        pane_id = str(state.get("pane_id") or "")
        if pane_id:
            states[pane_id] = state
    return states


def selection_state_file(directory: Path) -> Path:
    return directory / SELECTION_STATE_FILE


def load_selection_key(directory: Path) -> str:
    state = load_state_file(selection_state_file(directory))
    if not state:
        return ""
    selected_key = state.get("selected_key")
    return str(selected_key) if isinstance(selected_key, str) else ""


def update_selection_key(
    directory: Path,
    *,
    selected_key: str,
    updated_at: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "selected_key": selected_key,
        "updated_at": int(updated_at if updated_at is not None else time.time()),
    }
    write_json_atomic(selection_state_file(directory), payload)
    return payload


def update_state_file(
    state_file: Path,
    *,
    pane_id: str,
    app: str,
    status: str,
    message: str,
    updated_at: int,
    session_id: str,
    window_id: str,
    pane_title: str,
    pane_current_command: str,
    pane_current_path: str,
) -> dict[str, Any] | None:
    return DEFAULT_PANE_STATE_SERVICE.update(
        state_file,
        pane_id=pane_id,
        app=app,
        status=status,
        message=message,
        updated_at=updated_at,
        session_id=session_id,
        window_id=window_id,
        pane_title=pane_title,
        pane_current_command=pane_current_command,
        pane_current_path=pane_current_path,
    )


def clear_actionable_state_file(state_file: Path, *, updated_at: int | None = None) -> dict[str, Any] | None:
    return DEFAULT_PANE_STATE_SERVICE.clear_actionable(state_file, updated_at=updated_at)


def parse_live_panes(tmux_panes: str) -> dict[str, tuple[str, str]]:
    live_panes: dict[str, tuple[str, str]] = {}
    for line in tmux_panes.splitlines():
        pane_id, session_id, window_id, sidebar_flag = (line.split("\t") + ["", "", "", ""])[:4]
        if not pane_id or sidebar_flag == "1":
            continue
        live_panes[pane_id] = (session_id, window_id)
    return live_panes


def parse_live_pane_metadata(tmux_panes: str) -> dict[str, dict[str, str]]:
    live_panes: dict[str, dict[str, str]] = {}
    for line in tmux_panes.splitlines():
        parts = line.split("\t")
        if len(parts) >= 7:
            pane_id, session_id, session_name, window_id, window_name, pane_path, sidebar_flag = (
                parts + ["", "", "", "", "", "", ""]
            )[:7]
        else:
            pane_id, session_id, window_id, sidebar_flag = (parts + ["", "", "", ""])[:4]
            session_name = ""
            window_name = ""
            pane_path = ""
        if not pane_id or sidebar_flag == "1":
            continue
        live_panes[pane_id] = {
            "session_id": session_id,
            "session_name": session_name,
            "window_id": window_id,
            "window_name": window_name,
            "path": pane_path,
        }
    return live_panes


def list_actionable_candidates(*, states_dir: Path, tmux_panes: str) -> list[dict[str, Any]]:
    return [
        candidate.to_dict()
        for candidate in DEFAULT_PANE_STATE_SERVICE.actionable_candidates(
            states_dir=states_dir,
            tmux_panes=tmux_panes,
        )
    ]


def short_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    if path.startswith(home + os.sep):
        path = "~/" + path[len(home) + 1 :]
    return path


def age_label(updated_at: int) -> str:
    now = int(time.time())
    delta = max(0, now - updated_at)
    if delta < 60:
        return f"{delta}s"
    if delta < 3600:
        return f"{delta // 60}m"
    if delta < 86400:
        return f"{delta // 3600}h"
    return f"{delta // 86400}d"


def truncate(text: str, limit: int = 96) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def parse_status_list(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def build_notification_payload(
    previous_state: dict[str, Any] | None,
    current_state: dict[str, Any],
    *,
    notify_statuses: set[str] | None = None,
) -> dict[str, str] | None:
    return DEFAULT_PANE_STATE_SERVICE.build_notification_payload(
        previous_state,
        current_state,
        notify_statuses=notify_statuses,
    )


def select_actionable_target(
    *,
    action: str,
    current_pane_id: str,
    tmux_panes: str,
    states_dir: Path,
) -> tuple[str, str, str] | None:
    return DEFAULT_PANE_STATE_SERVICE.select_actionable_target(
        action=action,
        current_pane_id=current_pane_id,
        tmux_panes=tmux_panes,
        states_dir=states_dir,
    )


def resolve_actionable_pane_target(
    *,
    pane_id: str,
    tmux_panes: str,
    states_dir: Path,
) -> tuple[str, str, str] | None:
    return DEFAULT_PANE_STATE_SERVICE.resolve_actionable_pane_target(
        pane_id=pane_id,
        tmux_panes=tmux_panes,
        states_dir=states_dir,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pane state helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_state = subparsers.add_parser("apply-state-update", help="Write a pane state file and emit notification metadata")
    apply_state.add_argument("--state-file", required=True)
    apply_state.add_argument("--pane-id", required=True)
    apply_state.add_argument("--app", default="")
    apply_state.add_argument("--status", default="")
    apply_state.add_argument("--message", default="")
    apply_state.add_argument("--updated-at", type=int, required=True)
    apply_state.add_argument("--session-id", default="")
    apply_state.add_argument("--window-id", default="")
    apply_state.add_argument("--pane-title", default="")
    apply_state.add_argument("--pane-current-command", default="")
    apply_state.add_argument("--pane-current-path", default="")
    apply_state.add_argument("--notify-statuses", default="needs-input,error,done")

    write_state = subparsers.add_parser("write-state", help="Write a pane state file")
    write_state.add_argument("--state-file", required=True)
    write_state.add_argument("--pane-id", required=True)
    write_state.add_argument("--app", default="")
    write_state.add_argument("--status", default="")
    write_state.add_argument("--message", default="")
    write_state.add_argument("--updated-at", type=int, required=True)
    write_state.add_argument("--session-id", default="")
    write_state.add_argument("--window-id", default="")
    write_state.add_argument("--pane-title", default="")
    write_state.add_argument("--pane-current-command", default="")
    write_state.add_argument("--pane-current-path", default="")

    clear_state = subparsers.add_parser("clear-actionable", help="Clear an actionable pane state back to idle")
    clear_state.add_argument("--state-file", required=True)
    clear_state.add_argument("--updated-at", type=int, default=None)

    select_actionable = subparsers.add_parser("select-actionable", help="Pick the next actionable pane")
    select_actionable.add_argument("--action", choices=("oldest", "next"), default="oldest")
    select_actionable.add_argument("--current-pane-id", default="")
    select_actionable.add_argument("--tmux-panes", default="")
    select_actionable.add_argument("--state-dir", required=True)

    resolve_actionable = subparsers.add_parser("resolve-actionable-pane", help="Resolve a pane id to actionable target metadata")
    resolve_actionable.add_argument("--pane-id", required=True)
    resolve_actionable.add_argument("--tmux-panes", default="")
    resolve_actionable.add_argument("--state-dir", required=True)

    list_actionable = subparsers.add_parser("list-actionable", help="Render actionable panes")
    list_actionable.add_argument("--mode", choices=("tsv", "picker"), default="tsv")
    list_actionable.add_argument("--tmux-panes", default="")
    list_actionable.add_argument("--state-dir", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "apply-state-update":
        state_file = Path(args.state_file)
        previous_state = load_state_file(state_file)
        payload = update_state_file(
            state_file,
            pane_id=args.pane_id,
            app=args.app,
            status=args.status,
            message=args.message,
            updated_at=args.updated_at,
            session_id=args.session_id,
            window_id=args.window_id,
            pane_title=args.pane_title,
            pane_current_command=args.pane_current_command,
            pane_current_path=args.pane_current_path,
        )
        notification = None
        if payload is not None:
            notification = build_notification_payload(
                previous_state,
                payload,
                notify_statuses=parse_status_list(args.notify_statuses),
            )
        print("written" if payload else "skipped")
        print(json.dumps(notification, separators=(",", ":")) if notification else "")
        return 0

    if args.command == "write-state":
        payload = update_state_file(
            Path(args.state_file),
            pane_id=args.pane_id,
            app=args.app,
            status=args.status,
            message=args.message,
            updated_at=args.updated_at,
            session_id=args.session_id,
            window_id=args.window_id,
            pane_title=args.pane_title,
            pane_current_command=args.pane_current_command,
            pane_current_path=args.pane_current_path,
        )
        print("written" if payload else "skipped")
        return 0

    if args.command == "clear-actionable":
        payload = clear_actionable_state_file(
            Path(args.state_file),
            updated_at=args.updated_at,
        )
        print("cleared" if payload else "unchanged")
        return 0

    if args.command == "select-actionable":
        selection = select_actionable_target(
            action=args.action,
            current_pane_id=args.current_pane_id,
            tmux_panes=args.tmux_panes,
            states_dir=Path(args.state_dir),
        )
        if selection:
            print(selection[0])
            print(selection[1])
            print(selection[2])
        return 0

    if args.command == "resolve-actionable-pane":
        selection = resolve_actionable_pane_target(
            pane_id=args.pane_id,
            tmux_panes=args.tmux_panes,
            states_dir=Path(args.state_dir),
        )
        if selection:
            print(selection[0])
            print(selection[1])
            print(selection[2])
        return 0

    if args.command == "list-actionable":
        candidates = list_actionable_candidates(
            states_dir=Path(args.state_dir),
            tmux_panes=args.tmux_panes,
        )
        for item in candidates:
            status = str(item["status"])
            app = str(item.get("app") or "")
            updated_at = int(item["updated_at"])
            pane_id = str(item["pane_id"])
            session_id = str(item["session_id"])
            session_name = str(item["session_name"])
            window_id = str(item["window_id"])
            window_name = str(item["window_name"])
            pane_path = str(item["path"])
            message = str(item["message"])
            if args.mode == "picker":
                app_prefix = f"{app:<7} " if app else ""
                display = (
                    f"{STATUS_LABELS.get(status, status):<4}  "
                    f"{app_prefix}"
                    f"{session_name}/{window_name}  "
                    f"{short_path(pane_path)}  {age_label(updated_at)}"
                )
                if message:
                    display = f"{display}  {truncate(message)}"
                print(f"{display} ||| {pane_id}")
            else:
                print(
                    "\t".join(
                        [
                            status,
                            str(updated_at),
                            pane_id,
                            session_id,
                            session_name,
                            window_id,
                            window_name,
                            pane_path,
                            message,
                        ]
                    )
                )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
