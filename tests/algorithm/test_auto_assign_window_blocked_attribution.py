"""A07 合同测试：auto_assign 下"全部机-人组合完工都越过排产截止窗口"必须归因
AUTO_ASSIGN_REASON_WINDOW_BLOCKED，而不是笼统的 NO_FEASIBLE_PAIR。

锁住四个行为：
1. 归因规则：唯一失败原因=窗口 → WINDOW_BLOCKED；混合场景（存在窗口外原因的
   不可行判定）保守归 NO_FEASIBLE_PAIR。
2. 降级：SGS 评分层遇到 WINDOW_BLOCKED 不再抛 ValidationError 中止整个排产 run，
   而是返回 score_penalty=1.0 的垫底 key，让放置层按单批失败接住。
3. 文案：指向"排产截止日期/减少排产量"，不再误导用户查设备工种、人员资质；
   两种文案形态都能被 scheduler_public_errors 反解回 auto_assign_window_blocked。
4. 端到端：SGS + auto_assign + 截止日期下，越窗批次单批失败，其余批次继续排产。
"""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_runtime.auto_assign_contract import (
    AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR,
    AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE,
    AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
)
from core.algorithms.greedy.auto_assign import (
    _pair_failure_attempt,
    auto_assign_internal_resources_attempt,
)

_BASE_TIME = datetime(2026, 1, 1, 8, 0, 0)
# end_date=2026-01-01 的排他上界：次日 0 点。
_END_DT_EXCLUSIVE = datetime(2026, 1, 2, 0, 0, 0)


class _StubCalendar:
    """最小日历桩：不跳非工作时间，工时按自然小时线性推进。"""

    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id=None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubConfig:
    def __init__(self, values):
        self._values = dict(values or {})

    def get(self, key, default=None):
        return self._values.get(key, default)


def _resource_pool():
    return {
        "machines_by_op_type": {"OT-TURN": ["M1"]},
        "operators_by_machine": {"M1": ["W1"]},
        "machines_by_operator": {},
        "pair_rank": {},
    }


def _internal_op(*, op_id=101, op_code="BWB-101_10", batch_id="BWB-101", setup_hours=100.0, seq=10):
    return SimpleNamespace(
        id=op_id,
        op_code=op_code,
        batch_id=batch_id,
        piece_id=f"{batch_id}-1",
        seq=seq,
        source="internal",
        machine_id="",
        operator_id="",
        setup_hours=setup_hours,
        unit_hours=0.0,
        op_type_id="OT-TURN",
        op_type_name="车削",
        part_no="P-WB-01",
        part_name="窗测泵体",
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )


def _batch(batch_id="BWB-101"):
    return SimpleNamespace(
        batch_id=batch_id,
        part_no="P-WB-01",
        part_name="窗测泵体",
        priority="normal",
        due_date=date(2026, 1, 10),
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )


def _attempt(*, setup_hours: float, algo_stats):
    return auto_assign_internal_resources_attempt(
        calendar=_StubCalendar(),
        algo_stats=algo_stats,
        op=_internal_op(setup_hours=setup_hours),
        batch=_batch(),
        batch_progress={},
        machine_timeline={},
        operator_timeline={},
        base_time=_BASE_TIME,
        end_dt_exclusive=_END_DT_EXCLUSIVE,
        machine_downtimes=None,
        resource_pool=_resource_pool(),
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
    )


def test_all_pairs_window_blocked_reason_is_window_blocked():
    """唯一失败原因=窗口截止 → reason 必须是 WINDOW_BLOCKED，并有专属计数留痕。"""
    algo_stats = {"fallback_counts": {}}
    # 100h 工时：完工 2026-01-05 12:00，越过 2026-01-02 00:00 的排他上界。
    attempt = _attempt(setup_hours=100.0, algo_stats=algo_stats)

    assert attempt.machine_id == "" and attempt.operator_id == ""
    assert attempt.reason == AUTO_ASSIGN_REASON_WINDOW_BLOCKED
    fallback_counts = algo_stats.get("fallback_counts") or {}
    assert int(fallback_counts.get("auto_assign_window_blocked_count") or 0) == 1, f"计数异常：{fallback_counts!r}"
    assert int(fallback_counts.get("auto_assign_no_feasible_pair_count") or 0) == 0, f"不应误计 no_feasible_pair：{fallback_counts!r}"


