"""回归测试：报表中心各页（超期/资源利用率/停机影响/计划和现场实际）的卡片与行内回链须保留工作台上下文（version/plan_role/批次/资源/日期范围）并在各回链 URL 携带正确查询参数；导出 Excel 只含筛选目标行、隐藏内部字段表头；非 adopted 方案禁用「计划和现场实际」链接；停机重叠时长只按真实时间交集计数（compute_downtime_impact）。"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from core.infrastructure.database import get_connection
from core.services.common.degradation import DegradationCollector
from core.services.report.downtime_impact import compute_downtime_impact
from core.services.report.report_context_filters import filter_downtime_rows_for_report_context
from core.services.report.utilization import compute_utilization
from tests._support.legacy_report_contract import (
    IDENTITY_UNAVAILABLE,
    MISSING_ROLE,
    RETIRED_SCOPE,
    assert_rejected,
    assert_retired,
    get_unchanged,
    report_read_context,
)
from tests.web_pages.reports_workbench_backlink_helpers import (
    _assert_date_from_to,
    _assert_export_headers_hide_internal_tokens,
    _assert_public_output_boundaries,
    _assert_start_end,
    _client,
    _PageParser,
    _query,
    _xlsx_sheet_rows,
    _xlsx_text,
)

COMMON_REPORT_CONTEXT = {
    "version": "12",
    "plan_role": "adopted",
}
Query = Dict[str, List[str]]
QueryMap = Dict[str, Query]


def _read(client, path):
    return get_unchanged(client, path, client.application.config["DATABASE_PATH"])


def _old_report(client, path, *, download="", message=RETIRED_SCOPE, public=("12",)):
    response = _read(client, path)
    assert_retired(response, downloads=(download,) if download else (), message=message, public=public)
    parser = _PageParser()
    parser.feed(response.get_data(as_text=True))
    _assert_public_output_boundaries(parser)
    return response


def _model(client, path):
    return report_read_context(client.application, client.application.config["DATABASE_PATH"], path)


def _href(links, label, fragment=""):
    values = [link["url"] for link in links if link["label"] == label and fragment in link["url"]]
    assert len(values) == 1, (label, fragment, links)
    return values[0]


def _row_links(rows):
    return [link for row in rows for link in row["workbench_links"]]


def _assert_query_values(query, expected: Dict[str, str]) -> None:
    for key, value in expected.items():
        assert query[key] == [value], (key, query)


def _assert_queries_keep_adopted_context(*queries) -> None:
    for query in queries:
        _assert_query_values(query, COMMON_REPORT_CONTEXT)


def _assert_visible_contains_all(visible: str, texts: Tuple[str, ...]) -> None:
    for text in texts:
        assert text in visible


def _assert_visible_excludes_all(visible: str, texts: Tuple[str, ...]) -> None:
    for text in texts:
        assert text not in visible


def _utilization_link_queries(model) -> QueryMap:
    machines = _row_links(model["machine_rows"])
    operators = _row_links(model["operator_rows"])
    result = {}
    for prefix, links, resource in (("", machines, "M-RPT"), ("operator_", operators, "O-RPT")):
        for key, label in (("dispatch", "查看资源排班"), ("gantt", "定位甘特"),
                           ("overdue", "查看相关超期"), ("review", "查看计划和现场实际")):
            result[prefix + key] = _query(_href(links, label, resource))
    result["center"] = _query(_href(model["report_links"], "回报表中心"))
    for key, label in (("top_nav_overdue", "超期清单"), ("top_nav_review", "计划和现场实际")):
        result[key] = _query(_href(model["report_navigation_links"], label))
    return result

def _assert_machine_utilization_links(queries: QueryMap) -> None:
    _assert_date_from_to(queries["dispatch"])
    _assert_start_end(queries["gantt"])
    _assert_query_values(queries["dispatch"], {"period_preset": "custom", "scope_type": "machine", "machine_id": "M-RPT"})
    _assert_query_values(queries["gantt"], {"view": "machine", "gantt_resource": "M-RPT"})
    _assert_query_values(queries["overdue"], {"resource_type": "machine", "resource_id": "M-RPT"})
    _assert_query_values(queries["review"], {"resource_type": "machine", "resource_id": "M-RPT"})
    assert "date_from" not in queries["overdue"] and "date_to" not in queries["overdue"]


def _assert_operator_utilization_links(queries: QueryMap) -> None:
    _assert_date_from_to(queries["operator_dispatch"])
    _assert_start_end(queries["operator_gantt"])
    _assert_query_values(queries["operator_dispatch"], {"period_preset": "custom", "scope_type": "operator", "operator_id": "O-RPT"})
    _assert_query_values(queries["operator_gantt"], {"view": "operator", "gantt_resource": "O-RPT"})
    _assert_query_values(queries["operator_overdue"], {"resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["operator_review"], {"resource_type": "operator", "resource_id": "O-RPT"})
    assert "date_from" not in queries["operator_overdue"] and "date_to" not in queries["operator_overdue"]


def _assert_utilization_nav_context(queries: QueryMap, context) -> None:
    _assert_query_values(queries["center"], {"version": "12", "plan_role": "adopted", "date_from": "2026-05-06", "batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["top_nav_overdue"], {"resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["top_nav_review"], {"plan_role": "adopted", "batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    assert context["resource_type"] == "operator"
    assert context["resource_id"] == "O-RPT"

def _assert_utilization_export(client, export_href: str) -> None:
    export_query = _query(export_href)
    _assert_query_values(export_query, {"batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    export_resp = _read(client, export_href)
    assert export_resp.status_code == 200
    export_text = _xlsx_text(export_resp.data)
    _assert_visible_contains_all(export_text, ("M-RPT", "O-RPT"))
    _assert_visible_excludes_all(export_text, ("M-OTHER", "O-OTHER"))
    machine_rows = _xlsx_sheet_rows(export_resp.data, "设备负荷")
    operator_rows = _xlsx_sheet_rows(export_resp.data, "人员负荷")
    machine_row = next(row for row in machine_rows if row and row[0] == "M-RPT")
    operator_row = next(row for row in operator_rows if row and row[0] == "O-RPT")
    assert float(machine_row[2]) == 4.0
    assert int(machine_row[3]) == 1
    assert float(operator_row[2]) == 4.0
    assert int(operator_row[3]) == 1


def _assert_export_text(client, export_href: str, includes: Tuple[str, ...], excludes: Tuple[str, ...]):
    export_resp = _read(client, export_href)
    assert export_resp.status_code == 200
    export_text = _xlsx_text(export_resp.data)
    _assert_visible_contains_all(export_text, includes)
    _assert_visible_excludes_all(export_text, excludes)
    return export_resp


def _overdue_link_queries(model) -> QueryMap:
    links = _row_links(model["rows"])
    return {key: _query(_href(links, label, "B-RPT"))
            for key, label in (("gantt", "定位甘特"), ("dispatch", "回资源派工"),
                               ("review", "查看计划和现场实际"), ("diagnosis", "查看为什么晚了"))}

def _assert_overdue_link_context(queries: QueryMap, hidden_inputs) -> None:
    for query in (queries["dispatch"], queries["review"]):
        _assert_queries_keep_adopted_context(query)
        _assert_date_from_to(query)
        assert query["batch_id"] == ["B-RPT"]
    _assert_queries_keep_adopted_context(queries["diagnosis"])
    assert queries["diagnosis"]["batch_id"] == ["B-RPT"]
    assert "date_from" not in queries["diagnosis"] and "date_to" not in queries["diagnosis"]
    _assert_queries_keep_adopted_context(queries["gantt"])
    _assert_start_end(queries["gantt"])
    assert queries["gantt"]["gantt_batch"] == ["B-RPT"]
    _assert_query_values(hidden_inputs, {"resource_type": "machine", "resource_id": "M-RPT"})
    assert "date_from" not in hidden_inputs and "date_to" not in hidden_inputs


def _assert_overdue_operator_links(model) -> None:
    links = _row_links(model["rows"])
    operator_gantt = _query(_href(links, "定位甘特", "B-RPT"))
    operator_dispatch = _query(_href(links, "回资源派工", "B-RPT"))
    _assert_query_values(operator_gantt, {"view": "operator", "gantt_batch": "B-RPT", "gantt_resource": "O-RPT"})
    _assert_query_values(operator_dispatch, {"scope_type": "operator", "operator_id": "O-RPT", "period_preset": "custom"})

def _downtime_link_queries(model) -> QueryMap:
    links = _row_links(model["rows"])
    return {key: _query(_href(links, label))
            for key, label in (("dispatch", "查看设备排班"), ("gantt", "定位设备甘特"),
                               ("downtime", "继续看停机影响"), ("review", "查看计划和现场实际"))}

def _assert_downtime_link_context(queries: QueryMap) -> None:
    _assert_queries_keep_adopted_context(queries["dispatch"], queries["downtime"], queries["gantt"])
    _assert_date_from_to(queries["dispatch"])
    _assert_start_end(queries["downtime"])
    _assert_start_end(queries["gantt"])
    _assert_query_values(queries["dispatch"], {"period_preset": "custom", "scope_type": "machine", "machine_id": "M-RPT"})
    _assert_query_values(queries["downtime"], {"resource_type": "machine", "resource_id": "M-RPT"})
    assert queries["gantt"]["gantt_resource"] == ["M-RPT"]
    _assert_query_values(queries["review"], {"resource_type": "machine", "resource_id": "M-RPT"})


def test_reports_index_cards_keep_workbench_context() -> None:
    client = _client()
    path = ("/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
            "&query_date=2026-05-06&period_preset=week&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT")
    _old_report(client, path)
    model = _model(client, path)
    assert model["overdue_count"] == 1
    workbench = model["reports_workbench"]
    cards = {card["key"]: card for card in workbench["entry_cards"]}
    assert {card["title"] for card in cards.values()} == {"超期清单", "资源负荷与利用率", "计划和现场实际", "停机影响统计"}
    public = "\n".join(card["question_text"] + card["limitation_text"] for card in cards.values())
    _assert_visible_contains_all(public, (
        "回答哪些批次已经晚于交期", "回答哪些设备或人员在当前日期范围内最忙",
        "回答当前可复盘的正式排产记录里计划时间和现场实际反馈是否一致",
        "回答当前日期范围内哪些设备有停机记录", "当前上下文下有 1 个超期批次",
        "不能单独证明唯一原因", "当前只做设备级说明",
    ))
    overdue_query = _query(cards["overdue"]["link"]["url"])
    _assert_query_values(overdue_query, {"version": "12", "plan_role": "adopted", "batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    for key in ("query_date", "period_preset", "date_from", "date_to"):
        assert key not in overdue_query
    for key in ("utilization", "execution_review", "downtime"):
        query = _query(cards[key]["link"]["url"])
        _assert_query_values(query, {"version": "12", "plan_role": "adopted", "query_date": "2026-05-06", "period_preset": "week", "batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    _assert_start_end(_query(cards["utilization"]["link"]["url"]))
    _assert_start_end(_query(cards["downtime"]["link"]["url"]))
    _assert_date_from_to(_query(cards["execution_review"]["link"]["url"]))
    links = workbench["workbench_links"]
    _assert_query_values(_query(_href(links, "定位甘特")), {"gantt_batch": "B-RPT", "gantt_resource": "M-RPT"})
    _assert_query_values(_query(_href(links, "回资源派工")), {"scope_type": "machine", "machine_id": "M-RPT", "batch_id": "B-RPT"})
    _assert_query_values(_query(_href(links, "查看计划和现场实际")), {"plan_role": "adopted", "batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})

def test_utilization_rows_link_back_to_dispatch_gantt_and_overdue() -> None:
    client = _client()
    query = ("version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
             "&batch_id=B-RPT&resource_type=operator&resource_id=O-RPT")
    path = "/reports/utilization?" + query
    export_href = "/reports/utilization/export?" + query
    _old_report(client, path, download=export_href)
    model = _model(client, path)
    queries = _utilization_link_queries(model)
    assert [row["machine_id"] for row in model["machine_rows"]] == ["M-RPT"]
    assert [row["operator_id"] for row in model["operator_rows"]] == ["O-RPT"]
    assert "不能证明资源一定造成延期" in str(model["report_limits"])
    _assert_queries_keep_adopted_context(*queries.values())
    _assert_machine_utilization_links(queries)
    _assert_operator_utilization_links(queries)
    _assert_utilization_nav_context(queries, model["navigation_context"])
    _assert_utilization_export(client, export_href)

def test_report_filters_keep_scenario_on_submit_and_clear_when_plan_changes() -> None:
    client = _client()
    from web.routes.domains.scheduler.scheduler_plan_context_token import scenario_id_from_plan_context_token

    for name, dates in (("overdue", "date_from=2026-05-06&date_to=2026-05-06"),
                        ("utilization", "start_date=2026-05-06&end_date=2026-05-06"),
                        ("downtime", "start_date=2026-05-06&end_date=2026-05-06")):
        path = f"/reports/{name}?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT&{dates}"
        _old_report(client, path, message=IDENTITY_UNAVAILABLE, public=())
        model = _model(client, path)
        token = model["navigation_context"]["plan_context_token"]
        assert token and token != "SCENARIO-RPT"
        with client.application.app_context():
            assert scenario_id_from_plan_context_token(token) == "SCENARIO-RPT"
        changed = _model(client, f"/reports/{name}?version=12&plan_role=adopted&{dates}")
        assert not changed["navigation_context"].get("plan_context_token")
        assert not changed["navigation_context"].get("scenario_id")

def test_overdue_rows_link_to_workbench_with_batch_context() -> None:
    client = _client()
    for resource_type, resource_id in (("machine", "M-RPT"), ("operator", "O-RPT")):
        query = ("version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
                 f"&resource_type={resource_type}&resource_id={resource_id}")
        path = "/reports/overdue?" + query
        download = "/reports/overdue/export?" + query
        _old_report(client, path, download=download)
        model = _model(client, path)
        assert [row["batch_id"] for row in model["rows"]] == ["B-RPT"]
        queries = _overdue_link_queries(model)
        diagnosis = queries["diagnosis"]
        _assert_queries_keep_adopted_context(diagnosis)
        assert diagnosis["batch_id"] == ["B-RPT"]
        assert "date_from" not in diagnosis and "date_to" not in diagnosis
        exported_query = _query(model["overdue_export_url"])
        _assert_query_values(exported_query, {"resource_type": resource_type, "resource_id": resource_id})
        assert "date_from" not in exported_query and "date_to" not in exported_query
        _assert_export_text(client, download, ("B-RPT",), ("B-OTHER",))
        if resource_type == "operator":
            _assert_overdue_operator_links(model)
        else:
            _assert_overdue_link_context(queries, {"resource_type": ["machine"], "resource_id": ["M-RPT"]})

def test_overdue_batch_link_and_default_dates_keep_context() -> None:
    client = _client()
    query = "version=12&plan_role=adopted&batch_id=B-RPT"
    path = "/reports/overdue?" + query
    download = "/reports/overdue/export?" + query
    _old_report(client, path, download=download)
    model = _model(client, path)
    assert [row["batch_id"] for row in model["rows"]] == ["B-RPT"]
    assert model["navigation_context"]["batch_id"] == "B-RPT"
    diagnosis = _overdue_link_queries(model)["diagnosis"]
    assert diagnosis["batch_id"] == ["B-RPT"]
    assert "date_from" not in diagnosis and "date_to" not in diagnosis
    assert "date_from" not in _query(download) and "date_to" not in _query(download)
    _assert_export_text(client, download, ("B-RPT",), ("B-OTHER",))

def test_execution_review_stays_formal_and_links_to_site_record_entry() -> None:
    client = _client()
    query = "version=12&date_from=2026-05-06&date_to=2026-05-06"
    path = "/reports/execution-review?" + query
    download = "/reports/execution-review/export?" + query + "&plan_role=adopted"
    response = _old_report(client, path, download=download)
    assert "完整身份" not in response.get_data(as_text=True)
    model = _model(client, path)
    assert model["report_limits"] == {
        "answer_text": "这张表能回答正式计划和现场实际是否一致。",
        "limitation_text": "它不复盘模拟预览，也不在这里写现场记录。",
    }
    links = _row_links(model["rows"])
    for label in ("回资源派工", "查看现场记录入口"):
        values = _query(_href(links, label, "batch_id=B-RPT"))
        _assert_query_values(values, {"version": "12", "plan_role": "adopted", "batch_id": "B-RPT",
                                      "scope_type": "machine", "machine_id": "M-RPT", "period_preset": "custom"})
    gantt = _query(_href(links, "定位甘特", "gantt_batch=B-RPT"))
    _assert_query_values(gantt, {"view": "machine", "gantt_batch": "B-RPT", "gantt_resource": "M-RPT"})
    _assert_export_text(client, download, ("B-RPT", "B-SAME", "B-OTHER"), ("完整身份",))

def test_execution_review_without_dates_still_links_back_to_workbench() -> None:
    client = _client()
    query = "version=12&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT"
    path = "/reports/execution-review?" + query
    download = "/reports/execution-review/export?" + query + "&plan_role=adopted"
    _old_report(client, path, download=download)
    model = _model(client, path)
    assert [row["batch_id_label"] for row in model["rows"]] == ["B-RPT"]
    links = model["report_links"]
    _assert_query_values(_query(_href(links, "回报表中心")), {"date_from": "2026-05-06", "date_to": "2026-05-06", "resource_type": "machine", "resource_id": "M-RPT"})
    _assert_query_values(_query(_href(links, "定位甘特")), {"start_date": "2026-05-06", "end_date": "2026-05-06", "gantt_resource": "M-RPT"})
    _assert_query_values(_query(_href(links, "回资源派工")), {"period_preset": "custom", "machine_id": "M-RPT"})
    assert model["navigation_context"]["resource_type"] == "machine"
    assert model["navigation_context"]["resource_id"] == "M-RPT"
    assert "date_from" not in _query(download) and "date_to" not in _query(download)
    _assert_export_text(client, download, ("B-RPT",), ("B-SAME", "B-OTHER"))

def test_non_adopted_report_nav_disables_execution_review_link() -> None:
    client = _client()
    path = "/reports/utilization?version=12&plan_role=baseline_best&start_date=2026-05-06&end_date=2026-05-06"
    _old_report(client, path, message=MISSING_ROLE, public=("12", "原算法代表方案"))
    model = _model(client, path)
    review = next(link for link in model["report_navigation_links"] if link["label"] == "计划和现场实际")
    assert review["disabled"] is True and review["url"] == ""
    assert "计划和现场实际只复盘正式采用方案" in review["disabled_reason"]
    rejected = _read(client, "/reports/execution-review/export?version=12&plan_role=baseline_best")
    assert rejected.status_code == 400
    assert "计划和现场实际只复盘正式采用方案" in rejected.get_data(as_text=True)

def test_downtime_rows_use_unified_workbench_links() -> None:
    client = _client()
    query = ("version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
             "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT")
    path = "/reports/downtime?" + query
    download = "/reports/downtime/export?" + query
    _old_report(client, path, download=download)
    model = _model(client, path)
    assert [row["machine_id"] for row in model["rows"]] == ["M-RPT"]
    _assert_downtime_link_context(_downtime_link_queries(model))
    _assert_query_values(_query(download), {"batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    exported = _assert_export_text(client, download, ("M-RPT",), ("M-OTHER",))
    rows = _xlsx_sheet_rows(exported.data, "停机影响")
    row = next(row for row in rows if row and row[0] == "M-RPT")
    assert float(row[2]) == 1.0 and int(row[3]) == 1
    assert float(row[4]) == 1.0 and int(row[5]) == 1

def _insert_bad_time_report_rows() -> None:
    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        cur = conn.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("OP-BAD-TIME", "B-RPT", 99, "返修", "internal", "pending"),
        )
        bad_op_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (bad_op_id, "M-RPT", "O-RPT", "2026-05-06 99:00:00", "2026-05-06 12:30:00", "unlocked", 12),
        )
        conn.execute(
            """
            INSERT INTO MachineDowntimes (machine_id, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("M-RPT", "2026-05-06 99:00:00", "2026-05-06 12:30:00", "maintenance", "坏时间停机", "active"),
        )
        conn.commit()
    finally:
        conn.close()


