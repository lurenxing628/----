from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler import BatchService, ConfigService, ScheduleService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _create_batch_from_minimal_template(conn: Any, batch_id: str) -> None:
    batch_svc = BatchService(conn, logger=None, op_logger=None)
    batch_svc.create_batch_from_template(
        batch_id=batch_id,
        part_no="P1",
        quantity=1,
        due_date="2026-02-10",
        priority="normal",
        ready_status="yes",
    )
    op_row = conn.execute(
        "SELECT id, setup_hours, unit_hours FROM BatchOperations WHERE batch_id=? AND source=? ORDER BY id LIMIT 1",
        (batch_id, "internal"),
    ).fetchone()
    assert op_row is not None

    ScheduleService(conn, logger=None, op_logger=None).update_internal_operation(
        int(op_row["id"]),
        machine_id="MC_A1",
        operator_id="OP001",
        setup_hours=op_row["setup_hours"],
        unit_hours=op_row["unit_hours"],
    )


def _seed_minimal_schedule_case(conn: Any) -> None:
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_A", "A工种", "internal"))
    conn.execute(
        "INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)",
        ("MC_A1", "A-01", "OT_A", "active"),
    )
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
    conn.execute(
        "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        ("OP001", "MC_A1", "normal", "yes"),
    )
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P1", "P1", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations
        (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P1", 10, "OT_A", "A工种", "internal", None, None, None, 0.0, 1.0, "active"),
    )
    conn.commit()
    _create_batch_from_minimal_template(conn, "B001")


def _make_conn(tmp_path: Path, mode: str) -> Any:
    test_db = tmp_path / f"aps_graph_report_{mode}.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    conn = get_connection(str(test_db))
    cfg_svc = ConfigService(conn, logger=None, op_logger=None)
    cfg_svc.restore_default()
    conn.execute(
        "UPDATE ScheduleConfig SET config_value=? WHERE config_key=?",
        (mode, "graph_analysis_mode"),
    )
    conn.commit()
    _seed_minimal_schedule_case(conn)
    return conn


def _set_graph_mode(conn: Any, mode: str) -> None:
    conn.execute(
        "UPDATE ScheduleConfig SET config_value=? WHERE config_key=?",
        (mode, "graph_analysis_mode"),
    )
    conn.commit()


def _schedule_rows_signature(conn: Any, version: int) -> Tuple[Tuple[Any, ...], ...]:
    rows = conn.execute(
        """
        SELECT op_id, machine_id, operator_id, start_time, end_time, lock_status
        FROM Schedule
        WHERE version=?
        ORDER BY op_id
        """,
        (int(version),),
    ).fetchall()
    return tuple(
        (
            int(row["op_id"]),
            row["machine_id"],
            row["operator_id"],
            str(row["start_time"]),
            str(row["end_time"]),
            row["lock_status"],
        )
        for row in rows
    )


def _latest_result_summary(conn: Any, version: int) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT result_summary FROM ScheduleHistory WHERE version=? ORDER BY id DESC LIMIT 1",
        (int(version),),
    ).fetchone()
    assert row is not None
    return json.loads(row["result_summary"] or "{}")


def _summary_pr4_signature(summary: Dict[str, Any]) -> Dict[str, Any]:
    algo = dict(summary.get("algo") or {})
    return {
        "counts": dict(summary.get("counts") or {}),
        "best_batch_order": list(algo.get("best_batch_order") or []),
        "selected_batch_ids": list(summary.get("selected_batch_ids") or []),
        "freeze_window": dict(algo.get("freeze_window") or {}),
        "resource_pool": dict(algo.get("resource_pool") or {}),
    }


def _run_case(tmp_path: Path, mode: str) -> Dict[str, Any]:
    conn = _make_conn(tmp_path, mode)
    try:
        result = ScheduleService(conn, logger=None, op_logger=None).run_schedule(
            batch_ids=["B001"],
            start_dt="2026-02-01 08:00:00",
            simulate=False,
            enforce_ready=False,
            created_by="regression",
        )
        version = int(result["version"])
        return {
            "result": result,
            "rows": _schedule_rows_signature(conn, version),
            "summary": _latest_result_summary(conn, version),
        }
    finally:
        conn.close()


