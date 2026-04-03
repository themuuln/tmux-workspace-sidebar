from __future__ import annotations

import argparse
import re
import sys


IDLE_PATTERNS = (
    "flutter run key commands.",
    "a dart vm service on",
    "the flutter devtools debugger and profiler on",
    "to hot restart changes while running",
    "reloaded ",
    "hot reload performed",
    "restarted application",
)
RUNNING_PATTERNS = (
    "launching ",
    "running gradle task",
    "syncing files to device",
    "performing hot reload",
    "performing hot restart",
    "waiting for connection from debug service",
    "downloading ",
    "resolving dependencies",
    "building ",
)
ERROR_PATTERNS = (
    "[error:flutter",
    "unhandled exception:",
    "gradle task",
    "failed",
    "exception:",
)
INPUT_PATTERNS = (
    "please choose one",
    "which device",
    "multiple devices found",
)


def normalize_task(task: str) -> str:
    value = " ".join(str(task or "").split())
    return value or "command"


def compact_message(message: str) -> str:
    return " ".join(str(message or "").split()).strip()


def default_message(task: str, status: str) -> str:
    normalized_task = normalize_task(task)
    if status == "running":
        return f"flutter {normalized_task}"
    if status == "done":
        return f"flutter {normalized_task} finished"
    if status == "error":
        return f"flutter {normalized_task} failed"
    if status == "needs-input":
        return f"flutter {normalized_task} needs input"
    if status == "idle":
        return f"flutter {normalized_task} ready"
    return ""


def infer_status_and_message(*, line: str = "", event: str = "", task: str = "") -> tuple[str, str]:
    normalized_line = compact_message(line)
    lowered = normalized_line.lower()
    normalized_event = event.strip().lower().replace("_", "-")

    if normalized_event == "start":
        return "running", default_message(task, "running")
    if normalized_event in {"done", "complete", "completed"}:
        return "done", default_message(task, "done")
    if normalized_event in {"error", "failed", "fail"}:
        return "error", default_message(task, "error")

    if not normalized_line:
        return "", ""

    if any(pattern in lowered for pattern in INPUT_PATTERNS):
        return "needs-input", normalized_line
    if any(pattern in lowered for pattern in IDLE_PATTERNS):
        return "idle", normalized_line
    if any(pattern in lowered for pattern in RUNNING_PATTERNS):
        return "running", normalized_line
    if any(pattern in lowered for pattern in ERROR_PATTERNS):
        if "gradle task" in lowered and "failed" not in lowered:
            return "running", normalized_line
        return "error", normalized_line
    if re.search(r"\bno issues found\b", lowered):
        return "done", normalized_line
    if re.search(r"\ball tests passed\b", lowered):
        return "done", normalized_line

    return "", ""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Flutter status helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_line = subparsers.add_parser("parse-line", help="Infer sidebar state from a Flutter log line")
    parse_line.add_argument("--line", default="")
    parse_line.add_argument("--event", default="")
    parse_line.add_argument("--task", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "parse-line":
        status, message = infer_status_and_message(
            line=args.line,
            event=args.event,
            task=args.task,
        )
        print(status)
        print(message)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
