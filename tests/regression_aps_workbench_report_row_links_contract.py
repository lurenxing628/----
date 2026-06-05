from __future__ import annotations

from typing import Dict, List

from tests.reports_workbench_backlink_helpers import (
    _client,
    _href_with_text_and_fragment,
    _parser_for,
    _query,
)


def _assert_query_values(query: Dict[str, List[str]], expected: Dict[str, str]) -> None:
    for key, value in expected.items():
        assert query[key] == [value], (key, query)


def test_workbench_report_rows_keep_batch_and_resource_context_when_returning_to_action_pages() -> None:
    client = _client()

    _assert_overdue_row_workbench_links(client)
    _assert_utilization_row_workbench_links(client)


def _assert_overdue_row_workbench_links(client) -> None:
    overdue = _parser_for(
        client,
        "/reports/overdue?version=12&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06"
        "&batch_id=B-RPT&resource_type=machine&resource_id=M-RPT",
    )
    gantt = _query(_href_with_text_and_fragment(overdue, "定位甘特", "/scheduler/gantt", "gantt_batch=B-RPT"))
    dispatch = _query(_href_with_text_and_fragment(overdue, "回资源派工", "/scheduler/resource-dispatch", "batch_id=B-RPT"))

    _assert_query_values(
        gantt,
        {
            "version": "12",
            "plan_role": "adopted",
            "start_date": "2026-05-06",
            "end_date": "2026-05-06",
            "gantt_batch": "B-RPT",
            "gantt_resource": "M-RPT",
        },
    )
    _assert_query_values(
        dispatch,
        {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "scope_type": "machine",
            "machine_id": "M-RPT",
        },
    )


def _assert_utilization_row_workbench_links(client) -> None:
    utilization = _parser_for(
        client,
        "/reports/utilization?version=12&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=operator&resource_id=O-RPT",
    )
    row_dispatch = _query(
        _href_with_text_and_fragment(utilization, "查看资源排班", "/scheduler/resource-dispatch", "operator_id=O-RPT")
    )
    row_gantt = _query(_href_with_text_and_fragment(utilization, "定位甘特", "/scheduler/gantt", "gantt_resource=O-RPT"))

    _assert_query_values(
        row_dispatch,
        {
            "version": "12",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "scope_type": "operator",
            "operator_id": "O-RPT",
        },
    )
    _assert_query_values(
        row_gantt,
        {
            "start_date": "2026-05-06",
            "end_date": "2026-05-06",
            "view": "operator",
            "gantt_resource": "O-RPT",
        },
    )
