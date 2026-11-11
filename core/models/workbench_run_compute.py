"""Internal candidate computation artifacts, never a persisted RunResult.

模型层声明计算与持久化结果所需的结构性契约（Protocol）与具名结果数据类：
服务层的 PreparedBusinessInput 满足该协议。
"""

from dataclasses import dataclass
from typing import Any, Collection, Dict, List, Protocol


class _FrozenSeeds(Protocol):
    @property
    def frozen_op_ids(self) -> Collection[int]: ...


class FrozenScopeInput(Protocol):
    """持久化候选任务和分析依据所需的冻结范围、运行工时事实。"""

    @property
    def seeds(self) -> _FrozenSeeds: ...

    @property
    def operation_efforts(self) -> Collection[Any]: ...


@dataclass(frozen=True)
class CandidateRunComputation:
    schedule_input: FrozenScopeInput
    candidate_comparison: Any
    result_summary_obj: Dict[str, Any]
    candidate_outcomes: Dict[str, Any]
    dispositions: List[Dict[str, Any]]
    state: str


@dataclass(frozen=True)
class PreparedRunResult:
    """The computation's identities, serializable result and immutable read models."""

    candidates: List[Dict[str, Any]]
    result: Dict[str, Any]
    read_models: Dict[str, Any]
    status_header: Dict[str, Any]
    # Only the source revisions and schema recorded at capture, for the persist-time recheck; not the archive.
    recorded_source: Dict[str, Any]


class CandidateRunInputError(ValueError):
    def __init__(self, reason: str, message: str, *, issues):
        super().__init__(message)
        self.code = reason
        self.reason = reason
        self.issues = list(issues)
