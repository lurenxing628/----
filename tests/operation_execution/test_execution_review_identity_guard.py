"""回归测试：守护 /reports/execution-review 现场复盘只对「正式采用方案」开放——baseline_best/未知 plan_role/模拟预览 scenario 等非正式身份会被可见拦截且禁用导出（含 /export 返回 400），不泄露原始 role；历史正式版本只读可见，资源过滤导出仍保留正式行。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.models.execution_review_identity import can_read_execution_review
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.report.execution_review import ExecutionReviewMixin


class _ReviewResolution:
    def __init__(self, *, status: str = "success", detail_saved=True) -> None:
        self.status = status
        self.detail_saved = detail_saved

    def to_dict(self):
        return {
            "source_table": SOURCE_SCHEDULE,
            "selected_role": ROLE_ADOPTED,
            "plan_identity": {
                "user_label": "正式采用方案",
                "is_official": True,
                "is_preview": False,
                "is_simulation": False,
                "result_summary_parse_failed": False,
                "schedule_result_status": self.status,
                "detail_saved": self.detail_saved,
            },
        }


class _NoFeedbackService:
    def get_execution_state_for_scopes(self, scopes):
        return {}


class _ReviewHost(ExecutionReviewMixin):
    def __init__(self, resolution: _ReviewResolution = None) -> None:
        self.calls = []
        self.execution_feedback_service = _NoFeedbackService()
        self.resolution = resolution or _ReviewResolution()

    def _resolve_plan(self, version, plan_role, scenario_id=None):
        self.calls.append(("resolve", version, plan_role, scenario_id))
        return self.resolution

    def _list_plan_rows_between(self, **kwargs):
        self.calls.append(("between", kwargs))
        return []

    def _list_plan_rows_all(self, **kwargs):
        self.calls.append(("all", kwargs))
        return []


def test_execution_review_identity_guard_parses_string_booleans() -> None:
    base = {
        "source_table": "schedule",
        "selected_role": ROLE_ADOPTED,
        "plan_identity": {
            "is_official": "yes",
            "is_preview": "no",
            "is_simulation": "no",
            "result_summary_parse_failed": "no",
            "schedule_result_status": "success",
            "detail_saved": "yes",
        },
    }

    assert can_read_execution_review(base) is True

    blocked = dict(base, plan_identity=dict(base["plan_identity"], result_summary_parse_failed="yes"))
    assert can_read_execution_review(blocked) is False


def test_execution_review_service_hard_pins_adopted_null_scope() -> None:
    host = _ReviewHost()

    host.execution_review(
        12,
        date_from="2026-05-06",
        date_to="2026-05-06",
        resource_type="machine",
        resource_id="M-RPT",
    )
    host.execution_review(12)

    assert host.calls[0] == ("resolve", 12, ROLE_ADOPTED, None)
    assert host.calls[1][0] == "between"
    assert host.calls[1][1]["plan_role"] == ROLE_ADOPTED
    assert host.calls[1][1]["scenario_id"] is None
    assert host.calls[2] == ("resolve", 12, ROLE_ADOPTED, None)
    assert host.calls[3][0] == "all"
    assert host.calls[3][1]["plan_role"] == ROLE_ADOPTED
    assert host.calls[3][1]["scenario_id"] is None


def test_execution_review_service_blocks_partial_before_reading_plan_rows() -> None:
    host = _ReviewHost(_ReviewResolution(status="partial"))

    with pytest.raises(ValidationError) as exc_info:
        host.execution_review(12)

    assert exc_info.value.details.get("field") == "plan_identity"
    assert exc_info.value.details.get("reason") == "not_reviewable_official_plan"
    assert host.calls == [("resolve", 12, ROLE_ADOPTED, None)]


