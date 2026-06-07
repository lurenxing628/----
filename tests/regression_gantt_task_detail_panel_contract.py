"""回归测试：甘特任务详情面板契约——build_tasks/关键链对外用「顺序（工种）」公共标签而不泄露内部 op_id，任务 meta 显示现场实际开完工与执行状态，详情链接保留 version/plan_role/batch 等上下文并在模拟预览或非正式方案时禁用「查看资源排班/计划和现场实际」且不泄露 scenario_id，模板与 aps_gantt.css 维持稳定的详情面板布局。"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from core.services.scheduler.gantt_critical_chain import compute_critical_chain_from_rows
from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_tasks import build_tasks
from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _json,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _gantt_data(client, *, plan_role: str = "adopted") -> dict:
    resp = client.get(
        "/scheduler/gantt/data"
        f"?view=machine&start_date=2026-05-01&end_date=2026-05-01&version=2&plan_role={plan_role}"
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = _json(resp)
    assert payload["success"] is True
    return payload["data"]


def _first_task(data: dict) -> dict:
    tasks = data.get("tasks") or []
    assert tasks, data
    return tasks[0]


def _links_by_label(meta: dict) -> dict:
    return {link["label"]: link for link in meta["detail_links"]}


def _assert_url_contains_all(url: str, values: Tuple[str, ...]) -> None:
    for value in values:
        assert value in url


def test_gantt_task_public_title_does_not_use_internal_op_id_fallback() -> None:
    wr = resolve_week_range(start_date="2026-05-01", end_date="2026-05-01")
    outcome = build_tasks(
        view="machine",
        wr=wr,
        rows=[
            {
                "schedule_id": 9001,
                "op_id": 123,
                "op_code": "",
                "batch_id": "B1",
                "piece_id": "piece-a",
                "part_no": "",
                "part_name": "",
                "seq": 20,
                "op_type_name": "车削",
                "source": "internal",
                "op_status": "scheduled",
                "machine_id": "M1",
                "machine_name": "一号设备",
                "operator_id": "O1",
                "operator_name": "张三",
                "priority": "normal",
                "lock_status": "locked",
                "start_time": "2026-05-01 08:00:00",
                "end_time": "2026-05-01 09:00:00",
                "due_date": "2026-05-01",
            }
        ],
        overdue_set=set(),
    )

    tasks = outcome.value
    assert len(tasks) == 1
    task = tasks[0]
    assert task["id"] == "op_123"
    assert "op_123" not in task["name"]
    assert task["name"].startswith("20（车削）")
    assert task["meta"]["task_label"] == "20（车削）"
    assert "op_123" not in task["meta"]["detail_title"]


def test_critical_chain_edges_keep_internal_ids_but_expose_public_labels() -> None:
    rows = [
        {
            "schedule_id": 9001,
            "op_id": 111,
            "op_code": "",
            "batch_id": "B1",
            "piece_id": "piece-a",
            "part_no": "P001",
            "part_name": "零件一",
            "seq": 10,
            "op_type_name": "车削",
            "machine_id": "M1",
            "operator_id": "O1",
            "start_time": "2026-05-01 08:00:00",
            "end_time": "2026-05-01 09:00:00",
        },
        {
            "schedule_id": 9002,
            "op_id": 222,
            "op_code": "",
            "batch_id": "B1",
            "piece_id": "piece-a",
            "part_no": "P001",
            "part_name": "零件一",
            "seq": 20,
            "op_type_name": "精加工",
            "machine_id": "M1",
            "operator_id": "O1",
            "start_time": "2026-05-01 09:00:00",
            "end_time": "2026-05-01 10:00:00",
        },
    ]

    critical_chain = compute_critical_chain_from_rows(rows)
    assert critical_chain["ids"] == ["op_111", "op_222"]
    assert len(critical_chain["edges"]) == 1
    edge = critical_chain["edges"][0]
    assert edge["from"] == "op_111"
    assert edge["to"] == "op_222"
    assert edge["from_label"] == "10（车削）"
    assert edge["to_label"] == "20（精加工）"
    assert "op_" not in edge["from_label"]
    assert "op_" not in edge["to_label"]


def test_gantt_task_meta_uses_execution_facts_and_keeps_no_record_state(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    before = _first_task(_gantt_data(client))["meta"]
    assert before["actual_summary_label"] == "暂未记录现场实际"
    assert before["actual_start_time"] == ""
    assert before["actual_end_time"] == ""
    assert before["execution_status_label"] == "待开工"

    card = _current_card(client)
    actual_resp = client.post(
        f"/scheduler/resource-dispatch/execution/tasks/{card['task_key']}/actual?{_current_query()}",
        json=_base_payload(
            card,
            idempotency_key="gantt-detail-actual-times",
            actual_start_time="2026-05-01 08:12:00",
            actual_finish_time="2026-05-01 08:58:00",
            quantity_done=10,
        ),
    )
    assert actual_resp.status_code == 200, actual_resp.get_data(as_text=True)

    after = _first_task(_gantt_data(client))["meta"]
    assert after["actual_start_time"] == "2026-05-01 08:12:00"
    assert after["actual_end_time"] == "2026-05-01 08:58:00"
    assert after["actual_start_time_label"] == "2026-05-01 08:12:00"
    assert after["actual_end_time_label"] == "2026-05-01 08:58:00"
    assert after["execution_status_label"] == "已完工"
    assert "实际开工：2026-05-01 08:12:00" in after["actual_summary_label"]
    assert "实际完工：2026-05-01 08:58:00" in after["actual_summary_label"]


def test_gantt_task_detail_links_preserve_context_and_guard_execution_review(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    adopted_meta = _first_task(_gantt_data(client, plan_role="adopted"))["meta"]
    adopted_links = _links_by_label(adopted_meta)
    assert adopted_links["查看资源排班"]["disabled"] is False
    _assert_url_contains_all(
        adopted_links["查看资源排班"]["url"],
        (
            "version=2",
            "plan_role=adopted",
            "period_preset=custom",
            "date_from=2026-05-01",
            "date_to=2026-05-01",
            "batch_id=B1",
            "scope_type=machine",
            "machine_id=M1",
        ),
    )
    assert adopted_links["查看计划和现场实际"]["disabled"] is False

    comparison_meta = _first_task(_gantt_data(client, plan_role="baseline_best"))["meta"]
    comparison_links = _links_by_label(comparison_meta)
    assert comparison_links["查看资源排班"]["disabled"] is False
    assert "plan_role=baseline_best" in comparison_links["查看资源排班"]["url"]
    assert comparison_links["查看计划和现场实际"]["disabled"] is True
    assert comparison_links["查看计划和现场实际"]["url"] == ""
    assert "正式采用方案" in comparison_links["查看计划和现场实际"]["disabled_reason"]


def test_gantt_task_detail_preview_links_do_not_leak_scenario_id() -> None:
    from web.viewmodels.scheduler_gantt_task_detail import decorate_gantt_task_detail_payload

    payload = decorate_gantt_task_detail_payload(
        {
            "version": 12,
            "view": "machine",
            "week_start": "2026-05-06",
            "week_end": "2026-05-06",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "scenario_id": "SC-SECRET",
            "scenario_display_name": "模拟方案",
            "is_scenario_preview": True,
            "can_write_feedback": False,
            "tasks": [
                {
                    "meta": {
                        "batch_id": "B-RPT",
                        "machine_id": "M-RPT",
                        "machine": "测试设备",
                    }
                }
            ],
        }
    )
    links = payload["tasks"][0]["meta"]["detail_links"]
    by_label = {link["label"]: link for link in links}

    assert links
    assert by_label["查看资源排班"]["disabled"] is True
    assert by_label["查看资源排班"]["url"] == ""
    assert "模拟预览" in by_label["查看资源排班"]["disabled_reason"]
    assert by_label["查看超期清单"]["disabled"] is True
    assert by_label["查看超期清单"]["url"] == ""
    assert "模拟预览" in by_label["查看超期清单"]["disabled_reason"]
    assert by_label["查看计划和现场实际"]["disabled"] is True
    assert by_label["查看计划和现场实际"]["url"] == ""
    assert "正式采用方案" in by_label["查看计划和现场实际"]["disabled_reason"]
    assert "SC-SECRET" not in str(links)
    assert "scenario_id" not in str(links)


def test_gantt_task_detail_links_explain_summary_parse_failure() -> None:
    from web.viewmodels.scheduler_gantt_task_detail import decorate_gantt_task_detail_payload

    payload = decorate_gantt_task_detail_payload(
        {
            "version": 12,
            "view": "machine",
            "week_start": "2026-05-06",
            "week_end": "2026-05-06",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "is_current_executable_official_version": True,
            "can_dispatch": True,
            "can_write_feedback": True,
            "result_summary_parse_failed": True,
            "result_summary_parse_reason": "排产摘要缺失",
            "tasks": [
                {
                    "meta": {
                        "batch_id": "B-RPT",
                        "machine_id": "M-RPT",
                        "machine": "测试设备",
                    }
                }
            ],
        }
    )
    links = {link["label"]: link for link in payload["tasks"][0]["meta"]["detail_links"]}

    assert links["查看资源排班"]["disabled"] is False
    assert links["查看计划和现场实际"]["disabled"] is True
    assert links["查看计划和现场实际"]["url"] == ""
    assert "当前排产摘要读取失败" in links["查看计划和现场实际"]["disabled_reason"]
    assert "排产摘要缺失" in links["查看计划和现场实际"]["disabled_reason"]
