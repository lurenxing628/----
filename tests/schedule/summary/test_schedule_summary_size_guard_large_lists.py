"""回归测试：apply_summary_size_guard 把超过 SUMMARY_SIZE_LIMIT_BYTES(512KB) 的排产摘要逐级裁剪到限内——优先裁 selected_batch_ids/overdue items/errors/missing_resource_ops 等大列表并打 *_truncated 标记、保留 readiness 与计数/样本，按需丢弃过大或非 optimizer 的 diagnostics（小诊断不误删），并记录 original_size_bytes。"""

import json
import sys

from tests._support.paths import REPO_ROOT_STR


def find_repo_root() -> str:
    return REPO_ROOT_STR


def _size_bytes(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _selected_case(n: int):
    return {
        "readiness": {"gate_enabled": True},
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": [f"B{i:05d}" for i in range(n)]},
        "warnings": [],
        "selected_batch_ids": [f"B{i:05d}" for i in range(n)],
        "overdue_batches": {"count": 0, "items": []},
        "time_cost_ms": 1,
    }


def _overdue_case(n: int):
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {
            "count": n,
            "items": [
                {"batch_id": f"B{i:05d}", "due_date": "2026-01-01", "finish_time": "2026-01-02 00:00:00"}
                for i in range(n)
            ],
        },
        "time_cost_ms": 1,
    }


def _near_due_case(n: int):
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "near_due_batches": {
            "count": n,
            "window_days": 3,
            "items": [
                {"batch_id": f"B{i:05d}", "due_date": "2026-06-20", "finish_time": "2026-06-19 12:00:00"}
                for i in range(n)
            ],
        },
        "time_cost_ms": 1,
    }


def _minimal_trigger_near_due_case():
    # strategy_params 巨大（非可裁列表）→ tier/diagnostic 都降不下来 → 走 minimal_summary_for_size_guard
    return {
        "summary_schema_version": "1.2",
        "is_simulation": False,
        "completion_status": "partial",
        "version": 99,
        "strategy": "priority_first",
        "strategy_params": {"payload": "x" * 600000},
        "algo": {
            "attempts": [],
            "improvement_trace": [],
            "best_batch_order": [],
            "search_report": {
                "schema_version": 1,
                "algorithm_profile": "multi_start_local_search",
                "seed": 99,
                "stop_reason": "time_budget",
                "best_origin": "multi_start",
                "time_budget_seconds": 10,
                "runtime_ms": 123,
                "iterations": 5,
                "evaluated_candidates": 8,
                "distinct_candidates": 4,
                "accepted_candidates": 2,
                "accepted_distinct_candidates": 2,
                "current_accepted_candidates": 1,
                "best_improved_candidates": 1,
                "rejected_candidates": 3,
                "best_score": [0.0, 1.0],
                "objective_name": "min_overdue",
                "distinct_fingerprint_scope": "decoded_output",
                "distinct_fingerprint_description": "distinct_candidates 按正式 SGS 解码结果去重",
                "best_fingerprint_changed": True,
                "improved": True,
                "rejection_summary": {"noop_neighbor": 3},
                "neighborhood_summary": {
                    "critical_chain": {"attempted": 2, "effective": 1, "noop": 1, "fallback": 0, "rejected": 1}
                },
                "acceptance_summary": {
                    "threshold": {"attempted": 2, "accepted": 1, "rejected": 1, "non_improving_accepted": 1}
                },
                "vns_summary": {"current_neighborhood": "tardy_window", "neighborhood_index": 1},
                "public_attempt_summary": [
                    {
                        "origin": "multi_start",
                        "status": "accepted",
                        "strategy": "priority_first",
                        "dispatch_mode": "sgs",
                        "dispatch_rule": "critical_ratio",
                        "score": [0.0, 1.0],
                        "failed_ops": 0,
                    }
                ],
                "attempts": [{"candidate_id": "candidate_secret", "source_table": "internal_table"}],
                "initial_fingerprint": "op:secret-initial",
                "best_fingerprint": "graph_w_secret",
                "improvement_trace": [{"node_id": "node_secret"}],
            },
        },
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 7, "items": [{"batch_id": "O1", "due_date": "2026-06-10", "finish_time": "2026-06-12 00:00:00"}]},
        "near_due_batches": {
            "count": 5,
            "window_days": 3,
            "items": [
                {"batch_id": f"N{i:05d}", "due_date": "2026-06-20", "finish_time": "2026-06-19 12:00:00"}
                for i in range(5)
            ],
        },
        "counts": {"scheduled_ops": 1, "failed_ops": 0},
        "result_status": "success",
        "time_cost_ms": 1,
    }


