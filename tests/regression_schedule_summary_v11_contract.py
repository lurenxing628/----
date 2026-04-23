import json
import os
import sys
import time
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _StubSvc:
    conn = object()
    logger = None

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_datetime(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        s = str(value).strip().replace("/", "-").replace("T", " ").replace("：", ":")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None


def _build_summary(
    *,
    objective_name: str,
    warnings,
    improvement_trace,
    downtime_meta: Optional[Dict[str, Any]] = None,
    auto_assign_enabled: str = "no",
):
    from core.algorithms.evaluation import ScheduleMetrics
    from core.services.scheduler.schedule_summary import build_result_summary
    from core.services.scheduler.schedule_summary_types import SummaryBuildContext

    cfg = SimpleNamespace(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        auto_assign_enabled=auto_assign_enabled,
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="improve",
        time_budget_seconds=10,
        objective=objective_name,
        freeze_window_enabled="no",
        freeze_window_days=0,
    )
    summary = SimpleNamespace(
        success=True,
        total_ops=1,
        scheduled_ops=1,
        failed_ops=0,
        warnings=list(warnings or []),
        errors=[],
    )
    metrics = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=2,
        weighted_tardiness_hours=20.0,
    )
    summary_ctx = SummaryBuildContext(
        cfg=cfg,
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=datetime(2026, 2, 1, 8, 0, 0),
        end_date=None,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"sort_strategy": "priority_first"},
        algo_mode="improve",
        objective_name=objective_name,
        time_budget_seconds=10,
        best_score=(0.0, 20.0, 1.0, 10.0, 100.0, 2.0),
        best_metrics=metrics,
        best_order=["B001"],
        attempts=[{"tag": "start:priority_first|sgs:slack", "dispatch_mode": "sgs", "dispatch_rule": "slack", "score": [0.0]}],
        improvement_trace=list(improvement_trace or []),
        frozen_op_ids=set(),
        downtime_meta=dict(downtime_meta or {}),
        simulate=False,
        t0=time.time(),
    )
    return build_result_summary(
        _StubSvc(),
        ctx=summary_ctx,
    )


