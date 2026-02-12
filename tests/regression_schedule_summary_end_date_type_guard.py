import os
import sys
import time
from datetime import date, datetime
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


class _StubSvc:
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


def _build_summary_with_end_date(end_date_value):
    from core.services.scheduler.schedule_summary import build_result_summary

    svc = _StubSvc()
    cfg = SimpleNamespace(freeze_window_enabled="no", auto_assign_enabled="no", freeze_window_days=0)
    summary = SimpleNamespace(
        success=True,
        total_ops=0,
        scheduled_ops=0,
        failed_ops=0,
        warnings=[],
        errors=[],
    )
    used_strategy = SimpleNamespace(value="priority_first")

    _overdue, _status, result_summary_obj, _json_text, _ms = build_result_summary(
        svc,
        cfg=cfg,
        version=1,
        normalized_batch_ids=["B001"],
        start_dt=datetime(2026, 2, 1, 8, 0, 0),
        end_date=end_date_value,
        batches={},
        operations=[],
        results=[],
        summary=summary,
        used_strategy=used_strategy,
        used_params={},
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=5,
        best_score=None,
        best_metrics=None,
        best_order=[],
        attempts=[],
        improvement_trace=[],
        frozen_op_ids=set(),
        downtime_meta={},
        simulate=False,
        t0=time.time(),
    )
    return result_summary_obj


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # 1) end_date 是字符串：不应抛异常，且应保留字符串
    r1 = _build_summary_with_end_date("2026-02-10")
    assert r1.get("end_date") == "2026-02-10", f"字符串 end_date 序列化异常：{r1.get('end_date')!r}"

    # 2) end_date 是 date：应输出 ISO 字符串
    r2 = _build_summary_with_end_date(date(2026, 2, 11))
    assert r2.get("end_date") == "2026-02-11", f"date end_date 序列化异常：{r2.get('end_date')!r}"

    print("OK")


if __name__ == "__main__":
    main()