def test_report_bad_time_rows_surface_degradation_on_page_and_export() -> None:
    client = _client()
    _insert_bad_time_report_rows()
    query = "version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
    for name, count in (("utilization", 1), ("downtime", 2)):
        path = f"/reports/{name}?" + query
        download = f"/reports/{name}/export?" + query
        response = _old_report(client, path, download=download)
        model = _model(client, path)
        assert model["report_bad_time_skipped_count"] == count
        assert f"已过滤 {count} 条开始或结束时间写法不对的记录" in model["report_degradation_message"]
        assert "批次号=B-RPT" in str(model["report_degradation_samples"])
        public = str(model["report_degradation_message"]) + str(model["report_degradation_samples"])
        for internal in ("99:00:00", "start_time", "end_time"):
            assert internal not in public
            assert internal not in response.get_data(as_text=True)
        exported = _read(client, download)
        assert exported.status_code == 200
        text = _xlsx_text(exported.data)
        for word in ("数据不完整", "开始或结束时间写法不对，已过滤的记录数", "批次号=B-RPT"):
            assert word in text
        assert "99:00:00" not in text

def test_utilization_and_downtime_keep_batch_context_in_page_links() -> None:
    client = _client()
    query = "version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&batch_id=B-RPT"
    for name in ("utilization", "downtime"):
        path = f"/reports/{name}?" + query
        _old_report(client, path, download=f"/reports/{name}/export?" + query)
        links = _model(client, path)["report_links"]
        assert _query(_href(links, "回报表中心"))["batch_id"] == ["B-RPT"]
        assert _query(_href(links, "定位甘特"))["gantt_batch"] == ["B-RPT"]
        assert _query(_href(links, "回资源派工"))["batch_id"] == ["B-RPT"]
        _assert_query_values(_query(_href(links, "查看计划和现场实际")), {"plan_role": "adopted", "batch_id": "B-RPT"})

