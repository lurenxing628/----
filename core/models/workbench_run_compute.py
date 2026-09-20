"""Internal candidate computation artifacts, never a persisted RunResult.

模型层只声明它对上游产物的结构性要求（Protocol），不反向引用服务层类型：
服务层的 CandidateRunInput / ScheduleOrchestrationOutcome 以结构满足这两个协议。
"""

from dataclasses import dataclass, field
from typing import Any, Collection, Dict, List, Protocol


class FrozenScopeInput(Protocol):
    """排产输入里持久化候选任务时唯一需要读的事实：冻结工序集合。"""

    @property
    def frozen_op_ids(self) -> Collection[int]: ...


class OrchestrationOutcome(Protocol):
    """编排产物里持久化候选集时需要读的事实：候选对比与结果摘要。"""

    @property
    def candidate_comparison(self) -> Any: ...

    @property
    def result_summary_obj(self) -> Any: ...


@dataclass(frozen=True)
class CandidateRunComputation:
    schedule_input: FrozenScopeInput
    orchestration: OrchestrationOutcome
    candidate_payloads: Dict[str, Any]
    dispositions: List[Dict[str, Any]]
    state: str
    result_persisted: bool = field(default=False, init=False)


class CandidateRunInputError(ValueError):
    def __init__(self, reason: str, message: str, *, issues=None):
        super().__init__(message)
        self.code = reason
        self.reason = reason
        self.issues = list(issues or [])
        self.can_adopt = False
        self.result_persisted = False
