"""合同测试：半途失败批次不得按截断完工时间被判"健康"（audit 2026-07-20 A18）。

派工失败标准形态：前几道工序成功进 results、失败后整批 block——该批次在
finish_by_batch 里有条目但值是被截断的部分完工时间。修复前它按截断值参与
超期/临期分类，多数落"健康跳过"，且未排清单只认零结果批次，三清单合计交出
"健康"口径。本文件锁定修复后口径：
1. 半途失败批次整体排除出超期/临期分类（含截断值本会判超期/临期/健康三种形态）；
2. result_summary 新增 incomplete_batches 风险清单（batch_id/原因/已排/未排工序数可见）；
3. 全成功批次口径不回归（照常参与超期/临期分类、不进 incomplete 清单）；
4. 全失败批次口径不回归（仍走 unscheduled 未完工口径、不进 incomplete 清单）。
"""

from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace

from core.services.scheduler.summary.due_risk_items import (
    build_incomplete_batch_items,
    incomplete_batch_ids_from_failure_details,
)
from core.services.scheduler.summary.schedule_summary import build_overdue_items, build_result_summary


class _SummarySvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def _result(op_id: int, batch_id: str, *, seq: int, end: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        op_id=op_id,
        op_code=f"{batch_id}_{seq:02d}",
        batch_id=batch_id,
        seq=seq,
        source="internal",
        machine_id="MC1",
        operator_id="OP1",
        op_type_name="车削",
        start_time=datetime(2026, 6, 1, 8, 0, 0),
        end_time=end,
    )


def _failure_detail(op_id: int, batch_id: str, *, seq: int, code: str) -> dict:
    return {"op_id": op_id, "op_code": f"{batch_id}_{seq:02d}", "batch_id": batch_id, "seq": seq, "code": code}


# ---------------------------------------------------------------------------
# 单元层：incomplete 集合推导 + 超期/临期分类排除
# ---------------------------------------------------------------------------


def test_incomplete_set_only_contains_partially_scheduled_failed_batches() -> None:
    finish = {"B_HALF": datetime(2026, 6, 10, 12, 0, 0)}
    details = [
        _failure_detail(2, "B_HALF", seq=20, code="dispatch_operation_failed"),
        _failure_detail(4, "B_FAIL", seq=10, code="dispatch_operation_failed"),  # 零结果批次：不进集合
        "not-a-dict",  # 脏明细：忽略
        {"code": "missing_batch", "batch_id": ""},  # 空批次号：忽略
    ]
    assert incomplete_batch_ids_from_failure_details(details, finish) == {"B_HALF"}
    assert incomplete_batch_ids_from_failure_details(None, finish) == set()


def test_overdue_and_near_due_classification_excludes_incomplete_batches() -> None:
    # due 2026-06-20 -> due_exclusive 2026-06-21 00:00；三个半途失败批次分别落在
    # 修复前会判 超期/临期/健康 的三种截断形态，修复后全部不进两侧清单。
    batches = {
        b: SimpleNamespace(due_date="2026-06-20")
        for b in ("HALF_OVR", "HALF_NEAR", "HALF_HEALTHY", "OK_OVR")
    }
    finish = {
        "HALF_OVR": datetime(2026, 6, 22, 0, 0, 0),
        "HALF_NEAR": datetime(2026, 6, 20, 12, 0, 0),
        "HALF_HEALTHY": datetime(2026, 6, 10, 0, 0, 0),
        "OK_OVR": datetime(2026, 6, 22, 0, 0, 0),
    }
    items, meta = build_overdue_items(
        _SummarySvc(),
        batches=batches,
        finish_by_batch=finish,
        summary=SimpleNamespace(warnings=[]),
        incomplete_batch_ids={"HALF_OVR", "HALF_NEAR", "HALF_HEALTHY"},
    )
    assert [i["batch_id"] for i in items] == ["OK_OVR"], items
    assert meta["near_due_items"] == [], meta


def test_overdue_classification_without_exclusion_keeps_legacy_behavior() -> None:
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    finish = {"B": datetime(2026, 6, 22, 0, 0, 0)}
    items, _meta = build_overdue_items(
        _SummarySvc(), batches=batches, finish_by_batch=finish, summary=SimpleNamespace(warnings=[])
    )
    assert [i["batch_id"] for i in items] == ["B"], items


def test_build_incomplete_batch_items_carries_reason_and_op_counts() -> None:
    finish = {"B_HALF": datetime(2026, 6, 10, 12, 0, 0)}
    results = [_result(1, "B_HALF", seq=10, end=finish["B_HALF"])]
    details = [
        _failure_detail(2, "B_HALF", seq=20, code="dispatch_operation_failed"),
        _failure_detail(3, "B_HALF", seq=30, code="skipped_after_batch_failure"),
    ]
    items = build_incomplete_batch_items(
        _SummarySvc(),
        incomplete_batch_ids={"B_HALF"},
        batches={"B_HALF": SimpleNamespace(due_date="2026-06-20")},
        finish_by_batch=finish,
        results=results,
        failure_details=details,
    )
    assert len(items) == 1, items
    item = items[0]
    assert item["batch_id"] == "B_HALF"
    assert item["reason_code"] == "dispatch_operation_failed"
    assert item["scheduled_op_count"] == 1
    assert item["failed_op_count"] == 2
    assert item["due_date"] == "2026-06-20"
    assert item["partial_finish_time"] == "2026-06-10 12:00:00"


# ---------------------------------------------------------------------------
# 集成层：build_result_summary 三批次全景（全成功 / 半途失败 / 全失败）
# ---------------------------------------------------------------------------


