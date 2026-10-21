"""The common cooperative unit of scheduling search."""
from __future__ import annotations

from typing import Optional


class SearchStage:
    """A strategy whose work can pause at an actual action boundary."""

    name = ""

    def available(self) -> bool:
        raise NotImplementedError

    def run_task(self) -> int:
        """Run one task and return its nonnegative strict improvement event count."""
        raise NotImplementedError

    def unavailable_reason(self) -> Optional[str]:
        """Explain why this stage cannot currently start; None means it can start."""
        raise NotImplementedError

    def finish(self) -> None:
        """Publish the report at search completion, including a stage that never ran."""
        raise NotImplementedError


__all__ = ["SearchStage"]