def test_pair_within_window_still_assigns_success():
    """窗口内可完工时不许过度归因：仍应正常派出机-人组合。"""
    algo_stats = {"fallback_counts": {}}
    attempt = _attempt(setup_hours=1.0, algo_stats=algo_stats)

    assert (attempt.machine_id, attempt.operator_id) == ("M1", "W1")
    assert attempt.reason == ""
    assert (algo_stats.get("fallback_counts") or {}) == {}


@pytest.mark.parametrize(
    ("seen_operator", "window_blocked_pairs", "non_window_infeasible_pairs", "expected_reason", "expected_counter"),
    [
        # 唯一失败原因=窗口 → WINDOW_BLOCKED。
        (True, 3, 0, AUTO_ASSIGN_REASON_WINDOW_BLOCKED, "auto_assign_window_blocked_count"),
        # 混合场景（既有窗口阻挡也有窗口外不可行）→ 保守归 NO_FEASIBLE_PAIR。
        (True, 2, 1, AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR, "auto_assign_no_feasible_pair_count"),
        # 无任何窗口证据 → NO_FEASIBLE_PAIR（历史行为不变）。
        (True, 0, 1, AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR, "auto_assign_no_feasible_pair_count"),
        # 连人员候选都没有 → NO_OPERATOR_CANDIDATE 优先级最高。
        (False, 0, 0, AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE, "auto_assign_no_operator_candidate_count"),
    ],
)
def test_pair_failure_attribution_rule(seen_operator, window_blocked_pairs, non_window_infeasible_pairs, expected_reason, expected_counter):
    counted = []
    attempt = _pair_failure_attempt(
        seen_operator=seen_operator,
        window_blocked_pairs=window_blocked_pairs,
        non_window_infeasible_pairs=non_window_infeasible_pairs,
        count=counted.append,
    )
    assert attempt.reason == expected_reason
    assert counted == [expected_counter]


def test_scoring_window_blocked_returns_bottom_key_instead_of_raising():
    """降级合同：评分层 WINDOW_BLOCKED 不抛 ValidationError（原整 run 中止点），
    返回 score_penalty=1.0 的垫底 key；可行候选保持 0.0 永远排在它前面。"""
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs_scoring import _score_internal_candidate
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.greedy.run_state import ScheduleRunState

    def score(setup_hours: float):
        ctx = ScheduleRunContext(calendar=_StubCalendar(), logger=None, algo_stats={"fallback_counts": {}})
        return _score_internal_candidate(
            ctx=ctx,
            state=ScheduleRunState(base_time=_BASE_TIME),
            op=_internal_op(setup_hours=setup_hours),
            batch=_batch(),
            batch_id="BWB-101",
            batch_order={"BWB-101": 0},
            dispatch_rule=DispatchRule.SLACK,
            end_dt_exclusive=_END_DT_EXCLUSIVE,
            machine_downtimes=None,
            auto_assign_enabled=True,
            resource_pool=_resource_pool(),
            avg_proc_hours=1.0,
            strict_mode=False,
        )

    blocked_key = score(100.0)
    feasible_key = score(1.0)
    assert blocked_key[0] == 1.0, f"WINDOW_BLOCKED 候选必须垫底：{blocked_key!r}"
    assert feasible_key[0] == 0.0, f"可行候选不许被误罚：{feasible_key!r}"
    assert feasible_key < blocked_key


