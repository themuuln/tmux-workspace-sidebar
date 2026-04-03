from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping


ACTIONABLE_STATUSES = frozenset({"done", "needs-input", "error"})
ACTIONABLE_ORDER = {"needs-input": 0, "error": 1, "done": 2}
NOTIFICATION_PRIORITIES = {
    "done": "default",
    "error": "urgent",
    "needs-input": "high",
    "running": "default",
}
NOTIFICATION_TAGS = {
    "done": "white_check_mark",
    "error": "rotating_light",
    "needs-input": "warning",
    "running": "computer",
}
CODEX_SPINNER_FRAMES = (
    "⠋",
    "⠙",
    "⠹",
    "⠸",
    "⠼",
    "⠴",
    "⠦",
    "⠧",
    "⠇",
    "⠏",
    "◌",
    "○",
    "◍",
    "◎",
    "●",
    "◐",
    "◓",
    "◑",
    "◒",
    "◴",
    "◷",
    "◶",
    "◵",
)
CODEX_SPINNER_PREFIXES = set(CODEX_SPINNER_FRAMES)

PaneMatcher = Callable[[str, str], bool]
StatusInferrer = Callable[[str, str, str], str]


def _default_matcher(command: str, title: str) -> bool:
    return bool(command.strip() or title.strip())


def _default_status_inferrer(_command: str, _title: str, _current_status: str) -> str:
    return ""


@dataclass(frozen=True)
class AppProvider:
    name: str
    label: str
    aliases: tuple[str, ...] = ()
    clear_stale_state: bool = False
    actionable_statuses: frozenset[str] = ACTIONABLE_STATUSES
    actionable_order: Mapping[str, int] = field(default_factory=lambda: dict(ACTIONABLE_ORDER))
    notification_titles: Mapping[str, str] = field(default_factory=dict)
    notification_priorities: Mapping[str, str] = field(default_factory=lambda: dict(NOTIFICATION_PRIORITIES))
    notification_tags: Mapping[str, str] = field(default_factory=lambda: dict(NOTIFICATION_TAGS))
    matches_pane: PaneMatcher = _default_matcher
    infer_live_status: StatusInferrer = _default_status_inferrer

    def matches_cli(self, value: str) -> bool:
        normalized = normalize_app_name(value)
        if not normalized:
            return False
        return normalized == self.name or normalized in self.aliases

    def notification_title(self, status: str) -> str:
        return self.notification_titles.get(status, f"{self.label} {status}".strip())

    def notification_priority(self, status: str) -> str:
        return self.notification_priorities.get(status, "default")

    def notification_tag(self, status: str) -> str:
        return self.notification_tags.get(status, "computer")

    def actionable_sort_order(self, status: str) -> int:
        return self.actionable_order.get(status, 99)


def normalize_app_name(value: str) -> str:
    return str(value or "").strip().lower()


def looks_like_codex_spinner_title(title: str) -> bool:
    normalized = title.strip()
    return bool(normalized) and normalized[0] in CODEX_SPINNER_PREFIXES


def _codex_matches_pane(command: str, title: str) -> bool:
    normalized_command = normalize_app_name(command)
    return normalized_command in {"codex", "script"} or looks_like_codex_spinner_title(title)


def _codex_live_status(command: str, title: str, current_status: str) -> str:
    if looks_like_codex_spinner_title(title):
        return "running"
    if normalize_app_name(command) in {"codex", "script"} and current_status in {"", "running"}:
        return "running"
    return ""


def _flutter_matches_pane(command: str, title: str) -> bool:
    normalized_command = normalize_app_name(command)
    normalized_title = normalize_app_name(title)
    if normalized_command == "flutter":
        return True
    return normalized_title.startswith("flutter ") or normalized_title.startswith("flutter:")


def _flutter_live_status(command: str, title: str, _current_status: str) -> str:
    if _flutter_matches_pane(command, title):
        return "running"
    return ""


PROVIDERS: dict[str, AppProvider] = {
    "codex": AppProvider(
        name="codex",
        label="Codex",
        aliases=("script",),
        clear_stale_state=True,
        notification_titles={
            "done": "Codex finished",
            "error": "Codex error",
            "needs-input": "Codex needs input",
            "running": "Codex working",
        },
        matches_pane=_codex_matches_pane,
        infer_live_status=_codex_live_status,
    ),
    "flutter": AppProvider(
        name="flutter",
        label="Flutter",
        notification_titles={
            "done": "Flutter finished",
            "error": "Flutter error",
            "needs-input": "Flutter needs input",
            "running": "Flutter working",
        },
        matches_pane=_flutter_matches_pane,
        infer_live_status=_flutter_live_status,
    ),
}

APP_LABELS = {name: provider.label.lower() for name, provider in PROVIDERS.items()}


def provider_for(app: str) -> AppProvider | None:
    normalized = normalize_app_name(app)
    if not normalized:
        return None
    if normalized in PROVIDERS:
        return PROVIDERS[normalized]
    for provider in PROVIDERS.values():
        if normalized in provider.aliases:
            return provider
    return None


def label_for_cli_value(value: str) -> str:
    normalized = normalize_app_name(value)
    provider = provider_for(normalized)
    if provider is None:
        return normalized
    return provider.label.lower()


def actionable_statuses_for_app(app: str) -> frozenset[str]:
    provider = provider_for(app)
    if provider is None:
        return frozenset()
    return provider.actionable_statuses


def actionable_sort_order_for_app(app: str, status: str) -> int:
    provider = provider_for(app)
    if provider is None:
        return ACTIONABLE_ORDER.get(status, 99)
    return provider.actionable_sort_order(status)


def notification_title_for_app(app: str, status: str) -> str:
    provider = provider_for(app)
    if provider is None:
        label = normalize_app_name(app) or "Pane"
        return f"{label.title()} {status}".strip()
    return provider.notification_title(status)


def notification_priority_for_app(app: str, status: str) -> str:
    provider = provider_for(app)
    if provider is None:
        return NOTIFICATION_PRIORITIES.get(status, "default")
    return provider.notification_priority(status)


def notification_tag_for_app(app: str, status: str) -> str:
    provider = provider_for(app)
    if provider is None:
        return NOTIFICATION_TAGS.get(status, "computer")
    return provider.notification_tag(status)


def should_clear_stale_state(app: str, command: str, title: str) -> bool:
    provider = provider_for(app)
    if provider is None or not provider.clear_stale_state:
        return False
    return not provider.matches_pane(command, title)


def infer_live_pane_state(command: str, title: str, current_app: str, current_status: str) -> tuple[str, str]:
    if current_app:
        provider = provider_for(current_app)
        if provider is not None:
            status = provider.infer_live_status(command, title, current_status)
            if status:
                return provider.name, status

    for provider in PROVIDERS.values():
        if provider.matches_pane(command, title):
            status = provider.infer_live_status(command, title, current_status)
            return provider.name, status

    return "", ""