def test_downtime_overlap_counts_only_real_time_intersection() -> None:
    rows = compute_downtime_impact(
        downtime_rows=[
            {"machine_id": "M-RPT", "machine_name": "一号设备", "start_time": "2026-05-06 07:59:00", "end_time": "2026-05-06 08:00:00"},
            {"machine_id": "M-RPT", "machine_name": "一号设备", "start_time": "2026-05-06 08:00:00", "end_time": "2026-05-06 08:01:00"},
            {"machine_id": "M-RPT", "machine_name": "一号设备", "start_time": "2026-05-06 12:00:00", "end_time": "2026-05-06 12:01:00"},
            {"machine_id": "M-RPT", "machine_name": "一号设备", "start_time": "2026-05-06 13:00:00", "end_time": "2026-05-06 13:01:00"},
        ],
        schedule_rows=[
            {
                "source": "internal",
                "machine_id": "M-RPT",
                "start_time": "2026-05-06 08:00:00",
                "end_time": "2026-05-06 12:00:00",
            }
        ],
        start_dt=datetime(2026, 5, 6, 0, 0, 0),
        end_dt_excl=datetime(2026, 5, 7, 0, 0, 0),
    )

    assert rows[0]["downtime_hours"] == 0.07
    assert rows[0]["downtime_count"] == 4
    assert rows[0]["schedule_overlap_hours"] == 0.02
    assert rows[0]["schedule_overlap_count"] == 1


