"""Retirement contracts: exact canonical identity, explicit unsupported scope and unchanged original exports."""

from __future__ import annotations

import json
import os
from contextlib import closing
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from tests.gantt.test_gantt_url_persistence import _business_state, _canonical_workspace
from tests.web_pages.reports_workbench_backlink_helpers import (
    INTERNAL_VISIBLE_TOKENS,
    _assert_public_output_boundaries,
    _PageParser,
    _xlsx_text,
)
from tests.web_pages.reports_workbench_backlink_helpers import (
    _client as _reports_client,
)


def _client():
    from core.infrastructure.database import get_connection
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.system.system_config_service import SystemConfigService
    client = _reports_client()
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        ConfigService(conn).ensure_defaults()
        SystemConfigService(conn).ensure_defaults(backup_keep_days_default=client.application.config["BACKUP_KEEP_DAYS"])
        conn.commit()
    return client


def _assert_query_values(query, expected):
    for key, value in expected.items():
        assert query[key] == [value], (key, query)


def _retired(client, path, query):
    response = client.get(path, query_string=query)
    assert response.status_code == 410, response.get_data(as_text=True)
    assert "Location" not in response.headers and response.headers["Cache-Control"] == "no-store"
    html = response.get_data(as_text=True)
    assert "旧入口已退役" in html and "原业务数据、保存的配置和历史记录仍保留" in html
    assert "/static/js/" not in html and "/static/css/" not in html
    parser = _PageParser()
    parser.feed(html)
    _assert_public_output_boundaries(parser)
    visible = "\n".join(parser.visible_parts)
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in visible
    assert not any(link["href"].startswith("/workbench?") for link in parser.links)
    return html, parser


def _no_current_summary(html):
    # The old home summary/disabled-link markup is gone, not replaced by adopted/current data.
    for text in ("超期批次 0", "超期批次需要先看", "资源负荷偏高", "设备利用率", "80.0%",
                 "最新排产", "当前正式采用方案", "当前排产风险概览"):
        assert text not in html


def _export(client, parser, path, expected, *, scenario=False):
    links = [link["href"] for link in parser.links if urlsplit(link["href"]).path == path + "/export"]
    assert len(links) == 1, parser.links
    query = parse_qs(urlsplit(links[0]).query)
    _assert_query_values(query, expected)
    if scenario:
        assert "scenario_id" not in query and query["plan_context_token"]
        assert "SCENARIO-RPT" not in query["plan_context_token"][0]
    response = client.get(links[0])
    assert response.status_code == 200 and "attachment" in response.headers["Content-Disposition"]
    text = _xlsx_text(response.data)
    assert text and response.data.startswith(b"PK")
    if path == "/reports/utilization" and expected.get("batch_id") == "B-RPT":
        import openpyxl
        book = openpyxl.load_workbook(BytesIO(response.data), read_only=True, data_only=True)
        try:
            rows = list(book["设备负荷"].iter_rows(values_only=True))
            assert rows[0][:4] == ("设备编号", "设备名称", "负荷(小时)", "任务数")
            assert len(rows) == 2 and rows[1][:4] == ("M-RPT", "一号设备", 4, 1)
        finally:
            book.close()
    return text


def _seed_newer_executable_version(version: int) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        source = conn.execute("SELECT op_id, machine_id, operator_id FROM Schedule WHERE version = 12 LIMIT 1").fetchone()
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source["op_id"],
                source["machine_id"],
                source["operator_id"],
                "2026-05-07 08:00:00",
                "2026-05-07 12:00:00",
                "unlocked",
                version,
            ),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version,
                "priority_first",
                1,
                1,
                "success",
                json.dumps({"algo": {"metrics": {"machine_util_avg": 0.8}}}, ensure_ascii=False),
                "pytest",
            ),
        )
        conn.commit()
    finally:
        conn.close()



