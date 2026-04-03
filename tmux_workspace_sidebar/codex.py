from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


DONE_EVENTS = {
    "agent-turn-complete",
    "complete",
    "completed",
    "done",
    "finish",
    "finished",
    "session-end",
    "stop",
    "stopped",
    "task-complete",
    "turn-complete",
}
DONE_STATUSES = {
    "complete",
    "completed",
    "done",
    "finished",
    "stopped",
}
IDLE_EVENTS = {"session-start"}
RUNNING_EVENTS = {
    "agent-turn-start",
    "agent-turn-started",
    "agent-turn-progress",
    "agent-turn-running",
    "in-progress",
    "progress",
    "running",
    "start",
    "started",
    "task-start",
    "task-started",
    "turn-start",
    "turn-started",
    "user-prompt-submit",
    "working",
}
RUNNING_STATUSES = {
    "busy",
    "executing",
    "in-progress",
    "inprogress",
    "running",
    "started",
    "working",
}
RUNNING_TOKENS = ("start", "run", "progress", "working", "execut")
DONE_TOKENS = ("complete", "done", "finish", "stop")
ERROR_TOKENS = ("error", "fail")


def looks_like_json(value: str) -> bool:
    return value.startswith("{") or value.startswith("[")


def load_payload(raw_payload: str, *, codex_event: str = "", codex_status: str = "", codex_message: str = "") -> dict[str, Any]:
    payload = raw_payload.strip()
    if not payload:
        payload = json.dumps(
            {
                "event": codex_event,
                "status": codex_status,
                "message": codex_message,
            },
            separators=(",", ":"),
        )
    try:
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def normalize(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", text)
    text = text.lower()
    return re.sub(r"[\s._/]+", "-", text)


def infer_status_and_message(
    *,
    hook_event: str = "",
    hook_payload: str = "",
    codex_event: str = "",
    codex_status: str = "",
    codex_message: str = "",
) -> tuple[str, str]:
    data = load_payload(
        hook_payload,
        codex_event=codex_event,
        codex_status=codex_status,
        codex_message=codex_message,
    )

    raw_event = normalize(
        hook_event
        or data.get("hook_event_name")
        or data.get("event")
        or data.get("type")
        or data.get("notification_type")
        or data.get("name")
        or codex_event
        or ""
    )
    notif_type = normalize(data.get("notification_type") or "")
    status_hint = normalize(
        data.get("status")
        or data.get("state")
        or data.get("phase")
        or codex_status
        or ""
    )
    message = str(
        data.get("summary")
        or data.get("transcript_summary")
        or data.get("last_assistant_message")
        or data.get("last-assistant-message")
        or data.get("last_agent_message")
        or data.get("message")
        or data.get("title")
        or data.get("prompt")
        or codex_message
        or ""
    ).strip()

    if raw_event in DONE_EVENTS or status_hint in DONE_STATUSES:
        status = "done"
    elif raw_event in IDLE_EVENTS:
        status = "idle"
    elif raw_event in RUNNING_EVENTS:
        status = "running"
    elif (
        raw_event.startswith("permission")
        or raw_event.startswith("approve")
        or raw_event
        in (
            "approval-requested",
            "approval-needed",
            "blocked",
            "input-required",
            "request-permissions",
            "request-user-input",
            "user-input-requested",
        )
        or notif_type == "permission_prompt"
    ):
        status = "needs-input"
    elif raw_event.startswith("error") or raw_event.startswith("fail"):
        status = "error"
    elif notif_type == "idle_prompt" or raw_event == "idle-prompt":
        status = "idle"
    elif status_hint in RUNNING_STATUSES:
        status = "running"
    elif status_hint in {"idle", "ready"}:
        status = "idle"
    elif status_hint in {"error", "failed"}:
        status = "error"
    elif raw_event and any(token in raw_event for token in RUNNING_TOKENS):
        status = "running"
    elif raw_event and any(token in raw_event for token in DONE_TOKENS):
        status = "done"
    elif raw_event and any(token in raw_event for token in ERROR_TOKENS):
        status = "error"
    else:
        status = ""

    return status, message


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex hook helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_hook = subparsers.add_parser("parse-hook", help="Infer sidebar state from a Codex hook payload")
    parse_hook.add_argument("--hook-event", default="")
    parse_hook.add_argument("--hook-payload", default="")
    parse_hook.add_argument("--codex-event", default="")
    parse_hook.add_argument("--codex-status", default="")
    parse_hook.add_argument("--codex-message", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "parse-hook":
        status, message = infer_status_and_message(
            hook_event=args.hook_event,
            hook_payload=args.hook_payload,
            codex_event=args.codex_event,
            codex_status=args.codex_status,
            codex_message=args.codex_message,
        )
        print(status)
        print(message)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
