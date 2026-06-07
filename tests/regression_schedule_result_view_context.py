"""回归测试：resolve_schedule_result_view_context 的方案角色解析契约——空 plan_role 默认 ROLE_ADOPTED；显式 baseline_best/critical_best 命中候选行(SOURCE_CANDIDATE_ROWS)时标记为对比方案；缺失时回退采用方案并给可见提示；非法角色抛 plan_role 字段的 ValidationError、缺历史在需要时先抛 version NOT_FOUND；并校验 attach_plan_metadata 与 plan_role_filter_fields 输出一致、serialize_plan_role_options 保留候选诊断字段。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SchedulePlanResolution,
    SchedulePlanRoleOption,
)
from core.services.scheduler.schedule_result_view_context import (
    attach_plan_metadata,
    default_plan_resolution_dict,
    plan_role_filter_fields,
    resolve_schedule_result_view_context,
    serialize_plan_role_options,
)
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

VERSION = 7


def _option(
    role: str,
    *,
    source_table: str = SOURCE_SCHEDULE,
    candidate_id: Optional[int] = None,
    candidate_key: Optional[str] = None,
) -> SchedulePlanRoleOption:
    return SchedulePlanRoleOption(
        role=role,
        source_table=source_table,
        candidate_id=candidate_id,
        candidate_key=candidate_key,
        candidate_label=role,
        candidate_kind=None,
        candidate_status="completed",
        detail_saved="yes" if source_table == SOURCE_CANDIDATE_ROWS else None,
    )


class FakePlanQueryService:
    def __init__(self, roles: List[SchedulePlanRoleOption]):
        self.roles = roles

    def resolve_plan(self, version: int, role: Optional[str]) -> SchedulePlanResolution:
        requested_role = str(role or "").strip() or ROLE_ADOPTED
        if requested_role not in {ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST}:
            raise ValueError(f"未知的排产方案角色：{requested_role}")
        roles_by_name = {item.role: item for item in self.roles}
        if requested_role in roles_by_name:
            selected = roles_by_name[requested_role]
            return SchedulePlanResolution(
                version=int(version),
                requested_role=requested_role,
                selected_role=selected.role,
                source_table=selected.source_table,
                candidate_id=selected.candidate_id,
                candidate_key=selected.candidate_key,
                status="resolved_adopted" if requested_role == ROLE_ADOPTED else "resolved_comparison",
                message="",
                available_roles=self.roles,
            )
        adopted = roles_by_name[ROLE_ADOPTED]
        return SchedulePlanResolution(
            version=int(version),
            requested_role=requested_role,
            selected_role=ROLE_ADOPTED,
            source_table=adopted.source_table,
            candidate_id=adopted.candidate_id,
            candidate_key=adopted.candidate_key,
            status="fallback_to_adopted",
            message="当前版本没有保存这套方案明细，已显示正式采用方案。",
            available_roles=self.roles,
        )


def _resolve(raw_plan_role: Optional[str], *, latest_version: int = VERSION, roles=None):
    plan_query_service = FakePlanQueryService(roles or [_option(ROLE_ADOPTED)])
    return resolve_schedule_result_view_context(
        raw_version=None,
        raw_plan_role=raw_plan_role,
        latest_version=latest_version,
        version_exists=lambda version: int(version) == VERSION,
        plan_query_service=plan_query_service,
    )


def test_context_defaults_empty_plan_role_to_adopted() -> None:
    context = _resolve(None)

    assert context.requested_role == ROLE_ADOPTED
    assert context.selected_role == ROLE_ADOPTED
    assert context.plan_resolution["status"] == "resolved_adopted"


def test_context_keeps_explicit_adopted() -> None:
    context = _resolve(ROLE_ADOPTED)

    assert context.requested_role == ROLE_ADOPTED
    assert context.selected_role == ROLE_ADOPTED
    assert context.source_table == SOURCE_SCHEDULE


def test_context_selects_existing_baseline_candidate_rows() -> None:
    context = _resolve(
        ROLE_BASELINE_BEST,
        roles=[
            _option(ROLE_ADOPTED),
            _option(
                ROLE_BASELINE_BEST,
                source_table=SOURCE_CANDIDATE_ROWS,
                candidate_id=101,
                candidate_key="baseline_best",
            ),
        ],
    )

    assert context.requested_role == ROLE_BASELINE_BEST
    assert context.selected_role == ROLE_BASELINE_BEST
    assert context.source_table == SOURCE_CANDIDATE_ROWS
    assert context.candidate_id == 101
    assert context.is_comparison is True


def test_context_selects_existing_critical_candidate_rows() -> None:
    context = _resolve(
        ROLE_CRITICAL_BEST,
        roles=[
            _option(ROLE_ADOPTED),
            _option(
                ROLE_CRITICAL_BEST,
                source_table=SOURCE_CANDIDATE_ROWS,
                candidate_id=202,
                candidate_key="graph_w1_of_5",
            ),
        ],
    )

    assert context.requested_role == ROLE_CRITICAL_BEST
    assert context.selected_role == ROLE_CRITICAL_BEST
    assert context.source_table == SOURCE_CANDIDATE_ROWS
    assert context.candidate_key == "graph_w1_of_5"
    assert context.is_comparison is True


def test_context_falls_back_to_adopted_when_requested_role_is_missing() -> None:
    context = _resolve(ROLE_BASELINE_BEST)

    assert context.requested_role == ROLE_BASELINE_BEST
    assert context.selected_role == ROLE_ADOPTED
    assert context.plan_resolution["status"] == "fallback_to_adopted"
    assert context.is_fallback is True
    assert context.is_comparison is True


def test_context_marks_non_adopted_schedule_source_as_comparison() -> None:
    context = _resolve(
        ROLE_BASELINE_BEST,
        roles=[
            _option(ROLE_ADOPTED),
            _option(
                ROLE_BASELINE_BEST,
                source_table=SOURCE_SCHEDULE,
                candidate_id=101,
                candidate_key="baseline_best",
            ),
        ],
    )
    fields = plan_role_filter_fields(context)

    assert context.requested_role == ROLE_BASELINE_BEST
    assert context.selected_role == ROLE_BASELINE_BEST
    assert context.source_table == SOURCE_SCHEDULE
    assert context.is_comparison is True
    assert fields["is_comparison"] is True


def test_context_rejects_bad_plan_role_with_plan_role_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _resolve("bad")

    assert exc_info.value.details.get("field") == "plan_role"


def test_context_no_history_uses_default_adopted_with_visible_fallback() -> None:
    context = _resolve(ROLE_CRITICAL_BEST, latest_version=0)

    assert context.has_history is False
    assert context.selected_version is None
    assert context.requested_role == ROLE_CRITICAL_BEST
    assert context.selected_role == ROLE_ADOPTED
    assert context.is_fallback is True
    assert context.is_comparison is True


def test_plan_metadata_and_resource_dispatch_filter_fields_stay_consistent() -> None:
    context = _resolve(
        ROLE_BASELINE_BEST,
        roles=[
            _option(ROLE_ADOPTED),
            _option(
                ROLE_BASELINE_BEST,
                source_table=SOURCE_CANDIDATE_ROWS,
                candidate_id=101,
                candidate_key="baseline_best",
            ),
        ],
    )
    plan_resolution: Dict[str, Any] = context.plan_resolution
    data: Dict[str, Any] = {}

    attach_plan_metadata(data, plan_resolution)
    fields = plan_role_filter_fields(plan_resolution)

    assert data["requested_plan_role"] == fields["requested_plan_role"]
    assert data["effective_plan_role"] == fields["effective_plan_role"]
    assert data["plan_role_status"] == fields["plan_role_status"]
    assert data["plan_role_message"] == fields["plan_role_message"]
    assert data["is_comparison_plan"] == fields["is_comparison"]
    assert fields["candidate_id"] == 101
    assert fields["candidate_key"] == "baseline_best"
    assert fields["source_table"] == SOURCE_CANDIDATE_ROWS
    assert fields["plan_role_label"] == data["effective_plan_role_label"]
    assert fields["requested_plan_role_label"] == data["requested_plan_role_label"]
    assert fields["effective_plan_role_label"] == data["effective_plan_role_label"]


def test_serialize_plan_role_options_keeps_existing_dict_items() -> None:
    options = [
        {
            "role": ROLE_BASELINE_BEST,
            "label": "原算法代表方案",
            "source_table": SOURCE_CANDIDATE_ROWS,
            "candidate_id": 101,
            "candidate_key": "baseline_best",
            "candidate_label": "原算法方案",
            "candidate_kind": "baseline",
            "candidate_status": "completed",
            "detail_saved": "yes",
            "is_comparison": True,
        }
    ]

    assert serialize_plan_role_options(options) == options


def test_serialize_plan_role_options_keeps_candidate_diagnostics_from_plain_objects() -> None:
    option = SimpleNamespace(
        role=ROLE_BASELINE_BEST,
        source_table=SOURCE_CANDIDATE_ROWS,
        candidate_id=101,
        selection_candidate_id=303,
        resolved_candidate_id=101,
        candidate_key="baseline_best",
        candidate_label="原算法方案",
        candidate_kind="baseline",
        candidate_status="completed",
        detail_saved="yes",
        candidate_missing=True,
    )

    [serialized] = serialize_plan_role_options([option])

    assert serialized["selection_candidate_id"] == 303
    assert serialized["resolved_candidate_id"] == 101
    assert serialized["candidate_missing"] is True


def test_missing_history_can_fail_before_plan_role_validation_when_required() -> None:
    with pytest.raises(BusinessError) as exc_info:
        resolve_schedule_result_view_context(
            raw_version=999,
            raw_plan_role="bad",
            latest_version=VERSION,
            version_exists=lambda _version: False,
            plan_query_service=FakePlanQueryService([_option(ROLE_ADOPTED)]),
            require_existing_version=True,
        )

    assert exc_info.value.code == ErrorCode.NOT_FOUND
    assert (exc_info.value.details or {}).get("field") == "version"
    assert (exc_info.value.details or {}).get("status") == "missing_history"


def test_gantt_plan_query_wrapper_keeps_legacy_bad_role_message() -> None:
    from core.services.scheduler import gantt_plan_query

    with pytest.raises(ValidationError) as exc_info:
        gantt_plan_query.default_plan_resolution_dict("bad")

    assert "未知的排产方案角色：bad" in exc_info.value.message
    assert exc_info.value.field == "plan_role"
