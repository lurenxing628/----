"""回归测试：摘要的公开展示不能泄露内部调试信息。"""

from __future__ import annotations

import importlib
import json
import sys

from tests.schedule.summary.test_scheduler_summary_result_summary_contract import (
    INTERNAL_SECRET,
    REPO_ROOT,
    _persist_summary_roundtrip,
    _prepare_db,
)


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
    client = app.test_client()

    for path in (
        "/scheduler/analysis?version=3",
        "/system/history?version=3",
        "/scheduler/",
        "/scheduler/week-plan?version=3",
        "/scheduler/gantt?version=3",
        "/scheduler/gantt/data?include_history=1",
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=OP1&period_preset=week&query_date=2026-04-01&version=3",
        "/reports/",
        "/reports/overdue?version=3",
        "/reports/utilization?version=3",
        "/reports/downtime?version=3",
    ):
        response = client.get(path)
        html = response.get_data(as_text=True)
        assert response.status_code == 200, f"{path} 返回异常：{response.status_code}\n{html[:500]}"
        if "selected_summary_display" in html or "latest_summary_display" in html:
            assert INTERNAL_SECRET not in html, path