def test_window_blocked_messages_point_to_deadline_and_reverse_map():
    """文案合同：两种形态的窗口失败文案都指向截止日期而非资质，
    且能被 scheduler_public_errors 反解回 auto_assign_window_blocked、原样放行。"""
    from core.algorithms.greedy.dispatch.resource_validation import (
        RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE,
        internal_resource_validation_message,
    )
    from core.algorithms.greedy.internal_operation import _auto_assign_failure_message
    from core.models.scheduler_public_errors import infer_legacy_public_code, legacy_public_error_message

    op = _internal_op()
    sgs_message, details = internal_resource_validation_message(
        batch=_batch(),
        op=op,
        meta={"op_id": op.id, "batch_id": op.batch_id, "seq": op.seq},
        machine_id="",
        operator_id="",
        reason=RESOURCE_REASON_AUTO_ASSIGN_UNAVAILABLE,
        auto_assign_reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
    )
    placement_message = _auto_assign_failure_message(op=op, reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED)

    for message in (sgs_message, placement_message):
        assert "排产截止日期内无法完成" in message, message
        assert "减少排产量" in message, message
        # 不许再误导用户去查设备工种/人员资质。
        assert "设备工种" not in message, message
        assert "人员可操作设备" not in message, message
        assert infer_legacy_public_code(message) == "auto_assign_window_blocked", message
        assert legacy_public_error_message(message) == message, f"文案没有匹配反解表，会被吞成通用错误：{message!r}"

    assert details.get("reason") == "auto_assign_window_blocked"
    assert details.get("auto_assign_reason") == AUTO_ASSIGN_REASON_WINDOW_BLOCKED
    assert details.get("user_message") == sgs_message


def test_sgs_window_blocked_single_batch_fails_others_continue():
    """端到端降级合同：SGS + auto_assign + 截止日期下，越窗批次记单批失败并留
    截止日期文案，其余批次照常排出——整 run 不许中止（对齐固定资源行为）。"""
    from core.algorithms import GreedyScheduler

    blocked_op = _internal_op(op_id=201, op_code="BWB-201_10", batch_id="BWB-201", setup_hours=100.0)
    ok_op = _internal_op(op_id=301, op_code="BWB-301_10", batch_id="BWB-301", setup_hours=1.0)
    batches = {"BWB-201": _batch("BWB-201"), "BWB-301": _batch("BWB-301")}

    sched = GreedyScheduler(
        calendar_service=_StubCalendar(),
        config_service=_StubConfig({"auto_assign_enabled": "yes"}),
    )
    results, summary, _strategy, _used_params = sched.schedule(
        operations=[blocked_op, ok_op],
        batches=batches,
        start_dt=_BASE_TIME,
        end_date="2026-01-01",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        resource_pool=_resource_pool(),
    )

    # 其余批次继续：可行批次照常排出。
    assert [r.op_code for r in results] == ["BWB-301_10"], f"可行批次应照常排出：{results!r}"
    assert summary.scheduled_ops == 1
    # 越窗批次单批失败，且留下结构化失败明细。
    assert summary.failed_ops == 1
    failed_codes = [d.get("code") for d in (summary.failure_details or [])]
    assert "dispatch_operation_failed" in failed_codes, f"失败明细缺失：{summary.failure_details!r}"
    # 失败文案指向截止日期，不许再误导查资质。
    window_errors = [e for e in (summary.errors or []) if "排产截止日期内无法完成" in (e or "")]
    assert len(window_errors) == 1, f"截止日期文案缺失或重复：{summary.errors!r}"
    assert "BWB-201_10" in window_errors[0]
    assert not any("设备工种" in (e or "") for e in (summary.errors or [])), f"仍在误导查资质：{summary.errors!r}"
    # 归因计数：放置层真实失败恰好记一次 WINDOW_BLOCKED（评分探测 probe_only 不计数）。
    fallback_counts = (sched._last_algo_stats or {}).get("fallback_counts") or {}
    assert int(fallback_counts.get("auto_assign_window_blocked_count") or 0) == 1, f"计数异常：{fallback_counts!r}"
