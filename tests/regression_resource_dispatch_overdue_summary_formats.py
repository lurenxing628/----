from __future__ import annotations

import json

from core.services.scheduler.resource_dispatch_support import extract_overdue_batch_ids


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