def _diagnostics_case(n: int):
    payload = "x" * 12000
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "diagnostics": {
            "optimizer": {
                "attempts": [
                    {
                        "tag": "start:priority_first|sgs:cr",
                        "used_params": {"payload": payload},
                        "algo_stats": {"fallback_samples": {"huge": [{"payload": payload}]}},
                    }
                    for _ in range(n)
                ]
            }
        },
        "time_cost_ms": 1,
    }


def _non_optimizer_diagnostics_case():
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "diagnostics": {"resource_pool": {"samples": ["x" * 600000]}},
        "time_cost_ms": 1,
    }


def _non_dict_diagnostics_case():
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "diagnostics": "x" * 600000,
        "time_cost_ms": 1,
    }


def _small_diagnostics_with_large_selected_case(n: int):
    return {
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [f"B{i:05d}" for i in range(n)],
        "overdue_batches": {"count": 0, "items": []},
        "diagnostics": {"resource_pool": {"sample": "可保留的小诊断"}},
        "time_cost_ms": 1,
    }


def _oversized_public_field_case():
    return {
        "summary_schema_version": "1.2",
        "is_simulation": False,
        "completion_status": "partial",
        "version": 42,
        "strategy": "priority_first",
        "strategy_params": {"payload": "x" * 600000},
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": ["停机资料有部分设备读取失败", "资源池资料有部分自动安排设备读取失败"],
        "degradation_events": [
            {
                "code": "downtime_avoid_degraded",
                "scope": "schedule.summary.downtime_avoid",
                "field": "downtime_avoid",
                "message": "部分设备停机区间加载失败",
                "count": 2,
                "sample": "MC_BAD",
            }
        ],
        "degradation_counters": {"downtime_avoid_degraded": 2},
        "degraded_causes": ["downtime_avoid_degraded"],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "counts": {"scheduled_ops": 1, "failed_ops": 0},
        "result_status": "success",
        "time_cost_ms": 1,
    }


def _malformed_large_list_field_case():
    return {
        "summary_schema_version": "1.2",
        "is_simulation": False,
        "completion_status": "partial",
        "version": 43,
        "strategy": "priority_first",
        "algo": {"attempts": "x" * 600000, "improvement_trace": [], "best_batch_order": []},
        "warnings": "x" * 600000,
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "counts": {"scheduled_ops": 1, "failed_ops": 0},
        "result_status": "success",
        "time_cost_ms": 1,
    }


def _large_errors_case(n: int):
    return {
        "summary_schema_version": "1.2",
        "is_simulation": False,
        "completion_status": "partial",
        "version": 44,
        "strategy": "priority_first",
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "counts": {"scheduled_ops": 0, "failed_ops": n},
        "error_count": n,
        "errors": [
            f"自制工序未补全设备或人员，无法排产：工序 B{i:05d}_05，附加说明 {'x' * 80}"
            for i in range(n)
        ],
        "errors_sample": [f"自制工序未补全设备或人员，无法排产：工序 B{i:05d}_05" for i in range(10)],
        "time_cost_ms": 1,
    }