def test_report_reversed_time_rows_surface_degradation() -> None:
    collector = DegradationCollector()
    machine_rows, operator_rows = compute_utilization(
        schedule_rows=[
            {
                "batch_id": "B-REVERSED",
                "source": "internal",
                "machine_id": "M-RPT",
                "operator_id": "O-RPT",
                "start_time": "2026-05-06 10:00:00",
                "end_time": "2026-05-06 09:00:00",
            }
        ],
        start_dt=datetime(2026, 5, 6, 0, 0, 0),
        end_dt_excl=datetime(2026, 5, 7, 0, 0, 0),
        cap_hours=8.0,
        degradation_collector=collector,
    )

    assert machine_rows == []
    assert operator_rows == []
    assert collector.to_counters()["bad_time_row_skipped"] == 1

    collector = DegradationCollector()
    downtime_rows = compute_downtime_impact(
        downtime_rows=[
            {
                "machine_id": "M-RPT",
                "machine_name": "一号设备",
                "start_time": "2026-05-06 10:00:00",
                "end_time": "2026-05-06 09:00:00",
            }
        ],
        schedule_rows=[
            {
                "batch_id": "B-REVERSED",
                "source": "internal",
                "machine_id": "M-RPT",
                "start_time": "2026-05-06 08:00:00",
                "end_time": "2026-05-06 07:00:00",
            }
        ],
        start_dt=datetime(2026, 5, 6, 0, 0, 0),
        end_dt_excl=datetime(2026, 5, 7, 0, 0, 0),
        degradation_collector=collector,
    )

    assert downtime_rows == []
    assert collector.to_counters()["bad_time_row_skipped"] == 2


