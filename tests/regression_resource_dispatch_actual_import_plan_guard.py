from __future__ import annotations

import io

from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _event_count,
    _json,
)
from tests.regression_resource_dispatch_actual_import import _workbook_bytes


def test_actual_record_and_import_reject_non_current_official_plan(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    import_file = _workbook_bytes([{"任务识别码": "任意任务", "实际开工时间": "2026-05-01 08:00:00"}])
    old_plan_query = (
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
        "&date_from=2026-05-01&date_to=2026-05-07&version=1&plan_role=adopted"
    )

    direct = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual?{old_plan_query}",
        json=_base_payload(
            card,
            idempotency_key="actual-reject-history",
            version=1,
            actual_start_time="2026-05-01 08:00:00",
        ),
    )
    template = client.get(
        f"/scheduler/resource-dispatch/execution/actual-template?{old_plan_query}"
    )
    preview = client.post(
        f"/scheduler/resource-dispatch/execution/import/preview?{old_plan_query}",
        data={"file": (io.BytesIO(import_file), "actual.xlsx")},
        content_type="multipart/form-data",
    )
    direct_import = client.post(
        f"/scheduler/resource-dispatch/execution/import?{old_plan_query}",
        data={"file": (io.BytesIO(import_file), "actual.xlsx")},
        content_type="multipart/form-data",
    )
    confirm = client.post(
        f"/scheduler/resource-dispatch/execution/import/confirm?{old_plan_query}",
        json={
            "preview_token": "old-plan",
            "raw_rows": [{"sheet": "任务反馈", "row_number": 2, "任务识别码": "任意任务", "实际开工时间": "2026-05-01 08:00:00"}],
        },
    )

    assert direct.status_code == 409
    assert _json(direct)["error"]["details"]["reason"] == "not_current_official_plan"
    assert template.status_code == 409
    assert preview.status_code == 409
    assert _json(preview)["error"]["details"]["reason"] == "not_current_official_plan"
    assert direct_import.status_code == 409
    assert _json(direct_import)["error"]["details"]["reason"] == "not_current_official_plan"
    assert confirm.status_code == 409
    assert _json(confirm)["error"]["details"]["reason"] == "not_current_official_plan"
    assert _event_count(db_path) == 0


def test_actual_record_and_import_reject_candidate_and_scenario_plans(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    import_file = _workbook_bytes([{"任务识别码": "任意任务", "实际开工时间": "2026-05-01 08:00:00"}])
    cases = (
        (
            "candidate",
            {"requested_plan_role": "baseline_best", "effective_plan_role": "adopted", "source_table": "schedule"},
            "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best",
        ),
        (
            "scenario",
            {"requested_plan_role": "adopted", "scenario_id": "scenario-plain"},
            "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted&scenario_id=scenario-plain",
        ),
    )

    for label, overrides, query in cases:
        direct = client.post(
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual?{query}",
            json=_base_payload(
                card,
                idempotency_key=f"actual-reject-{label}",
                actual_start_time="2026-05-01 08:00:00",
                **overrides,
            ),
        )
        template = client.get(f"/scheduler/resource-dispatch/execution/actual-template?{query}")
        preview = client.post(
            f"/scheduler/resource-dispatch/execution/import/preview?{query}",
            data={"file": (io.BytesIO(import_file), "actual.xlsx")},
            content_type="multipart/form-data",
        )
        direct_import = client.post(
            f"/scheduler/resource-dispatch/execution/import?{query}",
            data={"file": (io.BytesIO(import_file), "actual.xlsx")},
            content_type="multipart/form-data",
        )
        confirm = client.post(
            f"/scheduler/resource-dispatch/execution/import/confirm?{query}",
            json={
                "preview_token": f"reject-{label}",
                "raw_rows": [{"sheet": "任务反馈", "row_number": 2, "任务识别码": "任意任务", "实际开工时间": "2026-05-01 08:00:00"}],
            },
        )

        assert direct.status_code == 409
        assert _json(direct)["error"]["details"]["reason"] == "not_current_official_plan"
        assert template.status_code == 409
        assert preview.status_code == 409
        assert _json(preview)["error"]["details"]["reason"] == "not_current_official_plan"
        assert direct_import.status_code == 409
        assert _json(direct_import)["error"]["details"]["reason"] == "not_current_official_plan"
        assert confirm.status_code == 409
        assert _json(confirm)["error"]["details"]["reason"] == "not_current_official_plan"
    assert _event_count(db_path) == 0