def _build_three_batch_summary():
    from core.algorithms.evaluation import compute_metrics

    start_dt = datetime(2026, 6, 1, 8, 0, 0)
    batches = {
        # 全成功且完工超期：必须照常进超期清单（口径不回归）。
        "B_OK": SimpleNamespace(batch_id="B_OK", due_date="2026-06-20", priority="normal", quantity=1),
        # 半途失败：截断 finish 远早于交期，修复前会被判"健康"三清单全漏。
        "B_HALF": SimpleNamespace(batch_id="B_HALF", due_date="2026-06-20", priority="normal", quantity=1),
        # 全失败（零结果）：仍走 unscheduled 未完工口径。
        "B_FAIL": SimpleNamespace(batch_id="B_FAIL", due_date="2026-06-20", priority="normal", quantity=1),
    }
    results = [
        _result(1, "B_OK", seq=10, end=datetime(2026, 6, 22, 12, 0, 0)),
        _result(2, "B_HALF", seq=10, end=datetime(2026, 6, 5, 12, 0, 0)),
    ]
    failure_details = [
        _failure_detail(3, "B_HALF", seq=20, code="dispatch_operation_failed"),
        _failure_detail(4, "B_HALF", seq=30, code="skipped_after_batch_failure"),
        _failure_detail(5, "B_FAIL", seq=10, code="dispatch_operation_failed"),
    ]
    summary = SimpleNamespace(
        success=False,
        total_ops=5,
        scheduled_ops=2,
        failed_ops=3,
        warnings=[],
        errors=[],
        failure_details=failure_details,
    )
    overdue_items, result_status, result_summary_obj, result_summary_json, _time_cost_ms = build_result_summary(
        _SummarySvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=9,
        normalized_batch_ids=list(batches.keys()),
        start_dt=start_dt,
        end_date=None,
        batches=batches,
        operations=[],
        results=results,
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=compute_metrics(results, batches),
        best_order=list(batches.keys()),
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        simulate=False,
        t0=time.time() - 0.01,
    )
    return overdue_items, result_status, result_summary_obj, result_summary_json


def test_result_summary_lists_half_failed_batch_as_incomplete_risk() -> None:
    overdue_items, result_status, result_summary_obj, result_summary_json = _build_three_batch_summary()

    assert result_status == "partial", result_status

    incomplete = dict(result_summary_obj.get("incomplete_batches") or {})
    assert int(incomplete.get("count") or 0) == 1, incomplete
    items = list(incomplete.get("items") or [])
    assert len(items) == 1, items
    item = dict(items[0])
    assert item.get("batch_id") == "B_HALF", item
    assert item.get("reason_code") == "dispatch_operation_failed", item
    assert int(item.get("scheduled_op_count") or 0) == 1, item
    assert int(item.get("failed_op_count") or 0) == 2, item
    assert item.get("due_date") == "2026-06-20", item
    assert item.get("partial_finish_time") == "2026-06-05 12:00:00", item

    # 半途失败批次不得再按截断 finish 参与超期/临期"健康"分类。
    overdue_ids = {i["batch_id"] for i in overdue_items}
    near_ids = {i["batch_id"] for i in (result_summary_obj.get("near_due_batches") or {}).get("items") or []}
    assert "B_HALF" not in overdue_ids, overdue_items
    assert "B_HALF" not in near_ids, near_ids

    # payload/导出摘要可见：新键随 JSON 一并落盘。
    assert '"incomplete_batches"' in result_summary_json


def test_result_summary_fully_scheduled_and_fully_failed_batches_do_not_regress() -> None:
    overdue_items, _result_status, result_summary_obj, _json = _build_three_batch_summary()

    # 全成功且超期批次照常进超期清单，不被误伤进 incomplete。
    overdue_ids = {i["batch_id"] for i in overdue_items}
    assert "B_OK" in overdue_ids, overdue_items
    incomplete_ids = {
        str(i.get("batch_id")) for i in (result_summary_obj.get("incomplete_batches") or {}).get("items") or []
    }
    assert "B_OK" not in incomplete_ids, incomplete_ids

    # 全失败批次仍走 unscheduled 未完工口径，不进 incomplete 清单。
    assert "B_FAIL" not in incomplete_ids, incomplete_ids
    unscheduled_sample = [str(x) for x in result_summary_obj.get("unscheduled_batch_ids_sample") or []]
    assert any(x.startswith("B_FAIL") for x in unscheduled_sample), unscheduled_sample
    # 半途失败批次有部分完工结果，不属于"未形成完工结果"口径。
    assert not any(x.startswith("B_HALF") for x in unscheduled_sample), unscheduled_sample


def test_result_summary_without_failures_has_empty_incomplete_bucket() -> None:
    from core.algorithms.evaluation import compute_metrics

    start_dt = datetime(2026, 6, 1, 8, 0, 0)
    batches = {"B_OK": SimpleNamespace(batch_id="B_OK", due_date="2026-06-20", priority="normal", quantity=1)}
    results = [_result(1, "B_OK", seq=10, end=datetime(2026, 6, 10, 12, 0, 0))]
    summary = SimpleNamespace(
        success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[], failure_details=[]
    )
    _overdue, result_status, result_summary_obj, _json, _ms = build_result_summary(
        _SummarySvc(),
        cfg={"freeze_window_enabled": "no", "auto_assign_enabled": "no"},
        version=9,
        normalized_batch_ids=["B_OK"],
        start_dt=start_dt,
        end_date=None,
        batches=batches,
        operations=[],
        results=results,
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=compute_metrics(results, batches),
        best_order=["B_OK"],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        simulate=False,
        t0=time.time() - 0.01,
    )
    assert result_status == "success", result_status
    incomplete = dict(result_summary_obj.get("incomplete_batches") or {})
    assert int(incomplete.get("count") or 0) == 0, incomplete
    assert list(incomplete.get("items") or []) == [], incomplete