def test_downtime_context_filter_treats_reversed_time_as_bad_time() -> None:
    rows = filter_downtime_rows_for_report_context(
        [
            {
                "machine_id": "M-RPT",
                "start_time": "2026-05-06 10:00:00",
                "end_time": "2026-05-06 09:00:00",
            }
        ],
        [
            {
                "batch_id": "B-RPT",
                "source": "internal",
                "machine_id": "M-RPT",
                "start_time": "2026-05-06 08:00:00",
                "end_time": "2026-05-06 12:00:00",
            }
        ],
        batch_id="B-RPT",
    )

    assert rows == []


def test_downtime_empty_state_is_conservative() -> None:
    client = _client()
    query = "version=12&plan_role=adopted&start_date=2026-05-08&end_date=2026-05-08"
    path = "/reports/downtime?" + query
    download = "/reports/downtime/export?" + query
    response = _old_report(client, path, download=download)
    model = _model(client, path)
    assert model["rows"] == []
    assert "当前没有停机记录或尚未维护停机数据" in model["downtime_empty_message"]
    assert "当前不能证明具体影响了哪一道任务" in str(model["report_limits"])
    for word in ("当前范围内没有停机记录", "涉及设备\n0 台", "停机时长\n0 小时", "与排程重叠\n0 小时"):
        assert word not in response.get_data(as_text=True)
    exported = _read(client, download)
    assert exported.status_code == 400
    assert "暂无数据，不能导出" in exported.get_data(as_text=True)

