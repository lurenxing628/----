from __future__ import annotations

import json

from core.services.scheduler.resource_dispatch_support import (
    extract_overdue_batch_ids,
    extract_overdue_batch_ids_with_meta,
)


def test_extract_overdue_batch_ids_supports_canonical_count_items_format() -> None:
    summary = json.dumps(
        {
            "overdue_batches": {
                "count": 2,
                "items": [
                    {"batch_id": "B001", "hours": 4},
                    {"batch_id": "B002", "hours": 1.5},
                ],
            }
        },
        ensure_ascii=False,
    )

    assert extract_overdue_batch_ids(summary) == {"B001", "B002"}


def test_extract_overdue_batch_ids_supports_list_format() -> None:
    summary = json.dumps({"overdue_batches": [{"batch_id": "B001"}, {"id": "B002"}, "B003"]}, ensure_ascii=False)

    assert extract_overdue_batch_ids(summary) == {"B001", "B002", "B003"}


def test_extract_overdue_batch_ids_ignores_legacy_mapping_keys() -> None:
    summary = json.dumps({"overdue_batches": {"B001": {"hours": 4}}}, ensure_ascii=False)

    assert extract_overdue_batch_ids(summary) == set()


def test_extract_overdue_batch_ids_with_meta_marks_partial_when_valid_and_invalid_items_mixed() -> None:
    summary = json.dumps(
        {"overdue_batches": [{"batch_id": "B001"}, {"hours": 4}, "", None, {"id": "B002"}]},
        ensure_ascii=False,
    )

    meta = extract_overdue_batch_ids_with_meta(summary)

    assert meta.get("ids") == ["B001", "B002"]
    assert meta.get("degraded") is False
    assert meta.get("partial") is True
    assert meta.get("reason") == "overdue_item_partial"
    assert "已识别" in str(meta.get("message") or "")


def test_extract_overdue_batch_ids_with_meta_marks_degraded_when_all_items_invalid() -> None:
    summary = json.dumps({"overdue_batches": [{"hours": 4}, "", None]}, ensure_ascii=False)

    meta = extract_overdue_batch_ids_with_meta(summary)

    assert meta.get("ids") == []
    assert meta.get("degraded") is True
    assert meta.get("partial") is False
    assert meta.get("reason") == "overdue_item_invalid"
    assert "无法识别超期批次" in str(meta.get("message") or "")


def test_extract_overdue_batch_ids_with_meta_keeps_normal_state_for_empty_list() -> None:
    meta = extract_overdue_batch_ids_with_meta(json.dumps({"overdue_batches": []}, ensure_ascii=False))

    assert meta == {"ids": [], "degraded": False, "partial": False, "message": "", "reason": ""}