def test_workbench_main_flow_from_home_keeps_context_and_reaches_first_version_pages() -> None:
    client = _client()
    before = _business_state(client)
    identity = {"version": "12", "plan_role": "adopted"}
    scope = dict(identity, date_from="2026-05-06", date_to="2026-05-06",
                 batch_id="B-RPT", resource_type="machine", resource_id="M-RPT")
    home, _ = _retired(client, "/", scope)
    _no_current_summary(home)
    # The seven original navigation cases keep their literal query fields. Unsupported
    # old controls cannot silently turn these links into a new default workspace.
    cases = (
        ("/reports/overdue", dict(identity, batch_id="B-RPT", resource_type="machine", resource_id="M-RPT")),
        ("/scheduler/analysis", scope),
        ("/scheduler/gantt", dict(identity, view="machine", start_date="2026-05-06", end_date="2026-05-06",
                                  gantt_batch="B-RPT", gantt_resource="M-RPT")),
        ("/scheduler/gantt", dict(identity, view="operator", start_date="2026-05-06", end_date="2026-05-06", gantt_batch="B-RPT")),
        ("/scheduler/resource-dispatch", dict(identity, date_from="2026-05-06", date_to="2026-05-06",
                                              period_preset="custom", scope_type="machine", scope_id="M-RPT", machine_id="M-RPT", batch_id="B-RPT")),
        ("/reports/execution-review", scope),
        ("/reports/utilization", dict(identity, start_date="2026-05-06", end_date="2026-05-06",
                                      batch_id="B-RPT", resource_type="machine", resource_id="M-RPT")),
    )
    for path, query in cases:
        _, parser = _retired(client, path, query)
        if path.startswith("/reports/"):
            text = _export(client, parser, path, query)
            assert ("M-RPT" if path == "/reports/utilization" else "B-RPT") in text
            assert "M-OTHER" not in text
    context, payload = _canonical_workspace(client, dict(identity, start_date="2026-05-06", end_date="2026-05-06"))
    assert context["range_start"] == "2026-05-06T00:00:00" and context["range_end"] == "2026-05-07T00:00:00"
    assert payload["data"]["plan"]["version"] == 12 and len(payload["data"]["tasks"]) == 3
    assert _business_state(client) == before


def test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese() -> None:
    client = _client()
    before = _business_state(client)
    query = dict(version="12", plan_role="baseline_best", date_from="2026-05-06", date_to="2026-05-06")
    for path in ("/scheduler/analysis", "/"):
        html, parser = _retired(client, path, query)
        assert "所选对比方案未保存" in html and "未沿用旧页的采用方案回退" in html
        assert not [link for link in parser.links if "/execution-review" in link["href"]]
        _no_current_summary(html)
    # The old disabled button's business guard remains in the actual export endpoint.
    blocked = client.get("/reports/execution-review/export", query_string=query)
    assert blocked.status_code == 400
    assert "计划和现场实际只复盘正式采用方案" in blocked.get_data(as_text=True)
    assert _business_state(client) == before


def test_workbench_scenario_preview_home_entry_is_read_only_and_does_not_use_current_summary() -> None:
    client = _client()
    query = dict(version="12", plan_role="adopted", scenario_id="SCENARIO-RPT",
                 date_from="2026-05-06", date_to="2026-05-06", batch_id="B-RPT",
                 resource_type="machine", resource_id="M-RPT")
    broken_before = _business_state(client)
    broken, _ = _retired(client, "/scheduler/analysis", query)
    assert "永久身份缺失或绑定已失效" in broken
    assert _business_state(client) == broken_before
    # The old helper inserts the scenario before its base history. Recreate only
    # this disposable fixture after that history exists; never repair refs on GET.
    from core.infrastructure.database import get_connection
    with closing(get_connection(client.application.config["DATABASE_PATH"])) as conn:
        scenario = dict(conn.execute("SELECT * FROM ScheduleAdjustmentScenario WHERE scenario_id='SCENARIO-RPT'").fetchone())
        rows = [dict(row) for row in conn.execute("SELECT * FROM ScheduleAdjustmentScenarioRow WHERE scenario_id='SCENARIO-RPT'")]
        conn.execute("DELETE FROM ScheduleAdjustmentScenarioRow WHERE scenario_id='SCENARIO-RPT'")
        conn.execute("DELETE FROM ScheduleAdjustmentScenario WHERE scenario_id='SCENARIO-RPT'")
        for table, records in (("ScheduleAdjustmentScenario", [scenario]), ("ScheduleAdjustmentScenarioRow", rows)):
            for record in records:
                conn.execute("INSERT INTO " + table + " (" + ",".join(record) + ") VALUES (" + ",".join("?" for _ in record) + ")", tuple(record.values()))
        conn.commit()
    before = _business_state(client)
    for path in ("/scheduler/analysis", "/"):
        html, parser = _retired(client, path, query)
        assert "已保存模拟方案" in html
        _no_current_summary(html)
        assert not [link for link in parser.links if "/execution-review" in link["href"]]
    _, parser = _retired(client, "/reports/utilization", query)
    expected = {key: value for key, value in query.items() if key != "scenario_id"}
    exported = _export(client, parser, "/reports/utilization", expected, scenario=True)
    assert "M-RPT" in exported and "M-OTHER" not in exported
    _, payload = _canonical_workspace(client, dict(version="12", plan_role="adopted", scenario_id="SCENARIO-RPT",
                                                   start_date="2026-05-06", end_date="2026-05-06"))
    plan = payload["data"]["plan"]
    assert plan["kind"] == "scenario" and plan["display_name"] == "测试模拟方案"
    assert plan["is_current_official"] is False and plan["capabilities"]["report_actual"] is False
    assert len(payload["data"]["tasks"]) == 1 and payload["data"]["tasks"][0]["batch_id"] == "B-RPT"
    blocked = client.get("/reports/execution-review/export", query_string=query)
    assert blocked.status_code == 400 and "只复盘正式采用方案" in blocked.get_data(as_text=True)
    assert _business_state(client) == before