def test_report_exports_hide_internal_field_headers() -> None:
    client = _client()

    _assert_export_headers_hide_internal_tokens(client)
    execution_resp = client.get("/reports/execution-review/export?version=12&date_from=2026-05-06&date_to=2026-05-06&batch_id=B-RPT")
    assert execution_resp.status_code == 200
    execution_text = _xlsx_text(execution_resp.data)
    assert "B-RPT" in execution_text
    assert "B-OTHER" not in execution_text
    assert "完整身份" not in execution_text
    downtime_resp = client.get(
        "/reports/downtime/export?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=machine&resource_id=M-RPT"
    )
    assert downtime_resp.status_code == 200
    downtime_text = _xlsx_text(downtime_resp.data)
    assert "M-RPT" in downtime_text
    assert "M-OTHER" not in downtime_text
    invalid = client.get("/reports/utilization?version=12&start_date=2026-05-06&end_date=2026-05-06&resource_type=team&resource_id=T-RPT")
    assert invalid.status_code == 400
    assert_rejected(invalid)
    invalid_export = client.get(
        "/reports/utilization/export?version=12&start_date=2026-05-06&end_date=2026-05-06&resource_type=team&resource_id=T-RPT"
    )
    assert invalid_export.status_code == 400
    assert "当前报表暂不支持班组维度筛选" in invalid_export.get_data(as_text=True)
