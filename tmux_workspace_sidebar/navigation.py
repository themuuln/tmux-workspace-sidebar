from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple


WindowTarget = Tuple[str, str]


def flatten_window_targets(
    session_order: Sequence[str],
    window_rows: Iterable[Tuple[str, str, int]],
) -> List[WindowTarget]:
    windows_by_session: dict[str, list[Tuple[int, str]]] = {session_id: [] for session_id in session_order}

    for session_id, window_id, window_index in window_rows:
        windows_by_session.setdefault(session_id, []).append((window_index, window_id))

    ordered_targets: List[WindowTarget] = []
    for session_id in session_order:
        windows = sorted(windows_by_session.get(session_id, []), key=lambda item: item[0])
        ordered_targets.extend((session_id, window_id) for _, window_id in windows)

    return ordered_targets


def select_wrapped_window_target(
    window_targets: Sequence[WindowTarget],
    current_session_id: str,
    current_window_id: str,
    step: int,
) -> Optional[WindowTarget]:
    if not window_targets or step == 0:
        return None

    current_target = (current_session_id, current_window_id)
    if current_target not in window_targets:
        return window_targets[0 if step > 0 else -1]

    current_index = window_targets.index(current_target)
    target_index = (current_index + step) % len(window_targets)
    return window_targets[target_index]