def test_workbench_superseded_adopted_home_entry_keeps_guardrail() -> None:
    client = _client()
    _seed_newer_executable_version(13)
    before = _business_state(client)
    query = dict(version="12", plan_role="adopted", date_from="2026-05-06", date_to="2026-05-06",
                 batch_id="B-RPT", resource_type="machine", resource_id="M-RPT")
    for path in ("/scheduler/analysis", "/"):
        html, _ = _retired(client, path, query)
        assert "<dd>12</dd>" in html
        _no_current_summary(html)
    _, payload = _canonical_workspace(client, dict(version="12", plan_role="adopted",
                                                   start_date="2026-05-06", end_date="2026-05-06"))
    plan = payload["data"]["plan"]
    assert plan["version"] == 12 and plan["kind"] == "official"
    assert plan["is_current_official"] is False and plan["capabilities"]["report_actual"] is False
    assert len(payload["data"]["tasks"]) == 3
    assert all(task["start"].startswith("2026-05-06") for task in payload["data"]["tasks"])
    assert _business_state(client) == before


def test_workbench_report_rows_keep_batch_and_resource_context_when_returning_to_action_pages() -> None:
    client = _client()
    before = _business_state(client)
    overdue_query = dict(version="12", plan_role="adopted", date_from="2026-05-06", date_to="2026-05-06",
                         batch_id="B-RPT", resource_type="machine", resource_id="M-RPT")
    _, overdue = _retired(client, "/reports/overdue", overdue_query)
    text = _export(client, overdue, "/reports/overdue", overdue_query)
    assert "B-RPT" in text and "B-OTHER" not in text
    # Diagnosis is still explicitly undated; no plan-finish/event-date substitution.
    diagnosis = {key: value for key, value in overdue_query.items() if key not in ("date_from", "date_to")}
    assert "date_from" not in diagnosis and "date_to" not in diagnosis
    _retired(client, "/reports/overdue", diagnosis)
    utilization_query = dict(version="12", plan_role="adopted", start_date="2026-05-06", end_date="2026-05-06",
                             resource_type="operator", resource_id="O-RPT")
    _, utilization = _retired(client, "/reports/utilization", utilization_query)
    text = _export(client, utilization, "/reports/utilization", utilization_query)
    assert "O-RPT" in text and "O-OTHER" not in text
    _retired(client, "/scheduler/resource-dispatch", dict(version="12", date_from="2026-05-06", date_to="2026-05-06",
                                                         scope_type="operator", operator_id="O-RPT"))
    _retired(client, "/scheduler/gantt", dict(version="12", start_date="2026-05-06", end_date="2026-05-06",
                                             view="operator", gantt_resource="O-RPT"))
    assert _business_state(client) == before
