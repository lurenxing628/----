"""Run one folded FJSP benchmark case through APS scheduling."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from tests._support.optimizer_fjsp_dataset import (
    DATASET_SOURCES,
    assign_machines,
    load_instance_text,
    parse_fjsp,
)
from tests._support.optimizer_fjsp_fixture import (
    insert_minimal_entities,
    seed_calendar_24h,
    set_schedule_config,
)


def run_one_case(
    *,
    repo_root: Path,
    instance_key: str,
    fold_strategy: str,
    algo_mode: str,
    time_budget_seconds: int,
    allow_download: bool,
    calendar_days: int,
    start_dt: datetime,
    due_date: str,
) -> Dict[str, Any]:
    case = _prepare_case(
        instance_key=instance_key,
        fold_strategy=fold_strategy,
        algo_mode=algo_mode,
        time_budget_seconds=time_budget_seconds,
        allow_download=allow_download,
    )
    conn, db_path = _open_case_db(repo_root, instance_key, fold_strategy, algo_mode)
    try:
        _load_case_fixture(conn, case, calendar_days=calendar_days, start_dt=start_dt, due_date=due_date)
        run_payload = _execute_schedule(conn, case["batch_ids"], start_dt=start_dt)
        return _collect_case_result(conn, case, run_payload=run_payload, db_path=db_path)
    finally:
        _close_conn(conn)


def _prepare_case(
    *,
    instance_key: str,
    fold_strategy: str,
    algo_mode: str,
    time_budget_seconds: int,
    allow_download: bool,
) -> Dict[str, Any]:
    meta = DATASET_SOURCES[instance_key]
    text = load_instance_text(instance_key, allow_download=allow_download)
    instance = parse_fjsp(text, name=instance_key)
    assignment = assign_machines(instance, strategy=fold_strategy, seed=0)
    return {
        "meta": meta,
        "instance": instance,
        "assignment": assignment,
        "header": _result_header(instance, meta, fold_strategy, algo_mode, time_budget_seconds),
        "batch_ids": [],
    }


def _result_header(instance, meta, fold_strategy: str, algo_mode: str, time_budget_seconds: int) -> Dict[str, Any]:
    return {
        "instance": instance.name,
        "jobs": int(instance.num_jobs),
        "machines": int(instance.num_machines),
        "ref_type": meta.get("ref_type"),
        "ref_makespan": meta.get("ref_makespan"),
        "fold_strategy": fold_strategy,
        "algo_mode": algo_mode,
        "time_budget_seconds": int(time_budget_seconds),
    }


def _open_case_db(repo_root: Path, instance_key: str, fold_strategy: str, algo_mode: str):
    from core.infrastructure.database import ensure_schema, get_connection

    tmpdir = tempfile.mkdtemp(prefix=f"aps_fjsp_{instance_key}_{fold_strategy}_{algo_mode}_")
    db_path = str(Path(tmpdir) / "bench.db")
    ensure_schema(db_path, logger=None, schema_path=str(repo_root / "schema.sql"))
    return get_connection(db_path), db_path


def _load_case_fixture(conn, case: Dict[str, Any], *, calendar_days: int, start_dt: datetime, due_date: str) -> None:
    seed_calendar_24h(conn, start_date=start_dt.date(), days=int(calendar_days))
    set_schedule_config(
        conn,
        algo_mode=case["header"]["algo_mode"],
        time_budget_seconds=int(case["header"]["time_budget_seconds"]),
    )
    case["batch_ids"] = insert_minimal_entities(
        conn,
        instance=case["instance"],
        machine_assignment=case["assignment"],
        due_date=due_date,
    )
    conn.commit()


def _execute_schedule(conn, batch_ids, *, start_dt: datetime) -> Dict[str, Any]:
    from core.services.scheduler.schedule_service import ScheduleService

    svc = ScheduleService(conn, logger=None, op_logger=None)
    return svc.run_schedule(batch_ids=batch_ids, start_dt=start_dt, simulate=False, enforce_ready=False)


def _collect_case_result(conn, case: Dict[str, Any], *, run_payload: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    version = int(run_payload.get("version") or 0)
    result = dict(case["header"])
    result["version"] = version
    result["run_return"] = run_payload
    summary_obj = _load_summary(conn, version=version, instance_key=str(result["instance"]))
    result["result_summary"] = summary_obj
    _merge_summary_metrics(result, summary_obj, run_payload)
    _merge_makespan(conn, result, version=version)
    _merge_gap_and_validity(result, case["meta"])
    result["tmpdir"] = str(Path(db_path).parent)
    result["db_path"] = db_path
    return result


def _load_summary(conn, *, version: int, instance_key: str) -> Dict[str, Any]:
    from data.repositories import ScheduleHistoryRepository

    hist_repo = ScheduleHistoryRepository(conn, logger=None)
    hist = hist_repo.get_by_version(version)
    if not hist or not hist.result_summary:
        raise RuntimeError(f"{instance_key}: 未找到 ScheduleHistory(version={version}) 或 result_summary 为空")
    summary_obj = json.loads(str(hist.result_summary))
    return summary_obj if isinstance(summary_obj, dict) else {}


def _merge_summary_metrics(result: Dict[str, Any], summary_obj: Dict[str, Any], run_payload: Dict[str, Any]) -> None:
    metrics = (summary_obj.get("algo") or {}).get("metrics") or {}
    counts = summary_obj.get("counts") or {}
    result["metrics"] = metrics
    result["counts"] = counts
    result["time_cost_ms"] = int(summary_obj.get("time_cost_ms") or run_payload.get("time_cost_ms") or 0)


def _merge_makespan(conn, result: Dict[str, Any], *, version: int) -> None:
    from core.models.schedule_plan_role import SOURCE_SCHEDULE
    from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository

    makespan_h = _safe_float((result.get("metrics") or {}).get("makespan_hours"))
    span_repo = SchedulePlanQueryRepository(conn, logger=None)
    span = span_repo.get_plan_time_span(version=version, source_table=SOURCE_SCHEDULE, candidate_id=None)
    result["schedule_span"] = span
    if makespan_h is None and span:
        makespan_h = _span_hours(span)
    result["makespan_hours"] = makespan_h


def _span_hours(span: Dict[str, Any]) -> float:
    start_time = datetime.strptime(span["start_time"], "%Y-%m-%d %H:%M:%S")
    end_time = datetime.strptime(span["end_time"], "%Y-%m-%d %H:%M:%S")
    return (end_time - start_time).total_seconds() / 3600.0


def _merge_gap_and_validity(result: Dict[str, Any], meta: Dict[str, Any]) -> None:
    makespan_h = result.get("makespan_hours")
    ref = float(meta.get("ref_makespan") or 0.0)
    result["gap_percent"] = None
    if makespan_h is not None and ref > 0:
        result["gap_percent"] = (float(makespan_h) - ref) / ref * 100.0
    failed_ops = _safe_int((result.get("counts") or {}).get("failed_ops"))
    result["failed_ops"] = failed_ops
    result["valid"] = bool(failed_ops == 0 and makespan_h is not None)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def _close_conn(conn) -> None:
    try:
        conn.close()
    except Exception:
        pass
