from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import pytest

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.scheduler.resource_dispatch_range import resolve_dispatch_range
from core.services.scheduler.resource_dispatch_service import ResourceDispatchService
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_CRITICAL_BEST
from tests.resource_dispatch_frontend_support import read_resource_dispatch_script_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_resource_dispatch_page_renders_generic_degradation_channel() -> None:
    template_source = _read("templates/scheduler/resource_dispatch.html")
    js_source = read_resource_dispatch_script_bundle()

    assert 'id="rdDegradationSummary"' in template_source
    assert "summary.degradation_events" in js_source
    assert "rdDegradationSummary" in js_source


def _build_client(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(str(test_db))
    try:
        conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-01", "装配一组", "active"))
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("OP001", "张三", "active", "TEAM-01", ""),
        )
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
            ("MC001", "数控车床1", "active", "TEAM-01", ""),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)", ("PART-001", "回转壳体", "[]"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "PART-001", "回转壳体", 5, "2026-03-08", "urgent", "yes", "scheduled"),
        )
        cur = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        if cur.lastrowid is None:
            raise RuntimeError("BatchOperations insert did not return row id")
        op_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, "MC001", "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
        )
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "greedy",
                1,
                1,
                "simulated",
                json.dumps(
                    {
                        "is_simulation": True,
                        "completion_status": "partial",
                        "overdue_batches": {"count": 1, "items": [{"batch_id": "B001"}]},
                    },
                    ensure_ascii=False,
                ),
                "test",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    return app.test_client()


def _query_dict(location: str):
    parsed = urlparse(location)
    return parse_qs(parsed.query)


