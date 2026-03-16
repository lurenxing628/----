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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.scheduler.schedule_summary import _SUMMARY_SIZE_LIMIT_BYTES, _apply_summary_size_guard

    selected_obj = _selected_case(60000)
    selected_before = _size_bytes(selected_obj)
    assert selected_before > _SUMMARY_SIZE_LIMIT_BYTES, "selected_case 应先超过 size guard 上限"
    selected_after_obj = _apply_summary_size_guard(selected_obj)
    selected_after = _size_bytes(selected_after_obj)
    assert bool(selected_after_obj.get("summary_truncated")), "selected_case 未标记 summary_truncated"
    assert int(selected_after_obj.get("original_size_bytes") or 0) == selected_before, "selected_case 未记录原始大小"
    assert selected_after <= _SUMMARY_SIZE_LIMIT_BYTES, "selected_case 截断后仍超过 512KB"
    assert len(selected_after_obj.get("selected_batch_ids") or []) < 60000, "selected_case 未裁剪 selected_batch_ids"

    overdue_obj = _overdue_case(6000)
    overdue_before = _size_bytes(overdue_obj)
    assert overdue_before > _SUMMARY_SIZE_LIMIT_BYTES, "overdue_case 应先超过 size guard 上限"
    overdue_after_obj = _apply_summary_size_guard(overdue_obj)
    overdue_after = _size_bytes(overdue_after_obj)
    assert bool(overdue_after_obj.get("summary_truncated")), "overdue_case 未标记 summary_truncated"
    assert int(overdue_after_obj.get("original_size_bytes") or 0) == overdue_before, "overdue_case 未记录原始大小"
    assert overdue_after <= _SUMMARY_SIZE_LIMIT_BYTES, "overdue_case 截断后仍超过 512KB"
    overdue_batches = overdue_after_obj.get("overdue_batches") or {}
    assert int(overdue_batches.get("count") or 0) == 6000, "overdue_case 不应改动 overdue count"
    assert len(overdue_batches.get("items") or []) < 6000, "overdue_case 未裁剪 overdue items"

    print("OK")


if __name__ == "__main__":
    main()
