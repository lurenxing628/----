"""回归测试：报表中心各页（超期/资源利用率/停机影响/计划和现场实际）的卡片与行内回链须保留工作台上下文（version/plan_role/批次/资源/日期范围）并在各回链 URL 携带正确查询参数；导出 Excel 只含筛选目标行、隐藏内部字段表头；非 adopted 方案禁用「计划和现场实际」链接；停机重叠时长只按真实时间交集计数（compute_downtime_impact）。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from core.services.report.downtime_impact import compute_downtime_impact
from tests.reports_workbench_backlink_helpers import (
    REPO_ROOT,
    _assert_date_from_to,
    _assert_export_headers_hide_internal_tokens,
    _assert_public_output_boundaries,
    _assert_start_end,
    _client,
    _href_for_report_card,
    _href_with_text,
    _href_with_text_and_fragment,
    _html_for,
    _input_values,
    _parser_for,
    _query,
    _visible_text,
    _xlsx_sheet_rows,
    _xlsx_text,
)

COMMON_REPORT_CONTEXT = {
    "version": "12",
    "plan_role": "adopted",
}
Query = Dict[str, List[str]]
QueryMap = Dict[str, Query]


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


def _utilization_link_queries(parser) -> QueryMap:
    return {
        "dispatch": _query(_href_with_text_and_fragment(parser, "查看资源排班", "/scheduler/resource-dispatch", "machine_id=M-RPT")),
        "gantt": _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_resource=M-RPT")),
        "overdue": _query(_href_with_text_and_fragment(parser, "查看相关超期", "/reports/overdue", "resource_id=M-RPT")),
        "review": _query(_href_with_text_and_fragment(parser, "查看计划和现场实际", "/reports/execution-review", "resource_id=M-RPT")),
        "operator_dispatch": _query(_href_with_text_and_fragment(parser, "查看资源排班", "/scheduler/resource-dispatch", "operator_id=O-RPT")),
        "operator_gantt": _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_resource=O-RPT")),
        "operator_overdue": _query(_href_with_text_and_fragment(parser, "查看相关超期", "/reports/overdue", "resource_id=O-RPT")),
        "operator_review": _query(_href_with_text_and_fragment(parser, "查看计划和现场实际", "/reports/execution-review", "resource_id=O-RPT")),
        "center": _query(_href_with_text(parser, "报表中心", "/reports/")),
        "top_nav_overdue": _query(_href_with_text(parser, "超期清单", "/reports/overdue")),
        "top_nav_review": _query(_href_with_text(parser, "计划和现场实际", "/reports/execution-review")),
    }


def _assert_machine_utilization_links(queries: QueryMap) -> None:
    _assert_date_from_to(queries["dispatch"])
    _assert_start_end(queries["gantt"])
    _assert_date_from_to(queries["overdue"])
    _assert_query_values(queries["dispatch"], {"period_preset": "custom", "scope_type": "machine", "machine_id": "M-RPT"})
    _assert_query_values(queries["gantt"], {"view": "machine", "gantt_resource": "M-RPT"})
    _assert_query_values(queries["overdue"], {"resource_type": "machine", "resource_id": "M-RPT"})
    _assert_query_values(queries["review"], {"resource_type": "machine", "resource_id": "M-RPT"})


def _assert_operator_utilization_links(queries: QueryMap) -> None:
    _assert_date_from_to(queries["operator_dispatch"])
    _assert_start_end(queries["operator_gantt"])
    _assert_date_from_to(queries["operator_overdue"])
    _assert_query_values(queries["operator_dispatch"], {"period_preset": "custom", "scope_type": "operator", "operator_id": "O-RPT"})
    _assert_query_values(queries["operator_gantt"], {"view": "operator", "gantt_resource": "O-RPT"})
    _assert_query_values(queries["operator_overdue"], {"resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["operator_review"], {"resource_type": "operator", "resource_id": "O-RPT"})


def _assert_utilization_nav_context(queries: QueryMap, hidden_inputs) -> None:
    _assert_query_values(queries["center"], {"version": "12", "plan_role": "adopted", "date_from": "2026-05-06", "batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["top_nav_overdue"], {"resource_type": "operator", "resource_id": "O-RPT"})
    _assert_query_values(queries["top_nav_review"], {"plan_role": "adopted", "batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    assert hidden_inputs["resource_type"] == ["operator"]
    assert hidden_inputs["resource_id"] == ["O-RPT"]


def _assert_utilization_export(client, export_href: str) -> None:
    export_query = _query(export_href)
    _assert_query_values(export_query, {"batch_id": "B-RPT", "resource_type": "operator", "resource_id": "O-RPT"})
    export_resp = client.get(export_href)
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
    export_resp = client.get(export_href)
    assert export_resp.status_code == 200
    export_text = _xlsx_text(export_resp.data)
    _assert_visible_contains_all(export_text, includes)
    _assert_visible_excludes_all(export_text, excludes)
    return export_resp


def _overdue_link_queries(parser) -> QueryMap:
    return {
        "gantt": _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT")),
        "dispatch": _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT")),
        "review": _query(_href_with_text_and_fragment(parser, "查看计划和现场实际", "/reports/execution-review", "batch_id=B-RPT")),
        "diagnosis": _query(_href_with_text_and_fragment(parser, "查看为什么晚了", "/reports/overdue", "batch_id=B-RPT")),
    }


def _assert_overdue_link_context(queries: QueryMap, hidden_inputs) -> None:
    for query in (queries["dispatch"], queries["review"], queries["diagnosis"]):
        _assert_queries_keep_adopted_context(query)
        _assert_date_from_to(query)
        assert query["batch_id"] == ["B-RPT"]
    _assert_queries_keep_adopted_context(queries["gantt"])
    _assert_start_end(queries["gantt"])
    assert queries["gantt"]["gantt_batch"] == ["B-RPT"]
    _assert_query_values(hidden_inputs, {"date_from": "2026-05-06", "date_to": "2026-05-06", "resource_type": "machine", "resource_id": "M-RPT"})


def _assert_overdue_operator_links(parser) -> None:
    operator_gantt = _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    operator_dispatch = _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
    _assert_query_values(operator_gantt, {"view": "operator", "gantt_batch": "B-RPT", "gantt_resource": "O-RPT"})
    _assert_query_values(operator_dispatch, {"scope_type": "operator", "operator_id": "O-RPT", "period_preset": "custom"})


def _downtime_link_queries(parser) -> QueryMap:
    return {
        "dispatch": _query(_href_with_text(parser, "查看设备排班", "/scheduler/resource-dispatch")),
        "gantt": _query(_href_with_text(parser, "定位设备甘特", "/scheduler/gantt")),
        "downtime": _query(_href_with_text(parser, "继续看停机影响", "/reports/downtime")),
        "review": _query(_href_with_text(parser, "查看计划和现场实际", "/reports/execution-review")),
    }


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
    parser = _parser_for(
        client,
        "/reports/?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&query_date=2026-05-06&period_preset=week&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )

    _assert_visible_contains_all(
        _visible_text(parser),
        (
            "回答哪些批次已经晚于交期",
            "回答哪些设备或人员在当前日期范围内最忙",
            "回答当前可复盘的正式排产记录里计划时间和现场实际反馈是否一致",
            "回答当前日期范围内哪些设备有停机记录",
            "当前上下文下有 1 个超期批次",
            "不能单独证明唯一原因",
            "当前只做设备级说明",
        ),
    )
    report_card_attrs = [link.get("data-report-card") for link in parser.links if link.get("data-report-card")]
    assert {"超期清单", "资源负荷与利用率", "计划和现场实际", "停机影响统计"} <= set(report_card_attrs)
    assert not {"overdue", "utilization", "execution_review", "downtime"} & set(report_card_attrs)
    for card_key, target_path in (
        ("overdue", "/reports/overdue"),
        ("utilization", "/reports/utilization"),
        ("execution_review", "/reports/execution-review"),
        ("downtime", "/reports/downtime"),
    ):
        query = _query(_href_for_report_card(parser, card_key, target_path))
        _assert_query_values(query, {"version": "12", "plan_role": "adopted", "query_date": "2026-05-06", "period_preset": "week", "batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    _assert_date_from_to(_query(_href_for_report_card(parser, "overdue", "/reports/overdue")))
    _assert_start_end(_query(_href_for_report_card(parser, "utilization", "/reports/utilization")))
    _assert_date_from_to(_query(_href_for_report_card(parser, "execution_review", "/reports/execution-review")))
    _assert_start_end(_query(_href_for_report_card(parser, "downtime", "/reports/downtime")))
    page_gantt = _query(_href_with_text(parser, "定位甘特", "/scheduler/gantt"))
    page_dispatch = _query(_href_with_text(parser, "回资源派工", "/scheduler/resource-dispatch"))
    page_review = _query(_href_with_text(parser, "查看计划和现场实际", "/reports/execution-review"))
    _assert_query_values(page_gantt, {"gantt_batch": "B-RPT", "gantt_resource": "M-RPT"})
    _assert_query_values(page_dispatch, {"scope_type": "machine", "machine_id": "M-RPT", "batch_id": "B-RPT"})
    _assert_query_values(page_review, {"plan_role": "adopted", "batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    _assert_public_output_boundaries(parser)


def test_utilization_rows_link_back_to_dispatch_gantt_and_overdue() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/utilization?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&batch_id=B-RPT&resource_type=operator&resource_id=O-RPT",
    )
    visible = _visible_text(parser)
    queries = _utilization_link_queries(parser)
    export_href = _href_with_text_and_fragment(parser, "导出 Excel", "/reports/utilization/export", "resource_id=O-RPT")
    hidden_inputs = _input_values(parser)

    _assert_visible_contains_all(visible, ("继续处理", "不能证明资源一定造成延期"))
    _assert_visible_excludes_all(visible, ("M-OTHER", "O-OTHER"))
    _assert_queries_keep_adopted_context(*queries.values())
    _assert_machine_utilization_links(queries)
    _assert_operator_utilization_links(queries)
    _assert_utilization_nav_context(queries, hidden_inputs)
    _assert_utilization_export(client, export_href)
    _assert_public_output_boundaries(parser)


def test_report_filters_keep_scenario_on_submit_and_clear_when_plan_changes() -> None:
    script = (REPO_ROOT / "static" / "js" / "report_plan_filter.js").read_text(encoding="utf-8")
    assert all(token in script for token in ("[data-report-plan-role-select]", "[data-report-plan-version-select]", 'input[name="scenario_id"]', "data-initial-version", "submit"))
    for rel_path in ("overdue.html", "utilization.html", "downtime.html"):
        source = (REPO_ROOT / "templates" / "reports" / rel_path).read_text(encoding="utf-8")
        assert "'scenario_id'" not in source.split("preserved_report_context_inputs", 1)[1].split(")", 1)[0]
        assert all(token in source for token in ("data-report-plan-role-select", "data-report-plan-version-select", "report_plan_filter.js"))
    overdue_source = (REPO_ROOT / "templates" / "reports" / "overdue.html").read_text(encoding="utf-8")
    assert "r.quantity or '-'" not in overdue_source
    assert "r.quantity if r.quantity is not none else '-'" in overdue_source
    client = _client()
    for path in (
        "/reports/overdue?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT&date_from=2026-05-06&date_to=2026-05-06",
        "/reports/utilization?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT&start_date=2026-05-06&end_date=2026-05-06",
        "/reports/downtime?version=12&plan_role=adopted&scenario_id=SCENARIO-RPT&start_date=2026-05-06&end_date=2026-05-06",
    ):
        parser = _parser_for(client, path)
        assert _input_values(parser)["scenario_id"] == ["SCENARIO-RPT"]


def test_overdue_rows_link_to_workbench_with_batch_context() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&resource_type=machine&resource_id=M-RPT",
    )
    visible = _visible_text(parser)

    _assert_visible_contains_all(visible, ("继续处理", "查看为什么晚了", "B-RPT"))
    _assert_visible_excludes_all(visible, ("B-OTHER",))
    queries = _overdue_link_queries(parser)
    export_href = _href_with_text_and_fragment(parser, "导出 Excel", "/reports/overdue/export", "resource_id=M-RPT")
    export_query = _query(export_href)
    hidden_inputs = _input_values(parser)
    _assert_overdue_link_context(queries, hidden_inputs)
    _assert_query_values(export_query, {"resource_type": "machine", "resource_id": "M-RPT"})
    _assert_export_text(client, export_href, ("B-RPT",), ("B-OTHER",))

    operator_parser = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&resource_type=operator&resource_id=O-RPT",
    )
    _assert_overdue_operator_links(operator_parser)
    _assert_public_output_boundaries(operator_parser)
    _assert_public_output_boundaries(parser)


def test_overdue_batch_link_and_default_dates_keep_context() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/overdue?version=12&plan_role=adopted&batch_id=B-RPT")
    visible = _visible_text(parser)
    hidden_inputs = _input_values(parser)

    assert "B-RPT" in visible
    assert "B-OTHER" not in visible
    assert hidden_inputs["batch_id"] == ["B-RPT"]
    center = _query(_href_with_text(parser, "回报表中心", "/reports/"))
    gantt = _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    dispatch = _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
    assert center["batch_id"] == ["B-RPT"]
    assert center["date_from"] == ["2026-05-06"]
    assert center["date_to"] == ["2026-05-06"]
    assert gantt["start_date"] == ["2026-05-06"]
    assert gantt["end_date"] == ["2026-05-06"]
    assert dispatch["period_preset"] == ["custom"]
    _assert_public_output_boundaries(parser)


def test_execution_review_stays_formal_and_links_to_site_record_entry() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/execution-review?version=12&date_from=2026-05-06&date_to=2026-05-06")
    visible = _visible_text(parser)

    assert "这张表只展示当前筛选出的排产记录和现场实际" in visible
    assert "查看现场记录入口" in visible
    assert "完整身份" not in visible
    dispatch = _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
    gantt = _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    site_record = _query(_href_with_text_and_fragment(parser, "查看现场记录入口", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
    for query in (dispatch, site_record):
        assert query["version"] == ["12"]
        assert query["plan_role"] == ["adopted"]
        assert query["batch_id"] == ["B-RPT"]
        assert query["scope_type"] == ["machine"]
        assert query["machine_id"] == ["M-RPT"]
        assert query["period_preset"] == ["custom"]
    assert gantt["view"] == ["machine"]
    assert gantt["gantt_batch"] == ["B-RPT"]
    assert gantt["gantt_resource"] == ["M-RPT"]
    _assert_public_output_boundaries(parser)

def test_execution_review_without_dates_still_links_back_to_workbench() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/execution-review?version=12&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT")
    hidden_inputs = _input_values(parser)
    visible = _visible_text(parser)

    assert "B-RPT" in visible
    assert "B-SAME" not in visible
    assert "B-OTHER" not in visible
    center = _query(_href_with_text(parser, "回报表中心", "/reports/"))
    gantt = _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    dispatch = _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
    export_href = _href_with_text_and_fragment(parser, "导出 Excel", "/reports/execution-review/export", "resource_id=M-RPT")
    _assert_query_values(center, {"date_from": "2026-05-06", "date_to": "2026-05-06", "resource_type": "machine", "resource_id": "M-RPT"})
    _assert_query_values(gantt, {"start_date": "2026-05-06", "end_date": "2026-05-06", "gantt_resource": "M-RPT"})
    _assert_query_values(dispatch, {"period_preset": "custom", "machine_id": "M-RPT"})
    _assert_query_values(hidden_inputs, {"resource_type": "machine", "resource_id": "M-RPT"})
    _assert_export_text(client, export_href, ("B-RPT",), ("B-SAME", "B-OTHER"))
    _assert_public_output_boundaries(parser)


def test_non_adopted_report_nav_disables_execution_review_link() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/utilization?version=12&plan_role=baseline_best&start_date=2026-05-06&end_date=2026-05-06")
    html_text = _html_for(client, "/reports/utilization?version=12&plan_role=baseline_best&start_date=2026-05-06&end_date=2026-05-06")

    assert "计划和现场实际只复盘正式采用方案" in html_text
    assert 'aria-disabled="true"' in html_text
    assert "is-disabled" in html_text
    assert "/reports/execution-review?version=12&amp;plan_role=baseline_best" not in html_text
    assert not any(
        link["text"].strip() == "计划和现场实际" and urlparse(link["href"]).path == "/reports/execution-review"
        for link in parser.links
    )


def test_downtime_rows_use_unified_workbench_links() -> None:
    client = _client()
    parser = _parser_for(
        client,
        "/reports/downtime?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    visible = _visible_text(parser)

    assert "M-OTHER" not in visible
    queries = _downtime_link_queries(parser)
    export_href = _href_with_text_and_fragment(parser, "导出 Excel", "/reports/downtime/export", "resource_id=M-RPT")
    _assert_downtime_link_context(queries)
    export_query = _query(export_href)
    _assert_query_values(export_query, {"batch_id": "B-RPT", "resource_type": "machine", "resource_id": "M-RPT"})
    export_resp = _assert_export_text(client, export_href, ("M-RPT",), ("M-OTHER",))
    downtime_rows = _xlsx_sheet_rows(export_resp.data, "停机影响")
    downtime_row = next(row for row in downtime_rows if row and row[0] == "M-RPT")
    assert float(downtime_row[2]) == 1.0
    assert int(downtime_row[3]) == 1
    assert float(downtime_row[4]) == 1.0
    assert int(downtime_row[5]) == 1
    _assert_public_output_boundaries(parser)


def test_utilization_and_downtime_keep_batch_context_in_page_links() -> None:
    client = _client()
    utilization_parser = _parser_for(
        client,
        "/reports/utilization?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&batch_id=B-RPT",
    )
    downtime_parser = _parser_for(
        client,
        "/reports/downtime?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&batch_id=B-RPT",
    )

    for parser in (utilization_parser, downtime_parser):
        center = _query(_href_with_text(parser, "回报表中心", "/reports/"))
        gantt = _query(_href_with_text_and_fragment(parser, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
        dispatch = _query(_href_with_text_and_fragment(parser, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))
        review = _query(_href_with_text_and_fragment(parser, "查看计划和现场实际", "/reports/execution-review", "batch_id=B-RPT"))
        assert center["batch_id"] == ["B-RPT"]
        assert gantt["gantt_batch"] == ["B-RPT"]
        assert dispatch["batch_id"] == ["B-RPT"]
        assert review["plan_role"] == ["adopted"]
        assert review["batch_id"] == ["B-RPT"]
        _assert_public_output_boundaries(parser)


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


def test_downtime_empty_state_is_conservative() -> None:
    client = _client()
    parser = _parser_for(client, "/reports/downtime?version=12&plan_role=adopted&start_date=2026-05-08&end_date=2026-05-08")
    visible = _visible_text(parser)

    assert "当前没有停机记录或尚未维护停机数据" in visible
    assert "当前不能证明具体影响了哪一道任务" in visible
    assert "当前范围内没有停机记录" not in visible
    assert "涉及设备\n0 台" not in visible
    assert "停机时长\n0 小时" not in visible
    assert "与排程重叠\n0 小时" not in visible
    _assert_public_output_boundaries(parser)


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
    assert "当前报表暂不支持班组维度筛选" in invalid.get_data(as_text=True)
    invalid_export = client.get(
        "/reports/utilization/export?version=12&start_date=2026-05-06&end_date=2026-05-06&resource_type=team&resource_id=T-RPT"
    )
    assert invalid_export.status_code == 400
