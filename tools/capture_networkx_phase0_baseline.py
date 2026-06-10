from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.infrastructure.database import get_connection
from core.infrastructure.logging import OperationLogger
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.schedule_service import ScheduleService


def _csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _git(args: List[str]) -> str:
    try:
        return subprocess.check_output(["git"] + args, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def _json_loads(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {"_parse_error": True, "raw": str(value)}
    return parsed if isinstance(parsed, dict) else {"_invalid_type": type(parsed).__name__}


def _env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or str(value).strip() == "":
        raise RuntimeError(f"{name} 不能为空")
    return str(value)


def _set_case_config(cfg_svc: ConfigService) -> Dict[str, Optional[str]]:
    """Set deterministic scheduler config for a baseline run.

    The tool intentionally uses the existing configuration facade instead of
    writing tables directly. It only mutates the copied/temp DB passed via
    APS_PHASE0_DB_PATH.
    """

    algo_mode = os.environ.get("APS_PHASE0_ALGO_MODE", "greedy")
    strategy = os.environ.get("APS_PHASE0_STRATEGY")
    dispatch_mode = os.environ.get("APS_PHASE0_DISPATCH_MODE")
    dispatch_rule = os.environ.get("APS_PHASE0_DISPATCH_RULE")
    auto_assign_enabled = os.environ.get("APS_PHASE0_AUTO_ASSIGN_ENABLED")

    cfg_svc.ensure_defaults()
    cfg_svc.set_algo_mode(algo_mode)
    cfg_svc.set_freeze_window("no", 0)

    if strategy:
        cfg_svc.set_strategy(strategy)
    if dispatch_mode or dispatch_rule:
        cfg_svc.set_dispatch(dispatch_mode or "batch_order", dispatch_rule or "slack")
    if auto_assign_enabled:
        cfg_svc.set_auto_assign_enabled(auto_assign_enabled)

    return {
        "algo_mode": algo_mode,
        "strategy": strategy,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "freeze_window": "no",
        "auto_assign_enabled": auto_assign_enabled,
    }


def _load_schedule_rows(conn: Any, version: int) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                s.op_id,
                bo.batch_id,
                bo.op_code,
                bo.seq,
                s.machine_id,
                s.operator_id,
                bo.supplier_id,
                bo.source,
                s.start_time,
                s.end_time,
                s.lock_status,
                s.version
            FROM Schedule s
            JOIN BatchOperations bo ON bo.id = s.op_id
            WHERE s.version = ?
            ORDER BY bo.batch_id, bo.seq, bo.id, s.id
            """,
            (version,),
        ).fetchall()
    ]


def _load_history(conn: Any, version: int) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT version, strategy, batch_count, op_count, result_status, result_summary, created_by, schedule_time
        FROM ScheduleHistory
        WHERE version = ?
        """,
        (version,),
    ).fetchone()
    return dict(row) if row else {}


def _load_operation_log(conn: Any, *, version: int, simulate: bool) -> Dict[str, Any]:
    action = "simulate" if simulate else "schedule"
    row = conn.execute(
        """
        SELECT id, module, action, target_type, target_id, detail
        FROM OperationLogs
        WHERE module = 'scheduler'
          AND action = ?
          AND target_type = 'schedule'
          AND target_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (action, str(version)),
    ).fetchone()
    return dict(row) if row else {}


def main() -> int:
    db_path = _env("APS_PHASE0_DB_PATH")
    case_id = _env("APS_PHASE0_CASE_ID")
    case_title = os.environ.get("APS_PHASE0_CASE_TITLE", case_id)
    batch_ids = _csv(_env("APS_PHASE0_BATCH_IDS"))
    start_dt = _env("APS_PHASE0_START_DT")
    simulate = os.environ.get("APS_PHASE0_SIMULATE", "yes").strip().lower() in ("1", "true", "yes", "on")

    if not batch_ids:
        raise RuntimeError("APS_PHASE0_BATCH_IDS 不能为空")

    out_dir = Path(os.environ.get("APS_PHASE0_OUT_DIR", "evidence/scheduler_baseline"))
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = get_connection(db_path)
    try:
        op_logger = OperationLogger(conn, logger=None)
        cfg_svc = ConfigService(conn, logger=None, op_logger=op_logger)
        config = _set_case_config(cfg_svc)

        svc = ScheduleService(conn, logger=None, op_logger=op_logger)
        ret = svc.run_schedule(
            batch_ids=batch_ids,
            start_dt=start_dt,
            simulate=simulate,
            created_by="networkx_phase0",
            enforce_ready=True,
        )
        version = int(ret["version"])

        schedule_rows = _load_schedule_rows(conn, version)
        history = _load_history(conn, version)
        result_summary = _json_loads(history.get("result_summary"))
        operation_log = _load_operation_log(conn, version=version, simulate=simulate)
        operation_log_detail = _json_loads(operation_log.get("detail"))

        payload = {
            "baseline_schema_version": "networkx_phase0_scheduler_baseline.v1",
            "case_id": case_id,
            "case_title": case_title,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "repo": {
                "branch": _git(["branch", "--show-current"]),
                "commit": _git(["rev-parse", "HEAD"]),
                "dirty_status": _git(["status", "--short"]),
            },
            "python": {
                "version": sys.version,
            },
            "run_input": {
                "batch_ids": batch_ids,
                "start_dt": start_dt,
                "simulate": simulate,
                "created_by": "networkx_phase0",
            },
            "config": config,
            "run_return": ret,
            "schedule_rows": schedule_rows,
            "history": {
                "version": history.get("version"),
                "strategy": history.get("strategy"),
                "batch_count": history.get("batch_count"),
                "op_count": history.get("op_count"),
                "result_status": history.get("result_status"),
                "created_by": history.get("created_by"),
                "schedule_time": history.get("schedule_time"),
                "result_summary_core": result_summary,
            },
            "operation_log": {
                "id": operation_log.get("id"),
                "module": operation_log.get("module"),
                "action": operation_log.get("action"),
                "target_type": operation_log.get("target_type"),
                "target_id": operation_log.get("target_id"),
                "detail_core": operation_log_detail,
            },
            "future_compare_ignore": [
                "repo.dirty_status",
                "run_return.version",
                "schedule_rows[].version",
                "history.version",
                "history.result_summary_core.time_cost_ms",
                "operation_log.id",
                "operation_log.detail_core.time_cost_ms",
                "history.result_summary_core.algo.graph_analysis",
                "history.result_summary_core.diagnostics.graph_analysis",
            ],
        }

        out_path = out_dir / f"{case_id}_result.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out_path))
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
