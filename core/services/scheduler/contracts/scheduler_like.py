"""排产器最小协议：优化器各步骤只依赖"能被调用 schedule"这一点，不依赖具体调度器类。"""

from __future__ import annotations

from typing import Any, Protocol


class SchedulerLike(Protocol):
    def schedule(self, *args: Any, **kwargs: Any) -> Any:
        ...
