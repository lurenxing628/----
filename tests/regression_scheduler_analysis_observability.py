from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, Dict, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def setup_runtime(repo_root: str) -> None:
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_analysis_observability_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = os.path.join(tmpdir, "aps.db")
    os.environ["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    os.environ["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def make_metrics(*, overdue_count: int) -> Dict[str, Any]:
    return {
        "overdue_count": int(overdue_count),
        "total_tardiness_hours": 5.0,
        "weighted_tardiness_hours": 3.0,
        "makespan_hours": 100.0,
        "makespan_internal_hours": 80.0,
        "changeover_count": 1,
        "machine_util_avg": 0.6,
        "machine_used_count": 3,
        "machine_load_cv": 0.1,
        "operator_util_avg": 0.5,
        "operator_used_count": 2,
        "operator_load_cv": 0.2,
    }


def make_old_summary() -> Dict[str, Any]:
    return {
        "version": 1,
        "algo": {
            "objective": "min_overdue",
            "metrics": make_metrics(overdue_count=2),
            "attempts": [
                {
                    "tag": "start:priority_first|batch_order:slack",
                    "strategy": "priority_first",
                    "failed_ops": 0,
                    "score": [0, 2],
                    "metrics": {"overdue_count": 2},
                }
            ],
            "improvement_trace": [],
        },
        "time_cost_ms": 123,
    }


def make_new_summary() -> Dict[str, Any]:
    return {
        "version": 2,
        "summary_truncated": True,
        "original_size_bytes": 600000,
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "comparison_metric": "overdue_count",
            "time_budget_seconds": 20,
            "metrics": make_metrics(overdue_count=1),
            "attempts": [
                {
                    "tag": "start:priority_first|sgs:cr",
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "score": [0, 1],
                    "metrics": {"overdue_count": 1},
                }
            ],
            "improvement_trace": [],
            "downtime_avoid": {
                "loaded_ok": False,
                "degraded": True,
                "degradation_reason": "停机区间加载失败",
                "extend_attempted": False,
            },
            "freeze_window": {
                "enabled": "yes",
                "days": 3,
                "frozen_op_count": 0,
                "frozen_batch_count": 0,
                "frozen_batch_ids_sample": [],
                "degraded": True,
                "degradation_reason": "【冻结窗口】跳过批次 B001",
            },
            "best_score_schema": [
                {"index": 0, "key": "failed_ops", "label": "失败工序数"},
                {"index": 1, "key": "overdue_count", "label": "超期批次数"},
            ],
            "config_snapshot": {
                "sort_strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "objective": "min_overdue",
                "time_budget_seconds": 20,
            },
        },
        "time_cost_ms": 456,
    }


def build_case_inputs(*, version: int, summary_obj: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    result_summary_json = json.dumps(summary_obj, ensure_ascii=False)
    selected = {
        "version": int(version),
        "schedule_time": f"2026-01-0{version} 08:00:00",
        "strategy": "priority_first",
        "result_status": "success",
        "created_by": "reg",
        "result_summary": result_summary_json,
    }
    return selected, {"version": int(version), "result_summary": result_summary_json}


def main() -> None:
    repo_root = find_repo_root()
    setup_runtime(repo_root)

    from flask import render_template

    from app import create_app
    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    app = create_app()

    old_summary = make_old_summary()
    old_selected, old_hist = build_case_inputs(version=1, summary_obj=old_summary)
    old_ctx = build_analysis_context(selected_ver=1, raw_hist=[old_hist], selected_item=old_selected)
    assert old_ctx.get("attempts"), "旧 summary 应提取出 attempts"
    assert old_ctx["attempts"][0].get("dispatch_mode") == "-", "旧 summary 的 dispatch_mode 应安全回退为 '-'"
    assert old_ctx["attempts"][0].get("dispatch_rule") == "-", "旧 summary 的 dispatch_rule 应安全回退为 '-'"

    with app.test_request_context("/scheduler/analysis?version=1"):
        old_html = render_template(
            "scheduler/analysis.html",
            title="regression",
            ui_mode="v1",
            versions=[
                {
                    "version": 1,
                    "schedule_time": old_selected["schedule_time"],
                    "strategy": old_selected["strategy"],
                    "result_status": old_selected["result_status"],
                }
            ],
            **old_ctx,
        )
    assert "排产优化分析" in old_html, "旧 summary 页面未成功渲染"
    assert "裁剪后摘要" not in old_html, "旧 summary 不应展示裁剪提示"
    assert "停机避让约束已降级" not in old_html, "旧 summary 不应展示停机降级提示"
    assert "冻结窗口约束已降级" not in old_html, "旧 summary 不应展示冻结窗口降级提示"
    assert "-/-" in old_html, "旧 summary 的 attempts 派工列应展示安全回退值"

    new_summary = make_new_summary()
    new_selected, new_hist = build_case_inputs(version=2, summary_obj=new_summary)
    new_ctx = build_analysis_context(selected_ver=2, raw_hist=[new_hist], selected_item=new_selected)
    assert new_ctx.get("attempts"), "新 summary 应提取出 attempts"
    assert new_ctx["attempts"][0].get("dispatch_mode") == "sgs", "dispatch_mode 未从 VM 透传"
    assert new_ctx["attempts"][0].get("dispatch_rule") == "cr", "dispatch_rule 未从 VM 透传"
    selected_summary = new_ctx.get("selected_summary") or {}
    assert bool(selected_summary.get("summary_truncated")), "selected_summary 未保留 summary_truncated"
    assert int(selected_summary.get("original_size_bytes") or 0) == 600000, "selected_summary 未保留 original_size_bytes"
    assert bool(((selected_summary.get("algo") or {}).get("downtime_avoid") or {}).get("degraded")), "停机降级字段丢失"
    assert bool(((selected_summary.get("algo") or {}).get("freeze_window") or {}).get("degraded")), "冻结窗口降级字段丢失"

    with app.test_request_context("/scheduler/analysis?version=2"):
        new_html = render_template(
            "scheduler/analysis.html",
            title="regression",
            ui_mode="v1",
            versions=[
                {
                    "version": 2,
                    "schedule_time": new_selected["schedule_time"],
                    "strategy": new_selected["strategy"],
                    "result_status": new_selected["result_status"],
                }
            ],
            **new_ctx,
        )
    assert "当前展示为裁剪后摘要" in new_html, "未展示 summary_truncated 提示"
    assert "600000" in new_html, "未展示 original_size_bytes"
    assert "停机避让约束已降级" in new_html, "未展示停机降级提示"
    assert "停机区间加载失败" in new_html, "未展示停机降级原因"
    assert "冻结窗口约束已降级" in new_html, "未展示冻结窗口降级提示"
    assert "【冻结窗口】跳过批次 B001" in new_html, "未展示冻结窗口降级原因"
    assert "排序策略" in new_html, "attempts 表头未更正为排序策略"
    assert "派工" in new_html, "attempts 表头未新增派工列"
    assert "sgs/cr" in new_html, "attempts 派工列未闭环展示 dispatch_mode/dispatch_rule"

    print("OK")


if __name__ == "__main__":
    main()
