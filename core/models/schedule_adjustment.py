"""已保存模拟方案（ScheduleAdjustmentScenario）的读模型。

写入方（甘特调整 Draft / Scenario / Validation 服务与草稿仓储）已于 2026-09-20 随旧路由层退役；
工作台计划目录、计划页与查询仍从 ScheduleAdjustmentScenario 表读取历史方案，所以只保留方案头模型。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ._helpers import RowLike, parse_int, parse_optional_int

SCENARIO_STATUS_ACTIVE = "active"


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
    published_version: Optional[int] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleAdjustmentScenario:
        return cls(
            scenario_id=str(row["scenario_id"] or ""),
            source_draft_id=str(row["source_draft_id"]),
            base_version=parse_int(row["base_version"], field="base_version"),
            base_plan_role=str(row["base_plan_role"]),
            base_source_table=str(row["base_source_table"]),
            base_candidate_id=parse_optional_int(row["base_candidate_id"], field="base_candidate_id"),
            base_candidate_key=_text_or_none(row["base_candidate_key"]),
            scenario_name=_text_or_none(row["scenario_name"]),
            status=str(row["status"] or SCENARIO_STATUS_ACTIVE),
            validation_status=str(row["validation_status"]),
            issue_count=parse_int(row["issue_count"], field="issue_count"),
            issues_json=_text_or_none(row["issues_json"]),
            row_count=parse_int(row["row_count"], field="row_count"),
            published_version=parse_optional_int(row["published_version"], field="published_version"),
        )
