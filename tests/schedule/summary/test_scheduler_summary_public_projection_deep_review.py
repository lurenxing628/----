"""回归测试：摘要的公开展示不能泄露内部调试信息。"""

from __future__ import annotations

import importlib
import json
import sys
from contextlib import closing

from core.infrastructure.database import get_connection
from tests._support.gantt_retirement import _business_state
from tests._support.schedule_retirement import assert_redirect_navigation, assert_retired_scope, initialize_read_fixture
from tests.schedule.summary.test_scheduler_summary_result_summary_contract import (
    INTERNAL_SECRET,
    REPO_ROOT,
    _persist_summary_roundtrip,
    _prepare_db,
)
from web.viewmodels.scheduler_summary_display import build_summary_display_state


def test_result_summary_roundtrip_keeps_public_attempts_and_diagnostics_separate(tmp_path, monkeypatch) -> None:
    test_db = _prepare_db(tmp_path, monkeypatch)

    loaded = _persist_summary_roundtrip(test_db)
    assert (loaded.get("readiness") or {}).get("gate_enabled") is True

    public_attempts = (loaded.get("algo") or {}).get("attempts") or []
    assert public_attempts
    assert all(attempt.get("source") != "candidate_rejected" for attempt in public_attempts)
    assert all("source" not in attempt for attempt in public_attempts)
    assert all(attempt.get("dispatch_mode") == "sgs" for attempt in public_attempts)
    assert all("tag" not in attempt for attempt in public_attempts)
    assert all("used_params" not in attempt for attempt in public_attempts)
    assert all("algo_stats" not in attempt for attempt in public_attempts)
    assert all("origin" not in attempt for attempt in public_attempts)

    diagnostic_attempts = (((loaded.get("diagnostics") or {}).get("optimizer") or {}).get("attempts") or [])
    rejected = [attempt for attempt in diagnostic_attempts if attempt.get("source") == "candidate_rejected"]
    assert rejected[0]["origin"] == {
        "type": "ValidationError",
        "field": "resource",
        "message": INTERNAL_SECRET,
    }
    assert "score" not in rejected[0]


def test_optimizer_diagnostics_secret_is_not_rendered_on_public_scheduler_surfaces(tmp_path, monkeypatch) -> None:
    test_db = _prepare_db(tmp_path, monkeypatch)
    loaded = _persist_summary_roundtrip(test_db)
    assert INTERNAL_SECRET in json.dumps(loaded.get("diagnostics"), ensure_ascii=False)

    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    initialize_read_fixture(app)
    client = app.test_client()
    before = _business_state(client)
    with closing(get_connection(str(test_db))) as conn:
        original_summary = conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=3").fetchone()[0]
        plan_ref = conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=3 AND active=1").fetchone()[0]

    public_display = build_summary_display_state(loaded, result_status="success")
    assert public_display
    assert INTERNAL_SECRET not in json.dumps(public_display, ensure_ascii=False)
    for view in ("analysis", "gantt"):
        assert_redirect_navigation(client, "/scheduler/" + view + "?version=3", view=view, context={"plan_ref": plan_ref})

    workspace = client.get("/api/workbench/v1/plans/" + plan_ref + "/workspace")
    assert workspace.status_code == 200, workspace.get_data(as_text=True)
    assert workspace.get_json()["data"]["plan"]["plan_ref"] == plan_ref
    assert workspace.get_json()["meta"]["source"] == "production"
    assert INTERNAL_SECRET not in workspace.get_data(as_text=True)

    for path in (
        "/scheduler/week-plan?version=3",
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
        "/reports/",
        "/reports/overdue?version=3",
        "/reports/utilization?version=3",
        "/reports/downtime?version=3",
    ):
        body = assert_retired_scope(client, path)
        assert INTERNAL_SECRET not in body, path
    for path in ("/system/history?version=3", "/scheduler/"):
        body = assert_retired_scope(client, path, message="未忽略条件后跳转")
        assert INTERNAL_SECRET not in body, path
    for path in (
        "/scheduler/gantt/data?include_history=1",
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
    ):
        response = client.get(path)
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.is_json and response.get_json()
        assert INTERNAL_SECRET not in response.get_data(as_text=True), path
    with closing(get_connection(str(test_db))) as conn:
        assert conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=3").fetchone()[0] == original_summary
    assert INTERNAL_SECRET in original_summary
    assert _business_state(client) == before
