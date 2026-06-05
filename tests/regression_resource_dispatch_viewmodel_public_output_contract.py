"""回归测试：decorate_resource_dispatch_payload 对外输出契约——op_code 缺失时用业务标题（如 "B001 工序10 数控车床1"）命名 task，补 counterpart_resource_identity_label，且对外 JSON 不泄露内部 op_id 与 schedule_id/op_id/_row_identity 等禁出键。"""

from __future__ import annotations

import json
from typing import Any, Set

from web.viewmodels.scheduler_resource_dispatch import decorate_resource_dispatch_payload

FORBIDDEN_PUBLIC_ROW_KEYS = {"schedule_id", "op_id", "_row_identity"}


def _json_keys(value: Any) -> Set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_json_keys(child))
        return keys
    if isinstance(value, list):
        keys: Set[str] = set()
        for child in value:
            keys.update(_json_keys(child))
        return keys
    return set()


def test_resource_dispatch_payload_uses_public_business_title_when_op_code_missing() -> None:
    internal_identity = "op:INTERNAL-OP-ID-987654:2026-03-02 08:00:00:2026-03-02 10:00:00"
    public_row = {
        "schedule_id": 1,
        "op_id": "INTERNAL-OP-ID-987654",
        "_row_identity": internal_identity,
        "scope_type": "operator",
        "batch_id": "B001",
        "seq": 10,
        "operator_id": "OP001",
        "operator_name": "张三",
        "machine_id": "MC001",
        "machine_name": "数控车床1",
        "op_code": "",
    }
    payload = {
        "detail_rows": [dict(public_row)],
        "tasks": [
            {
                **public_row,
                "id": "task_B001_deadbeef",
                "name": "task_B001_deadbeef",
                "meta": dict(public_row),
            }
        ],
        "calendar_rows": [
            {
                "scope_type": "operator",
                "operator_id": "OP001",
                "operator_name": "张三",
                "cells": [
                    {
                        "date": "2026-03-02",
                        "items": [dict(public_row, time_label="08:00-10:00")],
                    }
                ],
            }
        ],
    }

    out = decorate_resource_dispatch_payload(payload)

    assert out["tasks"][0]["name"] == "B001 工序10 数控车床1"
    assert out["tasks"][0]["meta"]["counterpart_resource_identity_label"] == "MC001 数控车床1"
    assert out["calendar_rows"][0]["cells"][0]["items"][0]["text"] == "08:00-10:00 B001 工序10 数控车床1"
    assert (
        out["calendar_rows"][0]["cells"][0]["items"][0]["counterpart_resource_identity_label"]
        == "MC001 数控车床1"
    )
    assert "task_B001_deadbeef" not in out["tasks"][0]["name"]
    public_json = json.dumps(out, ensure_ascii=False)
    assert "INTERNAL-OP-ID-987654" not in public_json
    public_keys = _json_keys(json.loads(public_json))
    for key in FORBIDDEN_PUBLIC_ROW_KEYS:
        assert key not in public_keys
