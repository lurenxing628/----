"""已保存模拟方案（ScheduleAdjustmentScenario）的读模型。

写入方（甘特调整 Draft / Scenario / Validation 服务与草稿仓储）已于 2026-09-20 随旧路由层退役；
工作台计划目录、计划页与查询仍从 ScheduleAdjustmentScenario 表读取历史方案，所以只保留方案头模型。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int

SCENARIO_STATUS_ACTIVE = "active"
SCENARIO_STATUS_DISCARDED = "discarded"
SCENARIO_STATUS_PUBLISHED = "published"
SCENARIO_STATUS_EXPIRED = "expired"

VALID_SCENARIO_STATUSES = (
    SCENARIO_STATUS_ACTIVE,
    SCENARIO_STATUS_DISCARDED,
    SCENARIO_STATUS_PUBLISHED,
    SCENARIO_STATUS_EXPIRED,
)


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


@dataclass
class ScheduleAdjustmentScenario:
    scenario_id: str
    source_draft_id: str
    base_version: int
    base_plan_role: str
    base_source_table: str
    validation_status: str
    base_candidate_id: Optional[int] = None
    base_candidate_key: Optional[str] = None
    scenario_name: Optional[str] = None
    status: str = SCENARIO_STATUS_ACTIVE
    issue_count: int = 0
    issues_json: Optional[str] = None
    row_count: int = 0
    execution_snapshot_revision: Optional[str] = None
    execution_snapshot_op_ids: Optional[str] = None
    execution_snapshot_op_count: int = 0
    created_by: Optional[str] = None
    published_version: Optional[int] = None
    published_by: Optional[str] = None
    published_reason: Optional[str] = None
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleAdjustmentScenario:
        return cls(
            scenario_id=str(get(row, "scenario_id") or ""),
            source_draft_id=str(get(row, "source_draft_id") or ""),
            base_version=parse_int(get(row, "base_version"), default=0) or 0,
            base_plan_role=str(get(row, "base_plan_role") or ""),
            base_source_table=str(get(row, "base_source_table") or ""),
            base_candidate_id=parse_int(get(row, "base_candidate_id"), default=None),
            base_candidate_key=_text_or_none(get(row, "base_candidate_key")),
            scenario_name=_text_or_none(get(row, "scenario_name")),
            status=str(get(row, "status") or SCENARIO_STATUS_ACTIVE),
            validation_status=str(get(row, "validation_status") or ""),
            issue_count=parse_int(get(row, "issue_count"), default=0) or 0,
            issues_json=_text_or_none(get(row, "issues_json")),
            row_count=parse_int(get(row, "row_count"), default=0) or 0,
            execution_snapshot_revision=_text_or_none(get(row, "execution_snapshot_revision")),
            execution_snapshot_op_ids=_text_or_none(get(row, "execution_snapshot_op_ids")),
            execution_snapshot_op_count=parse_int(get(row, "execution_snapshot_op_count"), default=0) or 0,
            created_by=_text_or_none(get(row, "created_by")),
            published_version=parse_int(get(row, "published_version"), default=None),
            published_by=_text_or_none(get(row, "published_by")),
            published_reason=_text_or_none(get(row, "published_reason")),
            published_at=_text_or_none(get(row, "published_at")),
            created_at=_text_or_none(get(row, "created_at")),
            updated_at=_text_or_none(get(row, "updated_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)
