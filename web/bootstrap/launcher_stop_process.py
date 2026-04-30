from __future__ import annotations

from typing import Callable, Optional


def runtime_process_inactive(pid: int, pid_match_hint: Optional[bool], *, pid_state_func: Callable[[int], Optional[bool]]) -> bool:
    pid_text = str(pid or "").strip()
    if not pid_text:
        return True
    pid_digits = pid_text[1:] if pid_text.startswith("-") else pid_text
    if not pid_digits.isdigit():
        return True
    pid_i = int(pid_text)
    if pid_i <= 0 or pid_match_hint is False:
        return True
    pid_state = pid_state_func(pid_i)
    if pid_state is None:
        return False
    if not pid_state:
        return True
    return False
