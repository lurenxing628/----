"""Owned geometry data, real factory/runtime lifecycle, and separate retention proof."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT
from tests.app_runtime.ui_geometry_contract_data import (
    BATCH,
    PART,
    PLUGIN_PUBLIC_BEGIN,
    PLUGIN_PUBLIC_END,
    PRIVATE_PATH_CANARY,
    RETIRED_GEOMETRY,
)

_BUSINESS_TABLES = (
    "Parts", "Batches", "BatchOperations", "Machines", "Operators", "Schedule",
    "ScheduleHistory", "MachineDowntimes", "Materials", "BatchMaterials", "ScheduleConfig", "SystemConfig",
)
_CONFIG_VALUES = {
    "freeze_window_enabled": "yes", "prefer_primary_skill": "no", "enforce_ready_default": "yes",
    "auto_assign_enabled": "no", "ortools_enabled": "no",
}


def _seed_config_and_material(conn):
    from core.services.scheduler.config.config_service import ConfigService
    from core.services.system.system_config_service import SystemConfigService

    ConfigService(conn).ensure_defaults()
    conn.executemany("UPDATE ScheduleConfig SET config_value=? WHERE config_key=?",
                     [(value, key) for key, value in _CONFIG_VALUES.items()])
    actual = dict(conn.execute("SELECT config_key,config_value FROM ScheduleConfig"))
    assert all(actual[key] == value for key, value in _CONFIG_VALUES.items())
    SystemConfigService(conn).ensure_defaults(backup_keep_days_default=7)
    conn.executemany("UPDATE SystemConfig SET config_value='no' WHERE config_key=?",
                     [(key,) for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled")])
    conn.execute("INSERT INTO Materials(material_id,name,unit,stock_qty) VALUES (?,?,?,?)",
                 ("MAT_UI_GEOMETRY", "几何测试物料", "件", 1))
    conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) VALUES (?,?,?,?,?)",
                 (BATCH, "MAT_UI_GEOMETRY", 1, 1, "yes"))


def _seed_geometry_database(database, *, invalid_history):
    conn = sqlite3.connect(str(database))
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_UI_GEOMETRY", "浏览器几何测试零件", "", "no"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_UI_GEOMETRY", "P_UI_GEOMETRY", "浏览器几何测试零件", 1, "2026-05-01", "normal", "yes", "pending"),
        )
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("M_UI_GEOMETRY", "几何测试设备", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("O_UI_GEOMETRY", "几何测试人员", "active"))
        cur = conn.execute(
            """
            INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name, source, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("OP_UI_GEOMETRY", "B_UI_GEOMETRY", 1, "加工", "internal", "pending"),
        )
        op_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op_id,
                "M_UI_GEOMETRY",
                "O_UI_GEOMETRY",
                "2026-05-06 08:00:00",
                "2026-05-06 12:00:00",
                "unlocked",
                1,
            ),
        )
        conn.execute(
            """
            INSERT INTO MachineDowntimes (machine_id, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("M_UI_GEOMETRY", "2026-05-06 09:00:00", "2026-05-06 10:00:00", "maintenance", "几何测试停机", "active"),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory
                (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 09:00:00",
                1,
                "priority_first",
                1,
                1,
                "success",
                json.dumps(
                    {
                        "algo": {
                            "mode": "improve",
                            "objective": "min_overdue",
                            "metrics": {
                                "total_tardiness_hours": 0,
                                "weighted_tardiness_hours": 0,
                                "makespan_hours": 1,
                                "changeover_count": 0,
                                "machine_util_avg": 0.5,
                            },
                        },
                        "warnings": [],
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                "ui-smoke",
            ),
        )
        if invalid_history:
            conn.execute(
                """
                INSERT INTO ScheduleHistory
                    (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-05-06 10:00:00",
                    2,
                    "priority_first",
                    1,
                    1,
                    "failed",
                    "{bad json",
                    "ui-smoke",
                ),
            )
        conn.execute(
            """
            INSERT INTO OperationLogs
                (log_time, log_level, module, action, target_type, target_id, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 10:30:00",
                "ERROR",
                "plugins",
                "toggle",
                "plugin",
                "ui-smoke-plugin",
                "{bad json",
                "PLUGIN_LOAD_FAILED",
                "历史日志里保留 Traceback / Werkzeug / Internal Server Error 字样，用于确认正常应用页面不会被误判成错误页。",
            ),
        )
        _seed_config_and_material(conn)
        conn.commit()
    finally:
        conn.close()


def _fixture_plugin_status(root):
    # Only the loader result is injected; bootstrap sanitization and its DB audit run unchanged.
    return {
        "loaded_at": "2026-05-06 09:00:00",
        "vendor_paths": [str(root / PRIVATE_PATH_CANARY)],
        "plugins_dir": str(root / PRIVATE_PATH_CANARY),
        "statuses": [{
            "plugin_id": "geometry-startup",
            "name": PLUGIN_PUBLIC_BEGIN + "：启动时发现扩展资料不完整，请核查本次运行记录。" * 8,
            "version": "1.0",
            "enabled": "yes",
            "loaded": "no",
            "error": "Fixture plugin load error at " + str(root / PRIVATE_PATH_CANARY),
            "capabilities": [PLUGIN_PUBLIC_END],
        }],
    }


def retention_snapshot(app):
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        business = {table: list(conn.execute("SELECT * FROM " + table + " ORDER BY rowid"))
                    for table in _BUSINESS_TABLES}
        audits = list(conn.execute("SELECT * FROM OperationLogs WHERE module='plugins' AND action='load' ORDER BY id"))
    return {"business": business, "startup_audit": audits}


def assert_geometry_retention(app):
    evidence = app.extensions["ui_geometry_evidence"]
    current = retention_snapshot(app)
    assert current == evidence["before"], "Read-only geometry changed business/configuration/startup-audit rows"
    assert current["business"]["ScheduleConfig"], "ScheduleConfig preservation had no rows"
    assert current["startup_audit"], "Plugin startup audit was not persisted"


def assert_retired_geometry_boundary(app):
    policy = RETIRED_GEOMETRY["scheduler.config"]
    response = app.test_client().get(policy["path"], follow_redirects=False)
    try:
        assert response.status_code == policy["status"] == 410
        html = response.get_data(as_text=True)
        assert "旧入口已退役" in html
        assert "原业务数据、保存的配置和历史记录仍保留" in html
        assert all('id="' + name + '"' not in html for name in policy["controls"])
    finally:
        response.close()
    assert_geometry_retention(app)


def _json_read(app, path):
    response = app.test_client().get(path)
    try:
        assert response.status_code == 200, (path, response.status_code, response.get_data(as_text=True))
        payload = response.get_json()
        assert payload and payload["ok"] is True, path
        return payload["data"]
    finally:
        response.close()


def _fixture_identity(app, *, invalid_history):
    from core.models.operation_log_public_projection import public_operation_log_detail_text
    from core.services.workbench.system_redaction import public_system_text

    plans = _json_read(app, "/api/workbench/v1/plans?collection=history&size=20")["plans"]
    valid = [row for row in plans if row["kind"] == "official" and row["version"] == 1]
    invalid = [row for row in plans if row["kind"] == "official" and row["version"] == 2]
    assert len(valid) == 1 and len(invalid) == int(invalid_history)
    assert valid[0]["capabilities"]["view"] is True
    if invalid_history:
        assert invalid[0]["capabilities"]["view"] is False
    else:
        assert valid[0]["is_current_official"] is True
    plan = valid[0]
    workspace = _json_read(app, "/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace")
    tasks = [task for task in workspace["tasks"] if task["batch_id"] == BATCH]
    assert len(tasks) == 1
    batches = _json_read(app, "/api/workbench/v1/entities/batch?query=" + BATCH)["entities"]
    batches = [row for row in batches if row["business_code"] == BATCH]
    assert len(batches) == 1
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        logs = list(conn.execute("SELECT detail,error_message FROM OperationLogs WHERE module='plugins' AND action='load'"))
        normal_logs = list(conn.execute("SELECT detail,error_message FROM OperationLogs WHERE module='plugins' AND action='toggle'"))
    assert len(logs) == 1 and app.config["PLUGIN_STATUS"]["telemetry_persisted"] is True
    raw, error = logs[0]
    assert PRIVATE_PATH_CANARY in raw
    public = public_system_text(public_operation_log_detail_text(raw) + "\n" + str(error or ""))
    assert PLUGIN_PUBLIC_BEGIN in public and PLUGIN_PUBLIC_END in public
    assert PRIVATE_PATH_CANARY not in public and "[展示长度已截断]" not in public
    assert len(normal_logs) == 1
    normal_raw, normal_error = normal_logs[0]
    normal_public = public_system_text(public_operation_log_detail_text(normal_raw) + "\n" + str(normal_error or ""))
    assert all(word in normal_public for word in ("{bad json", "Traceback", "Werkzeug", "Internal Server Error"))
    return {"plan_ref": plan["plan_ref"], "plan_name": plan["display_name"], "version": 1,
            "batch_id": BATCH, "part_no": PART, "batch_ref": batches[0]["ref"],
            "task_ref": tasks[0]["task_ref"], "machine_ref": tasks[0]["machine_ref"],
            "operator_ref": tasks[0]["operator_ref"], "invalid_plan_name": invalid[0]["display_name"] if invalid_history else None,
            "startup_public_body": public, "normal_public_body": normal_public, "private_path_canary": PRIVATE_PATH_CANARY}


@contextmanager
def managed_geometry_app(tmp_path, monkeypatch, *, invalid_history=True):
    from core.infrastructure.database import ensure_schema
    from core.plugins import PluginManager
    from core.services.workbench.system_journal import assert_system_maintenance_ready
    from web.bootstrap.entrypoint import create_app_with_mode
    from web.bootstrap.launcher_paths import db_scope_lock_path
    from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
    from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
    from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

    root = Path(tmp_path).resolve()
    database, journal = root / "aps_ui_geometry.db", root / "journal"
    assert not database.exists(), "Geometry fixture must not reuse a database"
    for name in ("logs", "backups", "journal"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for key, value in {"APS_ENV": "production", "APS_DB_PATH": str(database), "APS_LOG_DIR": str(root / "logs"),
                       "APS_BACKUP_DIR": str(root / "backups"), "APS_SYSTEM_JOURNAL_DIR": str(journal)}.items():
        monkeypatch.setenv(key, value)
    point_env_at_shared(monkeypatch)
    assert_system_maintenance_ready(str(database), str(journal))
    ensure_schema(str(database), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    _seed_geometry_database(database, invalid_history=invalid_history)
    payload = acquire_runtime_lock(str(root), cfg_log_dir=str(root / "logs"), db_path=str(database))
    runtime, gate = None, None
    try:
        with monkeypatch.context() as startup:
            startup.setattr(PluginManager, "load_from_base_dir", lambda *args, **kwargs: _fixture_plugin_status(root))
            app = create_app_with_mode("default")
        assert Path(app.config["DATABASE_PATH"]) == database
        gate = app.extensions["workbench_request_lifecycle"]
        runtime = install_workbench_run_runtime(app, runtime_lock=payload)
        assert runtime.ready, runtime.status
        host = install_workbench_system_restore_host(app, runtime=runtime)
        assert host.status["state"] == "ready"
        evidence = {"before": retention_snapshot(app)}
        app.extensions["ui_geometry_evidence"] = evidence
        evidence["identity"] = _fixture_identity(app, invalid_history=invalid_history)
        assert_geometry_retention(app)
        yield app
        assert_geometry_retention(app)
    finally:
        gate_stopped = gate.shutdown(timeout=20) if gate is not None else True
        runtime_stopped = runtime.shutdown(timeout=20) if runtime is not None else True
        assert gate_stopped and runtime_stopped, "Geometry fixture did not drain"
        release_runtime_lock(payload["state_dir"], db_path=str(database))
        assert not Path(payload["path"]).exists() and not Path(db_scope_lock_path(str(database))).exists()