def _run_frozen_seed_case(tmp_path: Path, mode: str) -> Dict[str, Any]:
    test_db = tmp_path / f"aps_graph_frozen_seed_{mode}.db"
    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    conn = get_connection(str(test_db))
    cfg_svc = ConfigService(conn, logger=None, op_logger=None)
    cfg_svc.restore_default()
    _set_graph_mode(conn, "off")
    _seed_minimal_schedule_case(conn)
    try:
        svc = ScheduleService(conn, logger=None, op_logger=None)
        svc.run_schedule(
            batch_ids=["B001"],
            start_dt="2026-02-01 08:00:00",
            simulate=False,
            enforce_ready=False,
            created_by="regression",
        )
        _create_batch_from_minimal_template(conn, "B002")
        cfg_svc.set_freeze_window("yes", 2)
        _set_graph_mode(conn, mode)
        result = svc.run_schedule(
            batch_ids=["B001", "B002"],
            start_dt="2026-02-01 08:00:00",
            simulate=False,
            enforce_ready=False,
            created_by="regression",
        )
        version = int(result["version"])
        return {
            "result": result,
            "rows": _schedule_rows_signature(conn, version),
            "summary": _latest_result_summary(conn, version),
        }
    finally:
        conn.close()


def test_graph_report_and_on_modes_use_real_graph_without_changing_schedule_result(tmp_path: Path) -> None:
    off_case = _run_case(tmp_path, "off")
    report_case = _run_case(tmp_path, "report")
    on_case = _run_case(tmp_path, "on")

    assert report_case["rows"] == off_case["rows"]
    assert on_case["rows"] == off_case["rows"]
    assert report_case["result"]["summary"]["counts"] == off_case["result"]["summary"]["counts"]
    assert on_case["result"]["summary"]["counts"] == off_case["result"]["summary"]["counts"]

    assert "graph_analysis" not in off_case["summary"]["algo"]

    report_graph = report_case["summary"]["algo"]["graph_analysis"]
    assert report_graph["status"] == "available"
    assert report_graph["mode"] == "report"
    assert report_graph["effective_mode"] == "report"
    assert report_graph["input_scope"] == "all_algo_ops_with_frozen_markers"
    assert report_graph["total_algo_op_count"] == 1
    assert report_graph["reschedulable_unfrozen_op_count"] == 1

    on_graph = on_case["summary"]["algo"]["graph_analysis"]
    assert on_graph["status"] == "available"
    assert on_graph["mode"] == "on"
    assert on_graph["effective_mode"] == "graph_ready_queue"
    assert on_graph["ready_queue_enabled"] is True
    assert on_graph["input_scope"] == "all_algo_ops_with_frozen_markers"

    report_diagnostics = report_case["summary"]["diagnostics"]["graph_analysis"]
    assert report_diagnostics["node_metrics_sample"] == []
    assert report_diagnostics["node_metrics_count"] == 0
    assert report_diagnostics["node_metrics_status"] == "skipped_basic_report"


def test_graph_report_and_on_modes_preserve_frozen_seed_service_contract(tmp_path: Path) -> None:
    off_case = _run_frozen_seed_case(tmp_path, "off")
    report_case = _run_frozen_seed_case(tmp_path, "report")
    on_case = _run_frozen_seed_case(tmp_path, "on")

    assert report_case["rows"] == off_case["rows"]
    assert on_case["rows"] == off_case["rows"]
    assert _summary_pr4_signature(report_case["summary"]) == _summary_pr4_signature(off_case["summary"])
    assert _summary_pr4_signature(on_case["summary"]) == _summary_pr4_signature(off_case["summary"])

    lock_statuses = [row[-1] for row in off_case["rows"]]
    assert lock_statuses.count("locked") == 1
    assert lock_statuses.count("unlocked") == 1

    report_graph = report_case["summary"]["algo"]["graph_analysis"]
    assert report_graph["mode"] == "report"
    assert report_graph["effective_mode"] == "report"
    assert report_graph["input_scope"] == "all_algo_ops_with_frozen_markers"
    assert report_graph["total_algo_op_count"] == 2
    assert report_graph["reschedulable_unfrozen_op_count"] == 1
    assert report_graph["frozen_node_count"] == 1
    assert report_graph["seed_result_count"] == 1

    on_graph = on_case["summary"]["algo"]["graph_analysis"]
    assert on_graph["mode"] == "on"
    assert on_graph["effective_mode"] == "graph_ready_queue"
    assert on_graph["ready_queue_enabled"] is True
    assert on_graph["total_algo_op_count"] == 2
    assert on_graph["reschedulable_unfrozen_op_count"] == 1
    assert on_graph["frozen_node_count"] == 1
    assert on_graph["seed_result_count"] == 1

    report_diagnostics = report_case["summary"]["diagnostics"]["graph_analysis"]
    assert report_diagnostics["node_metrics_sample"] == []
    assert report_diagnostics["node_metrics_count"] == 0
    assert report_diagnostics["node_metrics_status"] == "skipped_basic_report"
