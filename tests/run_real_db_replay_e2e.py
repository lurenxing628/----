from __future__ import annotations

"""
真实库排产回放抽检（严格不污染原 db/aps.db）：

- 复制 db/aps.db 到 evidence/RealDbReplay/<timestamp>/aps_copy.db
- 创建最小副作用 Flask app（参考 create_test_app）：每请求 get_connection、ensure_excel_templates、ensure_schema
- 自动挑选批次（排除 completed/cancelled，优先 pending，其次 scheduled/processing；按 priority+due_date 排序）
- POST /scheduler/run → 抽检 gantt/week-plan/reports
- 输出 summary.md + 导出物

运行示例：
  python tests/run_real_db_replay_e2e.py
  python tests/run_real_db_replay_e2e.py --max-batches 50 --max-ops 2000
"""

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _find_repo_root() -> Path:
    for base in [Path(__file__).resolve(), Path.cwd().resolve()]:
        p = base if base.is_dir() else base.parent
        for _ in range(12):
            if (p / "app.py").exists() and (p / "schema.sql").exists():
                return p
            if p.parent == p:
                break
            p = p.parent
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_text(p: Path, text: str) -> None:
    _ensure_dir(p.parent)
    p.write_text(text, encoding="utf-8")


def _write_bytes(p: Path, data: bytes) -> None:
    _ensure_dir(p.parent)
    p.write_bytes(data)


def _tomorrow_8am() -> datetime:
    d = date.today() + timedelta(days=1)
    return datetime(d.year, d.month, d.day, 8, 0, 0)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _priority_order_expr(col: str = "priority") -> str:
    return f"CASE {col} WHEN 'critical' THEN 0 WHEN 'urgent' THEN 1 ELSE 2 END"


def _status_order_expr(col: str = "status") -> str:
    """pending 优先，其次 scheduled、processing"""
    return f"CASE {col} WHEN 'pending' THEN 0 WHEN 'scheduled' THEN 1 WHEN 'processing' THEN 2 ELSE 3 END"


@dataclass
class SelectedBatches:
    batch_ids: List[str]
    total_ops: int
    per_batch_ops: Dict[str, int]
    selected_by: str


def _select_batches(conn, *, max_batches: int, max_ops: int) -> SelectedBatches:
    """
    排除 completed/cancelled；优先 pending，其次 scheduled/processing；
    按 priority(critical>urgent>normal)+due_date 排序；逐个累加 op_count 直到 max_ops 或 max_batches。
    """
    max_batches = max(int(max_batches), 1)
    max_ops = max(int(max_ops), 1)

    sql = """
    SELECT
      b.batch_id,
      b.priority,
      b.due_date,
      b.status,
      COUNT(bo.id) AS op_count
    FROM Batches b
    LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
    WHERE b.status NOT IN (?, ?)
    GROUP BY b.batch_id
    HAVING op_count > 0
    ORDER BY
      """ + _status_order_expr("b.status") + """,
      """ + _priority_order_expr("b.priority") + """,
      (b.due_date IS NULL) ASC,
      b.due_date ASC,
      b.batch_id ASC
    """
    rows = conn.execute(sql, ("completed", "cancelled")).fetchall()
    rows = [dict(r) for r in rows]

    batch_ids: List[str] = []
    per_batch_ops: Dict[str, int] = {}
    total_ops = 0
    for r in rows:
        bid = str(r.get("batch_id") or "").strip()
        if not bid:
            continue
        op_count = int(r.get("op_count") or 0)
        if op_count <= 0 or bid in per_batch_ops:
            continue

        if batch_ids and (total_ops + op_count) > max_ops:
            break

        batch_ids.append(bid)
        per_batch_ops[bid] = op_count
        total_ops += op_count

        if len(batch_ids) >= max_batches:
            break

    return SelectedBatches(
        batch_ids=batch_ids,
        total_ops=total_ops,
        per_batch_ops=per_batch_ops,
        selected_by="pending_then_scheduled_processing",
    )


def _latest_schedule_history(conn) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT id, version, result_status, result_summary, schedule_time AS created_at FROM ScheduleHistory ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["result_summary_json"] = json.loads(d.get("result_summary") or "{}")
    except Exception:
        d["result_summary_json"] = None
    return d