def test_resource_dispatch_invalid_queries_redirect_to_clean_url(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    cases = [
        (
            "invalid_date",
            "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=week&query_date=bad&version=1",
            {"scope_type": ["operator"], "operator_id": ["OP001"], "version": ["1"]},
            {"period_preset", "query_date"},
        ),
        (
            "invalid_scope",
            "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP404&period_preset=week&query_date=2026-03-02&version=1",
            {"scope_type": ["operator"], "period_preset": ["week"], "query_date": ["2026-03-02"], "version": ["1"]},
            {"operator_id", "scope_id"},
        ),
        (
            "invalid_scope_type",
            "/scheduler/resource-dispatch?scope_type=bad&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1",
            {"period_preset": ["week"], "query_date": ["2026-03-02"], "version": ["1"]},
            {"scope_type", "operator_id", "scope_id"},
        ),
        (
            "invalid_team_axis",
            "/scheduler/resource-dispatch?scope_type=team&team_id=TEAM-01&team_axis=bad&period_preset=week&query_date=2026-03-02&version=1",
            {
                "scope_type": ["team"],
                "team_id": ["TEAM-01"],
                "period_preset": ["week"],
                "query_date": ["2026-03-02"],
                "version": ["1"],
            },
            {"team_axis"},
        ),
        (
            "invalid_period_preset",
            "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=bad&query_date=2026-03-02&version=1",
            {"scope_type": ["operator"], "operator_id": ["OP001"], "version": ["1"]},
            {"period_preset", "query_date"},
        ),
        (
            "invalid_version",
            "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=bad",
            {"scope_type": ["operator"], "operator_id": ["OP001"], "period_preset": ["week"], "query_date": ["2026-03-02"]},
            {"version"},
        ),
        (
            "zero_version",
            "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=0",
            {"scope_type": ["operator"], "operator_id": ["OP001"], "period_preset": ["week"], "query_date": ["2026-03-02"]},
            {"version"},
        ),
    ]

    for case_name, url, expected_params, missing_keys in cases:
        resp = client.get(url)
        assert resp.status_code == 302, case_name
        params = _query_dict(resp.headers["Location"])
        for key, expected_value in expected_params.items():
            assert params.get(key) == expected_value, case_name
        for key in missing_keys:
            assert key not in params, case_name


def test_resource_dispatch_missing_history_version_fails_closed_without_query_cleanup(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)
    query = "scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=999"

    page_resp = client.get(f"/scheduler/resource-dispatch?{query}")
    page_html = page_resp.get_data(as_text=True)
    assert page_resp.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in page_html
    assert page_resp.headers.get("Location") is None

    data_resp = client.get(f"/scheduler/resource-dispatch/data?{query}")
    payload = data_resp.get_json()
    assert data_resp.status_code == 404
    assert payload["success"] is False
    assert payload["error"]["message"] == "排产版本不存在，请先选择已有版本。"
    assert "cleanup_query_keys" not in (payload["error"].get("details") or {})
    assert "cleanup_query_keys" not in (payload["error"].get("diagnostics") or {})

    export_resp = client.get(f"/scheduler/resource-dispatch/export?{query}")
    assert export_resp.status_code == 404
    assert "排产版本不存在，请先选择已有版本。" in export_resp.get_data(as_text=True)


def test_resource_dispatch_version_dropdown_uses_composed_result_status_label(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get("/scheduler/resource-dispatch?scope_type=operator&operator_id=OP001&version=1")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "模拟排产 / 部分成功" in html
    assert "模拟排产）" not in html


def test_resource_dispatch_mixed_invalid_filters_settle_without_500(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch?scope_type=operator&operator_id=OP404&period_preset=week&query_date=bad&version=1",
        follow_redirects=True,
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "资源排班" in html
    assert "id=\"rdPage\"" in html
    assert "query_date格式不正确" not in html
    assert "查询日期填写不正确，请检查后重试。" in html


def test_resource_dispatch_data_returns_machine_field_and_invalid_query_keys(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch/data?scope_type=bad&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1"
    )

    payload = resp.get_json()
    assert resp.status_code == 400
    assert payload["success"] is False
    assert payload["error"]["details"]["field"] == "范围类型"
    assert payload["error"]["details"]["invalid_query_keys"] == [
        "scope_type",
        "scope_id",
        "operator_id",
        "machine_id",
        "team_id",
    ]
    assert payload["error"]["details"]["invalid_query_labels"] == ["范围类型", "范围对象", "人员", "设备", "班组"]
    assert payload["error"]["details"]["cleanup_query_keys"] == [
        "scope_type",
        "scope_id",
        "operator_id",
        "machine_id",
        "team_id",
    ]
    assert payload["error"]["diagnostics"]["invalid_query_keys"] == [
        "scope_type",
        "scope_id",
        "operator_id",
        "machine_id",
        "team_id",
    ]
    assert payload["error"]["diagnostics"]["invalid_query_labels"] == [
        "范围类型",
        "范围对象",
        "人员",
        "设备",
        "班组",
    ]
    assert payload["error"]["diagnostics"]["cleanup_query_keys"] == [
        "scope_type",
        "scope_id",
        "operator_id",
        "machine_id",
        "team_id",
    ]


def test_resource_dispatch_data_uses_app_error_http_mapping(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    def _raise_not_found(self, **_kwargs):
        raise BusinessError(ErrorCode.NOT_FOUND, "资源排班版本不存在")

    monkeypatch.setattr(ResourceDispatchService, "get_dispatch_payload", _raise_not_found)

    resp = client.get(
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1"
    )

    payload = resp.get_json()
    assert resp.status_code == 404
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.NOT_FOUND.value
    assert payload["error"]["message"] == "资源排班版本不存在"


def test_resource_dispatch_data_unexpected_error_uses_unified_unknown_error_contract(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    def _raise_bug(self, **_kwargs):
        raise RuntimeError("dispatch exploded")

    monkeypatch.setattr(ResourceDispatchService, "get_dispatch_payload", _raise_bug)

    resp = client.get(
        "/scheduler/resource-dispatch/data?scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1"
    )

    payload = resp.get_json()
    assert resp.status_code == 500
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.UNKNOWN_ERROR.value
    assert payload["error"]["message"] == "资源排班数据生成失败，请稍后重试。"


def test_resource_dispatch_export_redirects_to_sanitized_page_url(tmp_path, monkeypatch) -> None:
    client = _build_client(tmp_path, monkeypatch)

    resp = client.get(
        "/scheduler/resource-dispatch/export?scope_type=operator&operator_id=OP001&period_preset=bad&query_date=2026-03-02&version=1"
    )

    assert resp.status_code == 302
    params = _query_dict(resp.headers["Location"])
    assert params.get("scope_type") == ["operator"]
    assert params.get("operator_id") == ["OP001"]
    assert params.get("version") == ["1"]
    assert "period_preset" not in params
    assert "query_date" not in params


def test_resource_dispatch_service_validation_errors_use_machine_field_keys() -> None:
    svc = object.__new__(ResourceDispatchService)

    with pytest.raises(ValidationError) as scope_exc:
        svc._normalize_scope_type("bad")
    with pytest.raises(ValidationError) as axis_exc:
        svc._normalize_team_axis("bad")

    assert scope_exc.value.field == "scope_type"
    assert axis_exc.value.field == "team_axis"


def test_resource_dispatch_service_version_latest_contract_matches_scheduler_routes() -> None:
    svc = object.__new__(ResourceDispatchService)
    cast(Any, svc).history_service = type(
        "_HistoryService",
        (),
        {
            "get_by_version": lambda _self, version: {"version": version} if int(version) in {7, 9} else None,
        },
    )()

    assert svc._resolve_version(None, latest_version=7).selected_version == 7
    assert svc._resolve_version("", latest_version=7).selected_version == 7
    assert svc._resolve_version("latest", latest_version=7).selected_version == 7
    assert svc._resolve_version("LATEST", latest_version=7).selected_version == 7
    assert svc._resolve_version("9", latest_version=7).selected_version == 9
    assert svc._resolve_version("latest", latest_version=0).selected_version is None

    for raw in ("abc", "0", "-1"):
        with pytest.raises(ValidationError):
            svc._resolve_version(raw, latest_version=7)


def test_resource_dispatch_service_no_history_latest_returns_empty_zero_version() -> None:
    svc = object.__new__(ResourceDispatchService)
    svc._latest_version = lambda: 0  # type: ignore[method-assign]

    latest_payload = svc.get_dispatch_payload(scope_type="operator", version="latest")
    default_payload = svc.get_dispatch_payload(scope_type="operator", version=None)
    critical_payload = svc.get_dispatch_payload(scope_type="operator", version="latest", plan_role=ROLE_CRITICAL_BEST)

    for payload in (latest_payload, default_payload, critical_payload):
        assert payload["has_history"] is False
        assert payload["status"] == "no_history"
        assert payload["filters"]["version"] is None
        assert payload["tasks"] == []
        assert payload["empty_message"] == "暂无排产历史，请先执行排产。"

    critical_filters = critical_payload["filters"]
    assert critical_filters["plan_role"] == ROLE_CRITICAL_BEST
    assert critical_filters["requested_plan_role"] == ROLE_CRITICAL_BEST
    assert critical_filters["effective_plan_role"] == ROLE_ADOPTED
    assert critical_filters["plan_role_status"] == "fallback_to_adopted"
    assert critical_filters["plan_role_message"] == ""
    assert critical_filters["candidate_id"] is None
    assert critical_filters["candidate_key"] is None
    assert critical_filters["source_table"] is None
    assert critical_filters["is_comparison"] is True
    assert len(critical_payload["plan_role_options"]) == 1
    adopted_option = critical_payload["plan_role_options"][0]
    assert adopted_option["role"] == ROLE_ADOPTED
    assert adopted_option["label"] == "正式采用方案"
    assert adopted_option["is_comparison"] is False
    assert adopted_option["display_label"] == "正式采用方案"
    assert adopted_option["display_candidate_label"] == ""
    assert adopted_option["display_text"] == "正式采用方案"
    assert critical_payload["plan_role_notice"] == ""


def test_resource_dispatch_range_validation_errors_use_machine_field_keys() -> None:
    with pytest.raises(ValidationError) as preset_exc:
        resolve_dispatch_range(period_preset="bad")
    with pytest.raises(ValidationError) as custom_exc:
        resolve_dispatch_range(period_preset="custom", start_date=None, end_date=None)

    assert preset_exc.value.field == "period_preset"
    assert custom_exc.value.field == "date_range"
