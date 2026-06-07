"""回归测试：web 视图层的数值/解析容错不得静默吞坏值——分析趋势/候选对比/诊断/报表导出/系统任务等 helper 只对可解析的空值用默认或标 parse_failed，遇坏布尔、NaN/Infinity、非整数导出行数等会显式抛 ValidationError/ReportPresentationValueError 或显示「记录异常/无法安全展示」而不泄漏原始坏值；result_summary 解析失败会关闭 can_dispatch/can_write_feedback 并给出护栏文案；week_plan/分析模板用公开展示标签而非裸 result_status/strategy 回退。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, g

from core.infrastructure.errors import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]


class _ExplodingFloat:
    def __float__(self):
        raise RuntimeError("float conversion exploded")


class _ExplodingHistoryRow:
    def to_dict(self):
        raise RuntimeError("history row conversion exploded")


def _string_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)
    elif isinstance(value, str):
        yield value


def test_scheduler_trend_numeric_helpers_only_swallow_parse_errors() -> None:
    from web.viewmodels import scheduler_analysis_trends as trends

    assert trends.safe_float("bad", default=7.5) == 7.5
    assert trends.safe_int("bad", default=7) == 7
    assert trends.safe_float(True, default=7.5) == 7.5
    assert trends.safe_int(False, default=7) == 7
    assert trends._metric_float_state(True) == (None, True)
    assert trends._int_state(False) == (None, True)

    with pytest.raises(RuntimeError, match="float conversion exploded"):
        trends.safe_float(_ExplodingFloat(), default=0.0)

    with pytest.raises(RuntimeError, match="history row conversion exploded"):
        trends.build_trend_rows([_ExplodingHistoryRow()], extract_metrics_from_summary=lambda _summary: {"ok": 1})

    with pytest.raises(RuntimeError, match="history row conversion exploded"):
        trends.build_selected_details(
            selected_ver=1,
            selected_item=_ExplodingHistoryRow(),
            trend_all=[],
            extract_metrics_from_summary=lambda _summary: {"ok": 1},
            comparison_metric_from_algo=lambda _algo: "ok",
        )


def test_scheduler_trend_summary_reports_bad_version_rows() -> None:
    from web.routes.domains.scheduler.scheduler_analysis_read import _trend_summary_state
    from web.viewmodels.scheduler_analysis_trends import build_trend_rows

    rows = [
        {"version": "bad-version", "result_summary": {"metrics": {"overdue_count": 1}}},
        {"version": 2, "result_summary": {"metrics": {"overdue_count": 0}}},
    ]

    trend_all, trend_rows = build_trend_rows(rows, extract_metrics_from_summary=lambda summary: summary.get("metrics"))
    state = _trend_summary_state(rows)

    assert [row["version"] for row in trend_all] == [2]
    assert [row["version"] for row in trend_rows] == [2]
    assert state["incomplete"] is True
    assert state["version_parse_failed_count"] == 1


def test_scheduler_analysis_candidate_metrics_do_not_leak_raw_bad_values() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = {
        "algo": {
            "candidate_comparison": {
                "enabled": True,
                "adopted_candidate_key": "adopted",
                "baseline_best_candidate_key": "baseline",
                "critical_best_candidate_key": "critical",
                "candidates": [
                    {
                        "candidate_key": "adopted",
                        "status": "completed",
                        "metrics": {
                            "failed_ops": 0,
                            "overdue_count": 0,
                            "total_tardiness_hours": 2,
                            "weighted_tardiness_hours": 2,
                            "makespan_hours": 8,
                            "changeover_count": 1,
                        },
                    },
                    {
                        "candidate_key": "baseline",
                        "status": "completed",
                        "metrics": {
                            "failed_ops": False,
                            "overdue_count": True,
                            "total_tardiness_hours": "bad_metric_value",
                            "weighted_tardiness_hours": "NaN",
                            "makespan_hours": "Infinity",
                            "changeover_count": "1.5",
                        },
                    },
                    {
                        "candidate_key": "critical",
                        "status": "completed",
                        "metrics": {
                            "failed_ops": 0,
                            "overdue_count": 1,
                            "total_tardiness_hours": 3,
                            "weighted_tardiness_hours": 3,
                            "makespan_hours": 9,
                            "changeover_count": 2,
                        },
                    },
                ],
            }
        }
    }
    options = [
        {
            "role": "adopted",
            "label": "正式采用方案",
            "source_table": "schedule",
            "candidate_status": "completed",
            "detail_saved": "yes",
        },
        {
            "role": "baseline_best",
            "label": "原算法代表方案",
            "source_table": "candidate_rows",
            "candidate_status": "completed",
            "detail_saved": "yes",
        },
        {
            "role": "critical_best",
            "label": "重点工序优先代表方案",
            "source_table": "candidate_rows",
            "candidate_status": "completed",
            "detail_saved": "yes",
        },
    ]

    display = build_candidate_comparison_display(summary, selected_ver=8, plan_role_options=options)

    rows_by_role = {row["role"]: row for row in display["rows"]}
    baseline = rows_by_role["baseline_best"]
    assert baseline["failed_ops"] is None
    assert baseline["failed_ops_parse_failed"] is True
    assert baseline["overdue_count_parse_failed"] is True
    assert baseline["total_tardiness_hours_parse_failed"] is True
    assert baseline["weighted_tardiness_hours_parse_failed"] is True
    assert baseline["makespan_hours_parse_failed"] is True
    assert baseline["changeover_count_parse_failed"] is True

    display_text = str(display)
    assert "bad_metric_value" not in display_text
    assert "NaN" not in display_text
    assert "Infinity" not in display_text
    assert "记录异常" in display_text
    assert "无法安全对比" in display_text


def test_scheduler_analysis_attempt_and_diagnostic_bool_numbers_are_visible_errors() -> None:
    from web.viewmodels import scheduler_analysis_trends as trends
    from web.viewmodels.scheduler_analysis_diagnostics import build_diagnostic_sections

    attempts = trends._build_attempt_rows(
        {
            "attempts": [
                {
                    "tag": "bad-bool-attempt",
                    "metrics": {"overdue_count": True},
                    "failed_ops": False,
                }
            ]
        },
        objective_key="overdue_count",
    )
    assert attempts[0]["primary_value"] is None
    assert attempts[0]["primary_value_parse_failed"] is True
    assert attempts[0]["failed_ops"] is None
    assert attempts[0]["failed_ops_parse_failed"] is True

    sections = build_diagnostic_sections(
        {
            "algo": {
                "graph_analysis": {
                    "status": "available",
                    "is_dag": True,
                    "node_count": True,
                    "edge_count": 0,
                    "critical_path_minutes": 0,
                    "critical_path_node_count": 0,
                    "warning_count": 0,
                    "cycle_edge_count": 0,
                    "time_cost_ms": 1,
                }
            }
        },
        selected_ver=7,
    )

    health = next(section for section in sections if section["key"] == "schedule_health")
    assert health["status"] == "error"
    assert health["degraded"] is True
    text_blob = "\n".join(_string_values(health))
    assert "无法安全展示" in text_blob
    assert "布尔值" not in text_blob
    assert "True" not in text_blob


def test_report_numeric_helpers_keep_empty_values_but_reject_bad_service_numbers() -> None:
    from core.services.report.delay_diagnosis_presentation import _delay_text
    from core.services.report.execution_review import ExecutionReviewMixin
    from core.services.report.exporters import export_utilization_xlsx
    from core.services.report.report_engine import ReportEngine
    from web.routes import reports_export_support
    from web.viewmodels import scheduler_reports_workbench as reports_vm

    assert reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": ""}], {}, resource_type="machine")[0]["utilization_percent"] is None
    assert reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": 0.125}], {}, resource_type="machine")[0]["utilization_percent"] == 12.5

    with pytest.raises(reports_vm.ReportPresentationValueError, match="利用率"):
        reports_vm.decorate_utilization_rows([{"machine_id": "M1", "utilization": "坏数据"}], {}, resource_type="machine")

    with pytest.raises(ValidationError, match="利用率"):
        export_utilization_xlsx([{"machine_id": "M1", "utilization": "坏数据"}], [])

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("1.5", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("-1", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int("1.0", field="导出行数")

    with pytest.raises(ValidationError, match="导出行数"):
        reports_export_support.report_nonnegative_int(1.0, field="导出行数")

    engine = ReportEngine.__new__(ReportEngine)
    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("-1")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("2.000")  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="导出行数"):
        engine._build_export_decision("坏数据")  # type: ignore[arg-type]

    with pytest.raises(reports_vm.ReportPresentationValueError, match="停机影响汇总值") as downtime_hours_exc:
        reports_vm._sum_number([{"downtime_hours": "坏数据"}], "downtime_hours")
    assert "downtime_hours" not in str(downtime_hours_exc.value)
    assert downtime_hours_exc.value.field == "downtime_hours"

    with pytest.raises(reports_vm.ReportPresentationValueError, match="停机影响汇总值") as downtime_count_exc:
        reports_vm.downtime_summary([{"downtime_count": "1.5", "schedule_overlap_count": 0}])
    assert "downtime_count" not in str(downtime_count_exc.value)
    assert downtime_count_exc.value.field == "downtime_count"

    with pytest.raises(ValidationError, match="暂停时长"):
        ExecutionReviewMixin._pause_duration_label("坏数据", True)

    class _Review(ExecutionReviewMixin):
        execution_feedback_service = SimpleNamespace(get_execution_state=lambda _op_ids: {})

    with pytest.raises(ValidationError, match="工序编号"):
        _Review()._execution_review_rows([{"op_id": "坏数据"}])

    with pytest.raises(ValidationError, match="延期小时"):
        _delay_text(SimpleNamespace(delay_hours="坏数据", delay_days=0, bucket="scheduled_overdue"))


def test_system_time_range_and_job_detail_parse_errors_stay_visible() -> None:
    from web.routes import system_utils

    with pytest.raises(ValidationError, match="开始时间不能晚于结束时间"):
        system_utils._normalize_time_range("2026-03-14", "2026-03-13")

    app = Flask(__name__)
    with app.test_request_context("/system/backup"):
        g.services = SimpleNamespace(
            system_job_state_query_service=SimpleNamespace(
                get=lambda key: SimpleNamespace(
                    to_dict=lambda: {
                        "job_key": key,
                        "last_run_time": "2026-03-13 08:00:00",
                        "last_run_detail": "{bad-json",
                    }
                )
            )
        )

        state_map = system_utils._get_job_state_map()

    auto_backup = state_map["auto_backup"]
    assert auto_backup["last_run_detail_obj"] is None
    assert auto_backup["last_run_detail_parse_error"]
    assert auto_backup["last_run_state"] == "valid"


def test_report_context_parse_failure_blocks_row_feedback_links() -> None:
    from web.viewmodels.scheduler_reports_workbench import build_report_context, decorate_execution_review_rows

    context = build_report_context(
        version=12,
        plan_resolution={
            "requested_role": "adopted",
            "selected_role": "adopted",
            "selected_label": "正式采用方案",
            "is_current_executable_official_version": True,
            "can_dispatch": True,
            "can_write_feedback": True,
            "result_summary_parse_failed": True,
        },
        date_from="2026-05-06",
        date_to="2026-05-06",
    )
    rows = decorate_execution_review_rows(
        [
            {
                "batch_id_label": "B-RPT",
                "planned_machine_id": "M-RPT",
                "planned_machine_name": "测试设备",
            }
        ],
        context,
    )
    link = rows[0]["workbench_links"][2]

    assert context["can_dispatch"] is False
    assert context["can_write_feedback"] is False
    assert "当前排产摘要读取失败" in context["guardrail_text"]
    assert link["label"] == "现场记录入口不可用"
    assert link["disabled"] is True
    assert link["url"] == ""
    assert "当前排产摘要读取失败" in link["disabled_reason"]


def test_report_plan_status_keeps_parse_failure_and_historical_reasons() -> None:
    from web.routes.reports_plan_template_fields import report_plan_status

    status = report_plan_status(
        {
            "user_label": "历史正式方案（已被新版本替代）",
            "result_summary_parse_failed": True,
            "result_summary_parse_reason": "json_decode_error",
            "is_superseded_by_newer_version": True,
        }
    )

    assert "当前排产摘要读取失败" in status["source_text"]
    assert "排产摘要内容不是有效 JSON" in status["source_text"]
    assert "json_decode_error" not in status["source_text"]
    assert "历史版本已被更新的正式排产替代" in status["source_text"]

    unknown = report_plan_status(
        {
            "user_label": "正式采用方案",
            "result_summary_parse_failed": True,
            "result_summary_parse_reason": "debug_stack_code",
        }
    )
    assert "当前排产摘要结构无法安全解析" in unknown["source_text"]
    assert "debug_stack_code" not in unknown["source_text"]


def test_report_plan_status_exposes_non_executable_official_result() -> None:
    from web.routes.reports_plan_template_fields import report_plan_status

    status = report_plan_status(
        {
            "user_label": "正式采用方案",
            "is_current_executable_official_version": False,
            "schedule_result_status": "failed",
        }
    )

    assert "当前排产结果状态是“失败”" in status["source_text"]
    assert "不能当作当前可执行正式方案" in status["source_text"]
    assert status["label"] == "正式采用方案"
    assert "failed" not in status["source_text"]


def test_resource_dispatch_parse_failure_overrides_stale_write_flags() -> None:
    from web.viewmodels.scheduler_resource_dispatch import decorate_resource_dispatch_context

    context = decorate_resource_dispatch_context(
        {
            "filters": {
                "plan_role": "adopted",
                "is_official_plan": True,
                "is_current_executable_official_version": True,
                "can_dispatch": True,
                "can_write_feedback": True,
                "result_summary_parse_failed": True,
                "result_summary_parse_reason": "json_decode_error",
            }
        }
    )

    identity = context["plan_identity"]
    assert identity["can_dispatch"] is False
    assert identity["can_write_feedback"] is False
    assert identity["kind_label"] == "只能查看的方案"
    assert identity["dispatch_feedback_label"] == "只能查看计划和实际"
    assert "排产摘要内容不是有效 JSON" in identity["guardrail_text"]
    assert "json_decode_error" not in identity["guardrail_text"]
    assert "schedule_result_status" not in context["client_filters"]


def test_scheduler_analysis_time_budget_labels_reject_bad_values() -> None:
    from web.viewmodels.scheduler_analysis_vm import _time_budget_seconds_display, _time_budget_seconds_label

    assert _time_budget_seconds_label(0) == "0"
    assert _time_budget_seconds_label("30") == "30"
    assert _time_budget_seconds_label(None) == "-"
    assert _time_budget_seconds_label("  ") == "-"
    assert _time_budget_seconds_label(False) == "记录异常"
    assert _time_budget_seconds_label("1.5") == "记录异常"
    assert _time_budget_seconds_display("30") == "30 秒"
    assert _time_budget_seconds_display(False) == "记录异常"
    assert _time_budget_seconds_display(None) == "-"