def _large_missing_resource_case(n: int):
    return {
        "summary_schema_version": "1.2",
        "is_simulation": False,
        "completion_status": "partial",
        "version": 45,
        "strategy": "priority_first",
        "algo": {"attempts": [], "improvement_trace": [], "best_batch_order": []},
        "warnings": [],
        "selected_batch_ids": [],
        "overdue_batches": {"count": 0, "items": []},
        "counts": {"scheduled_ops": 0, "failed_ops": n},
        "error_count": n,
        "failure_detail_count": n,
        "errors": [f"自制工序未补全设备或人员，无法排产：工序 B{i:05d}_05" for i in range(n)],
        "errors_sample": [f"自制工序未补全设备或人员，无法排产：工序 B{i:05d}_05" for i in range(10)],
        "public_error_details": [
            {
                "schema_version": "1.0",
                "code": "missing_internal_resource",
                "severity": "error",
                "message": f"自制工序未补全设备或人员，无法排产：工序 B{i:05d}_05",
                "op_id": i + 1,
                "op_code": "OP" + "y" * 1000,
            }
            for i in range(n)
        ],
        "missing_internal_resource_count": n,
        "missing_internal_resource_ops": [
            {
                "op_id": i + 1,
                "batch_id": "B" + "x" * 1000,
                "op_code": "OP" + "y" * 1000,
                "op_type_name": "TYPE" + "z" * 1000,
                "seq": i + 1,
                "missing_fields": ["设备", "人员", "不该出现的字段"],
            }
            for i in range(n)
        ],
        "time_cost_ms": 1,
    }


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.summary.schedule_summary import SUMMARY_SIZE_LIMIT_BYTES, apply_summary_size_guard

    selected_obj = _selected_case(60000)
    selected_before = _size_bytes(selected_obj)
    assert selected_before > SUMMARY_SIZE_LIMIT_BYTES, "selected_case 应先超过 size guard 上限"
    selected_after_obj = apply_summary_size_guard(selected_obj)
    selected_after = _size_bytes(selected_after_obj)
    assert bool(selected_after_obj.get("summary_truncated")), "selected_case 未标记 summary_truncated"
    assert selected_after_obj.get("readiness") == {"gate_enabled": True}, "selected_case 不应裁掉 readiness"
    assert int(selected_after_obj.get("original_size_bytes") or 0) == selected_before, "selected_case 未记录原始大小"
    assert selected_after <= SUMMARY_SIZE_LIMIT_BYTES, "selected_case 截断后仍超过 512KB"
    assert len(selected_after_obj.get("selected_batch_ids") or []) < 60000, "selected_case 未裁剪 selected_batch_ids"

    overdue_obj = _overdue_case(6000)
    overdue_before = _size_bytes(overdue_obj)
    assert overdue_before > SUMMARY_SIZE_LIMIT_BYTES, "overdue_case 应先超过 size guard 上限"
    overdue_after_obj = apply_summary_size_guard(overdue_obj)
    overdue_after = _size_bytes(overdue_after_obj)
    assert bool(overdue_after_obj.get("summary_truncated")), "overdue_case 未标记 summary_truncated"
    assert int(overdue_after_obj.get("original_size_bytes") or 0) == overdue_before, "overdue_case 未记录原始大小"
    assert overdue_after <= SUMMARY_SIZE_LIMIT_BYTES, "overdue_case 截断后仍超过 512KB"
    overdue_batches = overdue_after_obj.get("overdue_batches") or {}
    assert int(overdue_batches.get("count") or 0) == 6000, "overdue_case 不应改动 overdue count"
    assert len(overdue_batches.get("items") or []) < 6000, "overdue_case 未裁剪 overdue items"

    # 临期 tier 路径：与超期同构逐级裁 items、保 count/window_days、降到限内
    near_due_obj = _near_due_case(6000)
    near_due_before = _size_bytes(near_due_obj)
    assert near_due_before > SUMMARY_SIZE_LIMIT_BYTES, "near_due_case 应先超过 size guard 上限"
    near_due_after_obj = apply_summary_size_guard(near_due_obj)
    near_due_after = _size_bytes(near_due_after_obj)
    assert bool(near_due_after_obj.get("summary_truncated")), "near_due_case 未标记 summary_truncated"
    near_due_batches = near_due_after_obj.get("near_due_batches") or {}
    assert int(near_due_batches.get("count") or 0) == 6000, "near_due_case 不应改动 near_due count"
    assert int(near_due_batches.get("window_days") or 0) == 3, "near_due_case 不应丢 window_days"
    assert len(near_due_batches.get("items") or []) < 6000, "near_due_case 未裁剪 near_due items"
    assert near_due_after <= SUMMARY_SIZE_LIMIT_BYTES, "near_due_case 截断后仍超过 512KB"

    # minimal 兜底路径：公共字段过大 → 走 minimal，near_due 与 overdue 同构只留 count、丢 items
    minimal_near_obj = _minimal_trigger_near_due_case()
    assert _size_bytes(minimal_near_obj) > SUMMARY_SIZE_LIMIT_BYTES, "minimal_near 用例应先超过上限"
    minimal_near_after = apply_summary_size_guard(minimal_near_obj)
    assert bool(minimal_near_after.get("summary_truncated")), "minimal_near 未标记 summary_truncated"
    minimal_near_due = minimal_near_after.get("near_due_batches")
    assert isinstance(minimal_near_due, dict), "minimal 应保留 near_due_batches 键"
    assert int(minimal_near_due.get("count") or 0) == 5, "minimal 应保 near_due count"
    assert "items" not in minimal_near_due, "minimal 应丢 near_due items（仅留 count）"
    minimal_overdue = minimal_near_after.get("overdue_batches")
    assert isinstance(minimal_overdue, dict) and int(minimal_overdue.get("count") or 0) == 7 and "items" not in minimal_overdue, (
        "minimal overdue 同构校验失败"
    )
    minimal_algo = minimal_near_after.get("algo") or {}
    minimal_report = minimal_algo.get("search_report") or {}
    assert minimal_report.get("stop_reason") == "time_budget", "minimal 不应丢 search_report.stop_reason"
    assert minimal_report.get("best_origin") == "multi_start", "minimal 不应丢 search_report.best_origin"
    assert int(minimal_report.get("seed") or 0) == 99, "minimal 不应丢 search_report.seed"
    assert int(minimal_report.get("runtime_ms") or 0) == 123, "minimal 不应丢 search_report.runtime_ms"
    assert int(minimal_report.get("evaluated_candidates") or 0) == 8, "minimal 不应丢 search_report.evaluated_candidates"
    assert minimal_report.get("distinct_fingerprint_scope") == "decoded_output", "minimal 不应丢 distinct 口径"
    assert minimal_report.get("neighborhood_summary", {}).get("critical_chain", {}).get("attempted") == 2, (
        "minimal 不应丢 business neighborhood 口径"
    )
    assert minimal_report.get("acceptance_summary", {}).get("threshold", {}).get("non_improving_accepted") == 1, (
        "minimal 不应丢 acceptance 口径"
    )
    assert minimal_report.get("vns_summary", {}).get("current_neighborhood") == "tardy_window", "minimal 不应丢 VNS 口径"
    assert "attempts" not in minimal_report, "minimal public search_report 不得保留 raw attempts"
    assert "initial_fingerprint" not in minimal_report, "minimal public search_report 不得保留内部 initial_fingerprint"
    assert "best_fingerprint" not in minimal_report, "minimal public search_report 不得保留内部 best_fingerprint"
    minimal_text = json.dumps(minimal_report, ensure_ascii=False, sort_keys=True)
    assert "candidate_secret" not in minimal_text and "internal_table" not in minimal_text
    assert "op:secret" not in minimal_text and "graph_w_secret" not in minimal_text and "node_secret" not in minimal_text
    assert _size_bytes(minimal_near_after) <= SUMMARY_SIZE_LIMIT_BYTES, "minimal_near 后仍超过 512KB"

    diagnostics_obj = _diagnostics_case(30)
    diagnostics_before = _size_bytes(diagnostics_obj)
    assert diagnostics_before > SUMMARY_SIZE_LIMIT_BYTES, "diagnostics_case 应先超过 size guard 上限"
    diagnostics_after_obj = apply_summary_size_guard(diagnostics_obj)
    diagnostics_after = _size_bytes(diagnostics_after_obj)
    assert bool(diagnostics_after_obj.get("summary_truncated")), "diagnostics_case 未标记 summary_truncated"
    assert bool(diagnostics_after_obj.get("diagnostics_truncated")), "diagnostics_case 未标记 diagnostics_truncated"
    assert diagnostics_after <= SUMMARY_SIZE_LIMIT_BYTES, "diagnostics_case 截断后仍超过 512KB"

    non_optimizer_obj = _non_optimizer_diagnostics_case()
    non_optimizer_before = _size_bytes(non_optimizer_obj)
    assert non_optimizer_before > SUMMARY_SIZE_LIMIT_BYTES, "non_optimizer_diagnostics_case 应先超过 size guard 上限"
    non_optimizer_after_obj = apply_summary_size_guard(non_optimizer_obj)
    non_optimizer_after = _size_bytes(non_optimizer_after_obj)
    assert bool(non_optimizer_after_obj.get("summary_truncated")), "non_optimizer_diagnostics_case 未标记 summary_truncated"
    assert bool(non_optimizer_after_obj.get("diagnostics_truncated")), "non_optimizer_diagnostics_case 未标记 diagnostics_truncated"
    assert "diagnostics" not in non_optimizer_after_obj, "non_optimizer_diagnostics_case 最终应移除 diagnostics"
    assert non_optimizer_after <= SUMMARY_SIZE_LIMIT_BYTES, "non_optimizer_diagnostics_case 截断后仍超过 512KB"

    non_dict_obj = _non_dict_diagnostics_case()
    non_dict_before = _size_bytes(non_dict_obj)
    assert non_dict_before > SUMMARY_SIZE_LIMIT_BYTES, "non_dict_diagnostics_case 应先超过 size guard 上限"
    non_dict_after_obj = apply_summary_size_guard(non_dict_obj)
    non_dict_after = _size_bytes(non_dict_after_obj)
    assert bool(non_dict_after_obj.get("summary_truncated")), "non_dict_diagnostics_case 未标记 summary_truncated"
    assert bool(non_dict_after_obj.get("diagnostics_truncated")), "non_dict_diagnostics_case 未标记 diagnostics_truncated"
    assert "diagnostics" not in non_dict_after_obj, "non_dict_diagnostics_case 最终应移除 diagnostics"
    assert non_dict_after <= SUMMARY_SIZE_LIMIT_BYTES, "non_dict_diagnostics_case 截断后仍超过 512KB"

    small_diagnostics_obj = _small_diagnostics_with_large_selected_case(60000)
    small_diagnostics_after_obj = apply_summary_size_guard(small_diagnostics_obj)
    small_diagnostics_after = _size_bytes(small_diagnostics_after_obj)
    assert bool(small_diagnostics_after_obj.get("summary_truncated")), "small_diagnostics_case 未标记 summary_truncated"
    assert "diagnostics" in small_diagnostics_after_obj, "small_diagnostics_case 不应误删可保留的小 diagnostics"
    assert not small_diagnostics_after_obj.get("diagnostics_truncated"), "small_diagnostics_case 不应误标 diagnostics_truncated"
    assert small_diagnostics_after <= SUMMARY_SIZE_LIMIT_BYTES, "small_diagnostics_case 截断后仍超过 512KB"

    oversized_public_obj = _oversized_public_field_case()
    oversized_public_before = _size_bytes(oversized_public_obj)
    assert oversized_public_before > SUMMARY_SIZE_LIMIT_BYTES, "oversized_public_field_case 应先超过 size guard 上限"
    oversized_public_after_obj = apply_summary_size_guard(oversized_public_obj)
    oversized_public_after = _size_bytes(oversized_public_after_obj)
    assert bool(oversized_public_after_obj.get("summary_truncated")), "oversized_public_field_case 未标记 summary_truncated"
    assert int(oversized_public_after_obj.get("original_size_bytes") or 0) == oversized_public_before
    assert int(oversized_public_after_obj.get("warning_count") or 0) == 2, "minimal summary 不应丢失 warning_count"
    assert oversized_public_after_obj.get("warnings_sample"), "minimal summary 不应丢失 warnings_sample"
    assert bool(oversized_public_after_obj.get("warnings_truncated")), "minimal summary 裁掉 warnings 后应标记 warnings_truncated"
    events = list(oversized_public_after_obj.get("degradation_events") or [])
    assert events and events[0].get("code") == "downtime_avoid_degraded", "minimal summary 不应丢失 degradation_events"
    assert oversized_public_after_obj.get("degradation_counters") == {"downtime_avoid_degraded": 2}
    assert oversized_public_after_obj.get("degraded_causes") == ["downtime_avoid_degraded"]
    assert oversized_public_after <= SUMMARY_SIZE_LIMIT_BYTES, "oversized_public_field_case 截断后仍超过 512KB"

    malformed_list_obj = _malformed_large_list_field_case()
    malformed_list_before = _size_bytes(malformed_list_obj)
    assert malformed_list_before > SUMMARY_SIZE_LIMIT_BYTES, "malformed_large_list_field_case 应先超过 size guard 上限"
    malformed_list_after_obj = apply_summary_size_guard(malformed_list_obj)
    malformed_list_after = _size_bytes(malformed_list_after_obj)
    assert bool(malformed_list_after_obj.get("summary_truncated")), "malformed_large_list_field_case 未标记 summary_truncated"
    assert int(malformed_list_after_obj.get("original_size_bytes") or 0) == malformed_list_before
    assert malformed_list_after <= SUMMARY_SIZE_LIMIT_BYTES, "malformed_large_list_field_case 截断后仍超过 512KB"

    large_errors_obj = _large_errors_case(12000)
    large_errors_before = _size_bytes(large_errors_obj)
    assert large_errors_before > SUMMARY_SIZE_LIMIT_BYTES, "large_errors_case 应先超过 size guard 上限"
    large_errors_after_obj = apply_summary_size_guard(large_errors_obj)
    large_errors_after = _size_bytes(large_errors_after_obj)
    assert bool(large_errors_after_obj.get("summary_truncated")), "large_errors_case 未标记 summary_truncated"
    assert bool(large_errors_after_obj.get("errors_truncated")), "large_errors_case 未标记 errors_truncated"
    assert int(large_errors_after_obj.get("error_count") or 0) == 12000, "large_errors_case 不应改动 error_count"
    assert len(large_errors_after_obj.get("errors") or []) < 12000, "large_errors_case 未裁剪 errors"
    assert large_errors_after_obj.get("errors_sample"), "large_errors_case 裁剪后仍应保留 errors_sample"
    assert large_errors_after <= SUMMARY_SIZE_LIMIT_BYTES, "large_errors_case 截断后仍超过 512KB"

    large_missing_obj = _large_missing_resource_case(10000)
    large_missing_before = _size_bytes(large_missing_obj)
    assert large_missing_before > SUMMARY_SIZE_LIMIT_BYTES, "large_missing_resource_case 应先超过 size guard 上限"
    large_missing_after_obj = apply_summary_size_guard(large_missing_obj)
    large_missing_after = _size_bytes(large_missing_after_obj)
    assert bool(large_missing_after_obj.get("summary_truncated")), "large_missing_resource_case 未标记 summary_truncated"
    assert bool(large_missing_after_obj.get("errors_truncated")), "large_missing_resource_case 未标记 errors_truncated"
    assert bool(large_missing_after_obj.get("missing_internal_resource_ops_truncated")), (
        "large_missing_resource_case 未标记 missing_internal_resource_ops_truncated"
    )
    assert int(large_missing_after_obj.get("error_count") or 0) == 10000
    assert int(large_missing_after_obj.get("failure_detail_count") or 0) == 10000
    assert int(large_missing_after_obj.get("missing_internal_resource_count") or 0) == 10000
    assert len(large_missing_after_obj.get("public_error_details") or []) < 10000
    assert len(large_missing_after_obj.get("missing_internal_resource_ops") or []) < 10000
    assert large_missing_after <= SUMMARY_SIZE_LIMIT_BYTES, "large_missing_resource_case 截断后仍超过 512KB"
    for item in large_missing_after_obj.get("public_error_details") or []:
        assert "op_id" not in item
        assert "op_code" not in item
    for item in large_missing_after_obj.get("missing_internal_resource_ops") or []:
        assert "op_id" not in item
        assert "op_code" not in item
        assert len(item.get("batch_id", "")) <= 80
        assert len(item.get("op_type_name", "")) <= 80
        assert set(item.get("missing_fields", [])) <= {"设备", "人员"}

    print("OK")


def test_summary_size_guard_large_lists() -> None:
    main()


if __name__ == "__main__":
    main()