def _assert_downtime_partial_fail_contract() -> None:
    import core.services.scheduler.resource_pool_builder as builder_mod

    original_repo = builder_mod.MachineDowntimeRepository

    class _StubRepo:
        def __init__(self, *_args, **_kwargs):
            pass

        def list_active_after(self, machine_id, _start_str):
            if machine_id == "MC_BAD":
                raise RuntimeError("bad downtime")
            if machine_id == "MC_OK":
                return [SimpleNamespace(start_time="2026-02-01 08:00:00", end_time="2026-02-01 10:00:00")]
            return []

    builder_mod.MachineDowntimeRepository = _StubRepo
    try:
        svc = _StubSvc()
        load_warnings: List[str] = []
        load_meta: Dict[str, Any] = {}
        load_map = builder_mod.load_machine_downtimes(
            svc,
            algo_ops=[
                SimpleNamespace(source="internal", machine_id="MC_OK"),
                SimpleNamespace(source="internal", machine_id="MC_BAD"),
            ],
            start_dt=datetime(2026, 2, 1, 8, 0, 0),
            warnings=load_warnings,
            meta=load_meta,
        )
        assert "MC_OK" in load_map and len(load_map["MC_OK"]) == 1, f"逐机降级后应保留健康设备停机：{load_map!r}"
        assert "MC_BAD" not in load_map, f"坏设备不应写入停机区间：{load_map!r}"
        assert not bool(load_meta.get("downtime_load_ok")), f"部分失败时 downtime_load_ok 应为 False：{load_meta!r}"
        assert int(load_meta.get("downtime_partial_fail_count") or 0) == 1, f"部分失败计数异常：{load_meta!r}"
        assert list(load_meta.get("downtime_partial_fail_machines_sample") or []) == ["MC_BAD"], (
            f"部分失败 sample 异常：{load_meta!r}"
        )
        assert any("MC_BAD" in str(w) for w in load_warnings), f"部分失败 warning 未暴露设备样例：{load_warnings!r}"

        _o1, _s1, load_summary_obj, _j1, _m1 = _build_summary(
            objective_name="min_weighted_tardiness",
            warnings=[],
            improvement_trace=[],
            downtime_meta=load_meta,
        )
        load_da = ((load_summary_obj.get("algo") or {}).get("downtime_avoid") or {})
        assert not bool(load_da.get("loaded_ok")), f"load partial fail 后 loaded_ok 应为 False：{load_da!r}"
        assert bool(load_da.get("degraded")), f"load partial fail 后应标记 degraded：{load_da!r}"
        assert int(load_da.get("load_partial_fail_count") or 0) == 1, f"load partial fail count 未入摘要：{load_da!r}"
        assert list(load_da.get("load_partial_fail_machines_sample") or []) == ["MC_BAD"], (
            f"load partial fail sample 未入摘要：{load_da!r}"
        )
        assert "MC_BAD" in str(load_da.get("degradation_reason") or ""), f"load degradation_reason 未暴露样例：{load_da!r}"
        hard_constraints = list((load_summary_obj.get("algo") or {}).get("hard_constraints") or [])
        assert "downtime_avoid" not in hard_constraints, f"部分失败后不应宣称 downtime_avoid 仍是完整硬约束：{hard_constraints!r}"

        extend_warnings: List[str] = []
        extend_meta: Dict[str, Any] = {"downtime_load_ok": True, "downtime_load_error": None}
        extend_map = builder_mod.extend_downtime_map_for_resource_pool(
            svc,
            cfg=SimpleNamespace(auto_assign_enabled="yes"),
            resource_pool={"operators_by_machine": {"MC_OK": ["OP1"], "MC_BAD": ["OP2"]}},
            downtime_map={},
            start_dt=datetime(2026, 2, 1, 8, 0, 0),
            warnings=extend_warnings,
            meta=extend_meta,
        )
        assert "MC_OK" in extend_map and len(extend_map["MC_OK"]) == 1, f"extend 部分失败后应保留健康候选设备停机：{extend_map!r}"
        assert "MC_BAD" not in extend_map, f"坏候选设备不应写入停机区间：{extend_map!r}"
        assert bool(extend_meta.get("downtime_extend_attempted")), f"extend_attempted 应为 True：{extend_meta!r}"
        assert not bool(extend_meta.get("downtime_extend_ok")), f"extend 部分失败时 downtime_extend_ok 应为 False：{extend_meta!r}"
        assert int(extend_meta.get("downtime_extend_partial_fail_count") or 0) == 1, (
            f"extend 部分失败计数异常：{extend_meta!r}"
        )
        assert list(extend_meta.get("downtime_extend_partial_fail_machines_sample") or []) == ["MC_BAD"], (
            f"extend 部分失败 sample 异常：{extend_meta!r}"
        )
        assert any("MC_BAD" in str(w) for w in extend_warnings), f"extend 部分失败 warning 未暴露设备样例：{extend_warnings!r}"

        _o2, _s2, extend_summary_obj, _j2, _m2 = _build_summary(
            objective_name="min_weighted_tardiness",
            warnings=[],
            improvement_trace=[],
            downtime_meta=extend_meta,
            auto_assign_enabled="yes",
        )
        extend_da = ((extend_summary_obj.get("algo") or {}).get("downtime_avoid") or {})
        assert bool(extend_da.get("loaded_ok")), f"仅 extend 部分失败时 loaded_ok 应保持 True：{extend_da!r}"
        assert bool(extend_da.get("degraded")), f"extend partial fail 后应标记 degraded：{extend_da!r}"
        assert bool(extend_da.get("extend_attempted")), f"extend_attempted 未入摘要：{extend_da!r}"
        assert int(extend_da.get("extend_partial_fail_count") or 0) == 1, f"extend partial fail count 未入摘要：{extend_da!r}"
        assert list(extend_da.get("extend_partial_fail_machines_sample") or []) == ["MC_BAD"], (
            f"extend partial fail sample 未入摘要：{extend_da!r}"
        )
        assert "MC_BAD" in str(extend_da.get("degradation_reason") or ""), f"extend degradation_reason 未暴露样例：{extend_da!r}"
    finally:
        builder_mod.MachineDowntimeRepository = original_repo


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    _overdue, _status, result_summary_obj, result_summary_json, _ms = _build_summary(
        objective_name="min_weighted_tardiness",
        warnings=[],
        improvement_trace=[],
    )
    assert result_summary_obj.get("summary_schema_version") == "1.2", "summary_schema_version 未升到 1.2"

    algo = result_summary_obj.get("algo") or {}
    assert algo.get("comparison_metric") == "weighted_tardiness_hours", f"comparison_metric 错误：{algo.get('comparison_metric')!r}"
    schema_keys = [it.get("key") for it in (algo.get("best_score_schema") or []) if isinstance(it, dict)]
    assert schema_keys[:3] == [
        "failed_ops",
        "weighted_tardiness_hours",
        "total_tardiness_hours",
    ], f"best_score_schema 错误：{schema_keys}"
    config_snapshot = algo.get("config_snapshot") or {}
    assert config_snapshot.get("objective") == "min_weighted_tardiness", f"config_snapshot 未落盘 objective：{config_snapshot}"

    ctx = build_analysis_context(
        selected_ver=1,
        raw_hist=[{"version": 1, "result_summary": result_summary_json}],
        selected_item={"version": 1, "result_summary": result_summary_json},
    )
    assert ctx.get("objective_key") == "weighted_tardiness_hours", f"analysis_context 未使用 comparison_metric：{ctx.get('objective_key')!r}"

    old_summary_json = json.dumps(
        {
            "version": 1,
            "algo": {
                "objective": "min_tardiness",
                "metrics": {
                    "total_tardiness_hours": 12.0,
                    "overdue_count": 1,
                },
            },
        },
        ensure_ascii=False,
    )
    old_ctx = build_analysis_context(
        selected_ver=1,
        raw_hist=[{"version": 1, "result_summary": old_summary_json}],
        selected_item={"version": 1, "result_summary": old_summary_json},
    )
    assert old_ctx.get("objective_key") == "total_tardiness_hours", f"旧 summary 兼容回退异常：{old_ctx.get('objective_key')!r}"

    huge_warnings = [f"W{i}:" + ("x" * 6000) for i in range(120)]
    huge_trace = [{"tag": "T" + ("y" * 4000), "elapsed_ms": i, "metrics": {"weighted_tardiness_hours": float(i)}} for i in range(200)]
    _overdue2, _status2, big_obj, big_json, _ms2 = _build_summary(
        objective_name="min_weighted_tardiness",
        warnings=huge_warnings,
        improvement_trace=huge_trace,
    )
    assert bool(big_obj.get("summary_truncated")), "超大 summary 未标记 summary_truncated"
    assert int(big_obj.get("original_size_bytes") or 0) > len(big_json.encode("utf-8")), "original_size_bytes 未记录原始大小"
    assert len(big_json.encode("utf-8")) <= 512 * 1024, "summary 截断后仍超过 512KB"

    _assert_downtime_partial_fail_contract()

    print("OK")


def test_schedule_summary_v11_contract() -> None:
    main()


if __name__ == "__main__":
    main()