def _min_start_date(conn, *, version: int) -> Optional[str]:
    row = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (int(version),)).fetchone()
    if not row or not row[0]:
        return None
    return str(row[0])[:10]


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _create_test_app(*, repo_root: Path, db_path: Path, log_dir: Path, backup_dir: Path, template_dir: Path):
    """
    最小副作用 Flask app：每请求 get_connection、ensure_excel_templates、ensure_schema。
    不模拟正式 create_app_core() 的维护窗口短路，仅对齐请求级 g.services 挂载与目标白名单行为。
    """
    from flask import Flask, g, request

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.common.excel_backend_factory import get_excel_backend
    from core.services.common.excel_templates import ensure_excel_templates
    from web.bootstrap.request_services import RequestServices
    from web.error_handlers import register_error_handlers
    from web.routes.dashboard import bp as dashboard_bp
    from web.routes.equipment import bp as equipment_bp
    from web.routes.excel_demo import bp as excel_demo_bp
    from web.routes.material import bp as material_bp
    from web.routes.personnel import bp as personnel_bp
    from web.routes.process import bp as process_bp
    from web.routes.reports import bp as reports_bp
    from web.routes.scheduler import bp as scheduler_bp
    from web.routes.system import bp as system_bp
    from web.ui_mode import init_ui_mode

    static_dir = repo_root / "static"
    templates_dir = repo_root / "templates"
    app = Flask(
        __name__,
        static_folder=str(static_dir),
        template_folder=str(templates_dir),
    )
    app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "aps-replay-key",
            "DATABASE_PATH": str(db_path),
            "LOG_DIR": str(log_dir),
            "BACKUP_DIR": str(backup_dir),
            "EXCEL_TEMPLATE_DIR": str(template_dir),
        }
    )

    def tojson_zh(value, indent: int = 2):
        return json.dumps(value, ensure_ascii=False, indent=indent, default=str)

    app.jinja_env.filters["tojson_zh"] = tojson_zh

    _ensure_dir(db_path.parent if db_path.parent else Path("."))
    _ensure_dir(log_dir)
    _ensure_dir(backup_dir)
    _ensure_dir(template_dir)

    init_ui_mode(app, str(repo_root))
    ensure_excel_templates(str(template_dir))
    ensure_schema(
        str(db_path),
        logger=None,
        schema_path=str(repo_root / "schema.sql"),
        backup_dir=str(backup_dir),
    )

    @app.before_request
    def _open_db():
        try:
            req_path = str(request.path or "")
            # 与正式工厂一致：白名单短路路径不挂载 g.app_logger / g.db / g.op_logger / g.services，
            # 保持“纯静态/健康检查请求不进入业务主路径”的边界，避免测试工厂与正式行为漂移。
            # 若未来测试需要这些请求级对象，应改走业务路径而不是扩展白名单短路语义。
            if req_path.startswith("/static") or req_path in {"/system/health", "/system/runtime/shutdown"}:
                return
        except Exception as exc:
            app.logger.warning("请求白名单判定失败，将继续主路径：%s", exc)
        g.app_logger = app.logger
        if "db" in g and "services" not in g:
            raise RuntimeError("请求上下文已有 g.db，但缺少 g.services。")
        if "db" not in g:
            conn = None
            try:
                conn = get_connection(app.config["DATABASE_PATH"])
                op_logger = OperationLogger(conn, logger=getattr(app, "logger", None))
                services = RequestServices(
                    db=conn,
                    app_logger=g.app_logger,
                    op_logger=op_logger,
                    get_excel_backend=get_excel_backend,
                )
            except Exception:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception as close_exc:
                        app.logger.warning("测试应用请求级容器装配失败后的数据库关闭失败：%s", close_exc)
                raise
            g.db = conn
            g.op_logger = op_logger
            g.services = services

    @app.teardown_appcontext
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    register_error_handlers(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(excel_demo_bp, url_prefix="/excel-demo")
    app.register_blueprint(personnel_bp, url_prefix="/personnel")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(process_bp, url_prefix="/process")
    app.register_blueprint(scheduler_bp, url_prefix="/scheduler")
    app.register_blueprint(material_bp, url_prefix="/material")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(system_bp, url_prefix="/system")

    return app


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="真实库排产回放抽检（db/aps.db -> 副本，不污染原库）")
    p.add_argument("--out", default=os.path.join("evidence", "RealDbReplay"), help="证据输出根目录")
    p.add_argument("--max-batches", type=int, default=30, help="最多选择批次数（默认 30）")
    p.add_argument("--max-ops", type=int, default=2000, help="最多累计工序数（默认 2000）")
    args = p.parse_args(list(argv) if argv is not None else None)

    repo_root = _find_repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    src_db = repo_root / "db" / "aps.db"
    if not src_db.exists():
        raise RuntimeError(f"真实库不存在：{src_db.as_posix()}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_base = repo_root / str(args.out)
    out_dir = out_base / ts
    logs_dir = out_dir / "logs"
    backups_dir = out_dir / "backups"
    templates_dir = out_dir / "templates_excel"
    _ensure_dir(out_dir)

    db_copy = out_dir / "aps_copy.db"
    shutil.copy2(str(src_db), str(db_copy))

    app = _create_test_app(
        repo_root=repo_root,
        db_path=db_copy,
        log_dir=logs_dir,
        backup_dir=backups_dir,
        template_dir=templates_dir,
    )
    client = app.test_client()

    from core.infrastructure.database import get_connection

    conn = get_connection(str(db_copy))
    picked = _select_batches(conn, max_batches=int(args.max_batches), max_ops=int(args.max_ops))
    config_snapshot: Optional[Dict[str, Any]] = None
    try:
        from core.services.scheduler.config_service import ConfigService

        config_snapshot = ConfigService(conn).get_snapshot().to_dict()
    except Exception:
        pass
    try:
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    start_dt = _tomorrow_8am()

    checks: Dict[str, Any] = {
        "schedule_run": {"ok": False, "status_code": None, "error": None},
        "gantt_data": {"ok": False, "status_code": None, "success": None, "task_count": None, "error": None},
        "week_plan_export": {"ok": False, "status_code": None, "bytes": None, "error": None},
        "reports": [],
    }

    schedule_info: Dict[str, Any] = {}
    issues: List[str] = []

    t0 = time.perf_counter()
    if not picked.batch_ids:
        issues.append("未选到任何可排产批次（排除 completed/cancelled 后无 op_count>0 的批次）")
    else:
        try:
            resp = client.post(
                "/scheduler/run",
                data={"batch_ids": list(picked.batch_ids), "start_dt": _fmt_dt(start_dt)},
                follow_redirects=True,
            )
            checks["schedule_run"]["status_code"] = int(resp.status_code)
            checks["schedule_run"]["ok"] = (resp.status_code == 200)
            if resp.status_code != 200:
                issues.append(f"/scheduler/run 返回非200：{resp.status_code}")
        except Exception as e:
            checks["schedule_run"]["error"] = str(e)
            issues.append(f"/scheduler/run 调用异常：{e}")

    t_schedule = time.perf_counter() - t0

    conn = get_connection(str(db_copy))
    try:
        hist = _latest_schedule_history(conn)
        if not hist:
            issues.append("未找到 ScheduleHistory（排产未落库或库结构异常）")
        else:
            schedule_info["history"] = {
                "id": hist.get("id"),
                "version": hist.get("version"),
                "result_status": hist.get("result_status"),
                "created_at": hist.get("created_at"),
            }
            summary_json = hist.get("result_summary_json")
            schedule_info["result_summary"] = summary_json

            sj = _as_dict(summary_json)
            counts = _as_dict(sj.get("counts"))
            overdue = _as_dict(sj.get("overdue_batches"))
            algo = _as_dict(sj.get("algo"))
            metrics = _as_dict(algo.get("metrics"))
            time_cost_ms = sj.get("time_cost_ms")
            schedule_info["counts"] = counts
            schedule_info["overdue"] = overdue
            schedule_info["algo_metrics"] = metrics
            schedule_info["time_cost_ms"] = time_cost_ms

            raw_version = hist.get("version")
            try:
                if raw_version is None:
                    raise TypeError("version is None")
                ver = int(raw_version)
            except Exception:
                ver = None
                issues.append(f"ScheduleHistory.version 非整数：{raw_version}")

            if ver is not None:
                week_start = _min_start_date(conn, version=ver) or start_dt.date().isoformat()
                schedule_info["week_start"] = week_start

                op_count = int(counts.get("op_count") or 0)
                scheduled_ops = int(counts.get("scheduled_ops") or 0)
                failed_ops = int(counts.get("failed_ops") or 0)
                if op_count and scheduled_ops != op_count:
                    issues.append(f"排产覆盖率异常：scheduled_ops={scheduled_ops} op_count={op_count}")
                if failed_ops > 0:
                    issues.append(f"排产存在失败工序：failed_ops={failed_ops}")

                gantt_resp = client.get(
                    f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={ver}")
                checks["gantt_data"]["status_code"] = int(gantt_resp.status_code)
                if gantt_resp.status_code != 200:
                    issues.append(f"/scheduler/gantt/data 返回非200：{gantt_resp.status_code}")
                else:
                    payload = json.loads(gantt_resp.data.decode("utf-8", errors="replace"))
                    ok2 = bool(payload.get("success"))
                    data = _as_dict(payload.get("data"))
                    tc = data.get("task_count")
                    task_count = int(tc) if tc is not None else None
                    checks["gantt_data"]["success"] = ok2
                    checks["gantt_data"]["task_count"] = task_count
                    checks["gantt_data"]["ok"] = ok2 and (task_count is not None and task_count > 0)
                    if not ok2:
                        issues.append(f"/scheduler/gantt/data success=false：{payload}")
                    elif task_count is None or task_count <= 0:
                        issues.append(f"/scheduler/gantt/data task_count={task_count}（要求>0）")
                    if ok2 and task_count and task_count > 0:
                        _write_bytes(out_dir / f"gantt_machine_v{ver}.json", gantt_resp.data)

                wp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version={ver}")
                checks["week_plan_export"]["status_code"] = int(wp.status_code)
                checks["week_plan_export"]["ok"] = (wp.status_code == 200)
                if wp.status_code != 200:
                    issues.append(f"/scheduler/week-plan/export 返回非200：{wp.status_code}")
                else:
                    b = bytes(wp.data or b"")
                    checks["week_plan_export"]["bytes"] = len(b)
                    _write_bytes(out_dir / f"week_plan_v{ver}.xlsx", b)

                report_urls = [
                    ("/reports/", "/reports/"),
                    ("/reports/overdue", f"/reports/overdue?version={ver}"),
                    ("/reports/utilization", f"/reports/utilization?version={ver}&start_date={week_start}&end_date={week_start}"),
                    ("/reports/downtime", f"/reports/downtime?version={ver}&start_date={week_start}&end_date={week_start}"),
                ]
                for name, url in report_urls:
                    try:
                        rr = client.get(url)
                        ok3 = (rr.status_code == 200)
                        checks["reports"].append(
                            {"name": name, "url": url, "status_code": int(rr.status_code), "ok": ok3}
                        )
                        if not ok3:
                            issues.append(f"报表页不可访问：{name} status={rr.status_code}")
                    except Exception as e:
                        checks["reports"].append({"name": name, "url": url, "status_code": None, "ok": False, "error": str(e)})
                        issues.append(f"报表页调用异常：{name} err={e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    ok = len(issues) == 0

    result_obj = {
        "ok": ok,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "repo_root": str(repo_root),
        "src_db": str(src_db),
        "db_copy": str(db_copy),
        "out_dir": str(out_dir),
        "start_dt": _fmt_dt(start_dt),
        "selected": {
            "strategy": picked.selected_by,
            "batch_count": len(picked.batch_ids),
            "batch_ids": picked.batch_ids,
            "total_ops": picked.total_ops,
            "per_batch_ops": picked.per_batch_ops,
            "max_batches": int(args.max_batches),
            "max_ops": int(args.max_ops),
        },
        "schedule_info": schedule_info,
        "config_snapshot": config_snapshot,
        "checks": checks,
        "timing_s": {"schedule_call": float(round(t_schedule, 6))},
        "issues": issues,
    }
    _write_text(out_dir / "result.json", json.dumps(result_obj, ensure_ascii=False, indent=2, default=str))

    lines: List[str] = []
    lines.append("# 真实库排产回放抽检报告")
    lines.append("")
    lines.append(f"- 生成时间：{result_obj['generated_at']}")
    lines.append(f"- 源 DB：`{src_db.as_posix()}`")
    lines.append(f"- 副本 DB：`{db_copy.as_posix()}`")
    lines.append(f"- 选中 batch_ids 数：{len(picked.batch_ids)}，expected_ops：{picked.total_ops}")
    lines.append(f"- /scheduler/run 耗时：{round(t_schedule, 3)}s")
    lines.append(f"- start_dt：`{_fmt_dt(start_dt)}`")
    lines.append("")

    lines.append("## 结论")
    lines.append("")
    lines.append(f"- **PASS/FAIL：{'PASS' if ok else 'FAIL'}**")
    lines.append("")

    h = _as_dict(schedule_info.get("history"))
    ver_val = h.get("version")
    week_start_val = schedule_info.get("week_start")
    result_status = h.get("result_status")
    c = _as_dict(schedule_info.get("counts"))
    od = _as_dict(schedule_info.get("overdue"))
    metrics_d = _as_dict(schedule_info.get("algo_metrics"))
    time_cost_ms_val = schedule_info.get("time_cost_ms")

    lines.append("## 排产摘要")
    lines.append("")
    lines.append(f"- version：{ver_val}")
    lines.append(f"- week_start：{week_start_val}")
    lines.append(f"- result_status：{result_status}")
    lines.append(f"- counts：op_count={c.get('op_count')} scheduled_ops={c.get('scheduled_ops')} failed_ops={c.get('failed_ops')}")
    lines.append(f"- overdue_batches.count：{od.get('count')}")
    if time_cost_ms_val is not None:
        lines.append(f"- time_cost_ms：{time_cost_ms_val}")
    if metrics_d:
        lines.append(f"- algo.metrics：{json.dumps(metrics_d, ensure_ascii=False)[:500]}...")
    lines.append("")

    lines.append("## 路由抽检 PASS/FAIL")
    lines.append("")
    sr = checks["schedule_run"]
    lines.append(f"- /scheduler/run：{'PASS' if sr['ok'] else 'FAIL'}（status={sr['status_code']}）")
    gd = checks["gantt_data"]
    lines.append(f"- /scheduler/gantt/data：{'PASS' if gd['ok'] else 'FAIL'}（success={gd['success']} task_count={gd['task_count']}）")
    wp = checks["week_plan_export"]
    lines.append(f"- /scheduler/week-plan/export：{'PASS' if wp['ok'] else 'FAIL'}（status={wp['status_code']} bytes={wp['bytes']}）")
    for r in checks.get("reports") or []:
        lines.append(f"- {r.get('name')}：{'PASS' if r.get('ok') else 'FAIL'}（status={r.get('status_code')}）")
    lines.append("")

    if config_snapshot:
        lines.append("## 关键配置快照")
        lines.append("")
        for k, v in list(config_snapshot.items())[:20]:
            lines.append(f"- {k}：{v}")
        if len(config_snapshot) > 20:
            lines.append(f"- ...（共 {len(config_snapshot)} 项，完整见 result.json）")
        lines.append("")

    if issues:
        lines.append("## 问题")
        lines.append("")
        for x in issues:
            lines.append(f"- {x}")
        lines.append("")

    lines.append("## 产物")
    lines.append("")
    lines.append("- `result.json`")
    for pth in sorted(out_dir.glob("gantt_*.json")):
        lines.append(f"- `{pth.name}`")
    for pth in sorted(out_dir.glob("week_plan_v*.xlsx")):
        lines.append(f"- `{pth.name}`")
    lines.append("- `summary.md`")
    lines.append("")

    _write_text(out_dir / "summary.md", "\n".join(lines) + "\n")

    print(str(out_dir / "summary.md"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
