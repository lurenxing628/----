"""Read-only calibration contracts; lineage is evidence, never a join heuristic."""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_execution_input import public_ref

METHOD_VERSION = "d05-median-effective-hours-v1"
MIN_SAMPLES = 5
MAX_SAMPLES = 20
MAX_TEMPLATES = 10000
MAX_OPERATIONS = 10000
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_EXPORT_BYTES = 16 * 1024 * 1024


def issue(code, message):
    return {"code": code, "message": message}


def closed_capabilities():
    return {"view": True, "export": True, "adopt": False, "lock": False}


def write_blockers():
    return [issue("adoption_schema_unavailable", "采纳来源、人员、时间、原因及锁定写保护尚未完整接入，不能采用或锁定。")]


@dataclass(frozen=True)
class CalibrationQuery:
    query: str = ""
    part_ref: Optional[str] = None
    source: Optional[str] = None
    status: str = "all"
    deviation: str = "all"
    number: int = 1
    size: int = 20
    sort: str = "part_no"
    direction: str = "asc"

    def __post_init__(self):
        if type(self.query) is not str or len(self.query) > 200 or "\x00" in self.query:
            raise WorkbenchCommandRejected("invalid_input", "搜索内容最多200字，不能含空字符。", 400)
        object.__setattr__(self, "query", self.query.strip())
        if self.part_ref is not None:
            public_ref(self.part_ref)
        if self.source not in (None, "internal", "external", "unknown"):
            raise WorkbenchCommandRejected("invalid_input", "工序来源筛选无效。", 400)
        if self.status not in ("all", "suggested", "insufficient_data") or self.deviation not in ("all", "over_20_percent"):
            raise WorkbenchCommandRejected("invalid_input", "建议状态或偏差筛选无效。", 400)
        if type(self.number) is not int or not 1 <= self.number <= 1000000 or type(self.size) is not int or not 1 <= self.size <= 200:
            raise WorkbenchCommandRejected("invalid_input", "页码须为1至1000000，每页须为1至200条。", 400)
        if self.sort not in ("part_no", "operation_label", "old_unit_hours", "suggested_unit_hours", "sample_count", "absolute_deviation_percent") or self.direction not in ("asc", "desc"):
            raise WorkbenchCommandRejected("invalid_input", "排序列或排序方向无效。", 400)

    def scope(self):
        return {"kind": "calibration", "method_version": METHOD_VERSION,
                **{key: value for key, value in asdict(self).items() if key != "number"}}


@dataclass(frozen=True)
class CalibrationTemplate:
    operation_ref: str
    revision: int
    part_ref: str
    part_no: str
    part_name: str
    sequence: int
    operation_label: str
    source: Optional[str]
    old_unit_hours: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationLineage:
    """Internal verified origin contract. Current storage supplies no such fact."""

    template_operation_ref: str
    template_revision: int
    evidence_ref: str


@dataclass(frozen=True)
class CalibrationCandidate:
    execution: ExecutionProjection
    part_no: str
    batch_code: str
    operation_code: str
    operation_source: Optional[str]
    lineage: Optional[CalibrationLineage] = None
