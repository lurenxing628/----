import json
import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _size_bytes(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def _selected_case(n: int):
    return {
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
        "warnings": [],
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.schedule_summary import SUMMARY_SIZE_LIMIT_BYTES, apply_summary_size_guard

    selected_obj = _selected_case(60000)
    selected_before = _size_bytes(selected_obj)
    assert selected_before > SUMMARY_SIZE_LIMIT_BYTES, "selected_case 应先超过 size guard 上限"
    selected_after_obj = apply_summary_size_guard(selected_obj)
    selected_after = _size_bytes(selected_after_obj)
    assert bool(selected_after_obj.get("summary_truncated")), "selected_case 未标记 summary_truncated"
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
    assert oversized_public_after <= SUMMARY_SIZE_LIMIT_BYTES, "oversized_public_field_case 截断后仍超过 512KB"

    malformed_list_obj = _malformed_large_list_field_case()
    malformed_list_before = _size_bytes(malformed_list_obj)
    assert malformed_list_before > SUMMARY_SIZE_LIMIT_BYTES, "malformed_large_list_field_case 应先超过 size guard 上限"
    malformed_list_after_obj = apply_summary_size_guard(malformed_list_obj)
    malformed_list_after = _size_bytes(malformed_list_after_obj)
    assert bool(malformed_list_after_obj.get("summary_truncated")), "malformed_large_list_field_case 未标记 summary_truncated"
    assert int(malformed_list_after_obj.get("original_size_bytes") or 0) == malformed_list_before
    assert malformed_list_after <= SUMMARY_SIZE_LIMIT_BYTES, "malformed_large_list_field_case 截断后仍超过 512KB"

    print("OK")


if __name__ == "__main__":
    main()
