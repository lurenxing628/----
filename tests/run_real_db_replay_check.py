"""
真实库回放校验：复制 db/aps.db 到隔离目录，选批次执行排产，抽检甘特/周计划/报表，生成 summary.md 与 JSON 摘要。
环境变量必须在 import app 前设置；仅新增此文件，不修改其他文件。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "app.py").exists() and (p / "schema.sql").exists():
            return p
    raise RuntimeError("未找到仓库根目录：要求存在 app.py 与 schema.sql")


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    _ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, data: bytes) -> None:
    _ensure_dir(path.parent)
    path.write_bytes(data)


def _tomorrow_8am() -> datetime:
    d = date.today() + timedelta(days=1)
    return datetime(d.year, d.month, d.day, 8, 0, 0)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _safe_json_loads(s: Any) -> Dict[str, Any]:
    if s is None:
        return {}
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def _sqlite_backup_copy(src_db: Path, dst_db: Path) -> None:
    """SQLite backup API 做一致性复制。"""
    _ensure_dir(dst_db.parent)
    if dst_db.exists():
        try:
            dst_db.unlink()
        except Exception:
            pass
    src_uri = "file:" + src_db.as_posix() + "?mode=ro"
    src = sqlite3.connect(src_uri, uri=True)
    try:
        dst = sqlite3.connect(str(dst_db))
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()


def _connect_rw(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _priority_rank(priority: str) -> int:
    p = (priority or "").strip().lower()
    if p == "critical":
        return 0
    if p == "urgent":
        return 1
    if p == "normal":
        return 2
    return 3


@dataclass
class SelectedBatches:
    batch_ids: List[str]
    total_ops: int
    statuses: List[str]
    candidates_examined: int


def _select_batches(
    conn: sqlite3.Connection,
    *,
    min_batches: int,
    max_batches: int,
    max_ops: int,
) -> SelectedBatches:
    """
    从 Batches 选择：status 非 completed/cancelled，且有 BatchOperations。
    按 priority 和 due_date 排序，默认 20~50 个批次，op 总数不超过 max_ops。
    """
    sql = """
        SELECT b.batch_id, b.priority, b.due_date, b.status,
               COUNT(bo.id) AS op_count
        FROM Batches b
        INNER JOIN BatchOperations bo ON bo.batch_id = b.batch_id
        WHERE LOWER(COALESCE(b.status, '')) NOT IN ('completed', 'cancelled')
        GROUP BY b.batch_id
        HAVING op_count > 0
        ORDER BY
          CASE LOWER(COALESCE(b.priority, ''))
            WHEN 'critical' THEN 0
            WHEN 'urgent' THEN 1
            WHEN 'normal' THEN 2
            ELSE 3
          END,
          (b.due_date IS NULL) ASC,
          b.due_date ASC,
          b.batch_id ASC
    """
    rows = conn.execute(sql).fetchall()
    candidates = list(rows or [])

    selected: List[Tuple[str, int, str]] = []
    total_ops = 0

    for r in candidates:
        bid = str(r["batch_id"] or "").strip()
        if not bid:
            continue
        op_count = int(r["op_count"] or 0)
        if op_count <= 0:
            continue
        status = str(r["status"] or "").strip()

        if len(selected) >= max_batches:
            break
        if selected and (total_ops + op_count > max_ops) and len(selected) >= min_batches:
            break

        selected.append((bid, op_count, status))
        total_ops += op_count

    statuses = list({x[2] for x in selected if x[2]})
    return SelectedBatches(
        batch_ids=[x[0] for x in selected],
        total_ops=total_ops,
        statuses=statuses,
        candidates_examined=len(candidates),
    )


def _latest_schedule_history(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    row = conn.execute(
        """
        SELECT id, version, result_status, result_summary
        FROM ScheduleHistory
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return row


def _min_start_date(conn: sqlite3.Connection, version: int) -> Optional[str]:
    r = conn.execute(
        "SELECT MIN(start_time) AS st FROM Schedule WHERE version=?",
        (int(version),),
    ).fetchone()
    if not r:
        return None
    st = r["st"]
    if st is None:
        return None
    return str(st)[:10]


def _run_check(
    *,
    app,
    db_path: Path,
    out_dir: Path,
    min_batches: int,
    max_batches: int,
    max_ops: int,
    start_dt: str,
) -> Dict[str, Any]:
    client = app.test_client()

    conn = _connect_rw(db_path)
    try:
        picked = _select_batches(
            conn, min_batches=min_batches, max_batches=max_batches, max_ops=max_ops
        )
    finally:
        conn.close()

    if not picked.batch_ids:
        raise RuntimeError(
            "未能从 DB 中选出可排产批次（status 非 completed/cancelled 且有 BatchOperations）"
        )

    t0 = time.time()
    resp = client.post(
        "/scheduler/run",
        data={"batch_ids": picked.batch_ids, "start_dt": start_dt},
        follow_redirects=True,
    )
    t1 = time.time()

    if getattr(resp, "status_code", None) != 200:
        body = ""
        try:
            body = (resp.data or b"").decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(
            f"POST /scheduler/run 返回 {getattr(resp, 'status_code')}，期望 200；body={body[:500]}"
        )

    conn = _connect_rw(db_path)
    try:
        hist = _latest_schedule_history(conn)
        if not hist:
            raise RuntimeError("未写入 ScheduleHistory")
        version = int(hist["version"])
        week_start = _min_start_date(conn, version=version)
        if not week_start:
            week_start = str(_tomorrow_8am().date().isoformat())
        result_summary = _safe_json_loads(hist["result_summary"])
        result_status = str(hist["result_status"] or "").strip()
    finally:
        conn.close()

    gantt_resp = client.get(
        f"/scheduler/gantt/data?view=machine&week_start={week_start}&version={version}"
    )
    if gantt_resp.status_code != 200:
        raise RuntimeError(
            f"GET /scheduler/gantt/data 返回 {gantt_resp.status_code}，期望 200"
        )
    _write_bytes(out_dir / f"gantt_machine_v{version}.json", gantt_resp.data or b"")

    gantt_payload = _safe_json_loads((gantt_resp.data or b"").decode("utf-8", errors="ignore"))
    gantt_success = bool(gantt_payload.get("success"))
    gantt_data = gantt_payload.get("data") or {}
    gantt_task_count = int(gantt_data.get("task_count", 0))
    gantt_status = "ok" if (gantt_resp.status_code == 200 and gantt_success) else "fail"

    wp_resp = client.get(
        f"/scheduler/week-plan/export?week_start={week_start}&version={version}"
    )
    if wp_resp.status_code != 200:
        raise RuntimeError(
            f"GET /scheduler/week-plan/export 返回 {wp_resp.status_code}，期望 200"
        )
    _write_bytes(out_dir / f"week_plan_v{version}.xlsx", wp_resp.data or b"")
    week_plan_status = "ok" if wp_resp.status_code == 200 else "fail"

    report_urls = [
        ("/reports/", {}),
        ("/reports/overdue", {"version": version}),
        (
            "/reports/utilization",
            {"version": version, "start_date": week_start, "end_date": week_start},
        ),
        (
            "/reports/downtime",
            {"version": version, "start_date": week_start, "end_date": week_start},
        ),
    ]
    report_results: List[Dict[str, Any]] = []
    for path, params in report_urls:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = path + ("?" + qs if qs else "")
        rr = client.get(url)
        report_results.append({"name": path, "url": url, "status_code": rr.status_code})

    return {
        "picked": {
            "batch_count": len(picked.batch_ids),
            "total_ops": picked.total_ops,
            "statuses": picked.statuses,
            "candidates_examined": picked.candidates_examined,
            "batch_ids": picked.batch_ids,
        },
        "schedule": {
            "version": version,
            "result_status": result_status,
            "result_summary": result_summary,
            "week_start": week_start,
            "route_time_cost_s": round(t1 - t0, 3),
            "gantt_success": gantt_success,
            "gantt_task_count": gantt_task_count,
            "gantt_status": gantt_status,
            "week_plan_status": week_plan_status,
        },
        "reports": report_results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="真实库回放校验：副本排产 + 甘特/周计划/报表抽检，生成 summary.md"
    )
    p.add_argument(
        "--out-root",
        default=os.path.join("evidence", "RealDbReplay"),
        help="证据输出根目录（仓库内相对路径）",
    )
    p.add_argument("--min-batches", type=int, default=20, help="尽量选取的最小批次数")
    p.add_argument("--max-batches", type=int, default=50, help="最多选取批次数")
    p.add_argument("--max-ops", type=int, default=1500, help="工序总量上限")
    p.add_argument(
        "--start-dt",
        default=None,
        help="排产开始时间（默认：明天 08:00:00）",
    )
    args = p.parse_args(argv)

    repo_root = _find_repo_root()
    src_db = repo_root / "db" / "aps.db"
    if not src_db.exists():
        print(json.dumps({"ok": False, "summary": "FAIL", "block_reason": "源库不存在"}))
        return 1

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_root = repo_root / str(args.out_root)
    out_dir = out_root / ts
    _ensure_dir(out_dir)
    _ensure_dir(out_dir / "logs")
    _ensure_dir(out_dir / "backups")
    _ensure_dir(out_dir / "templates_excel")

    dst_db = out_dir / "aps_copy.db"
    try:
        _sqlite_backup_copy(src_db, dst_db)
    except Exception:
        shutil.copy2(str(src_db), str(dst_db))

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(dst_db)
    os.environ["APS_LOG_DIR"] = str(out_dir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(out_dir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(out_dir / "templates_excel")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    t_start = time.time()
    block_reason: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    try:
        from app import create_app

        app = create_app()
        start_dt = (
            str(args.start_dt).strip()
            if args.start_dt is not None
            else _fmt_dt(_tomorrow_8am())
        )
        result = _run_check(
            app=app,
            db_path=dst_db,
            out_dir=out_dir,
            min_batches=int(args.min_batches),
            max_batches=int(args.max_batches),
            max_ops=int(args.max_ops),
            start_dt=start_dt,
        )
    except Exception as e:
        block_reason = str(e)
        result = None

    elapsed_s = round(time.time() - t_start, 3)
    ended_at = time.strftime("%Y-%m-%d %H:%M:%S")

    sch = (result or {}).get("schedule") or {}
    picked = (result or {}).get("picked") or {}

    passed = result is not None and block_reason is None
    if result:
        for r in result.get("reports") or []:
            if r.get("status_code") != 200:
                passed = False
                if not block_reason:
                    block_reason = f"{r.get('name')} 返回 {r.get('status_code')}"
        if passed and sch:
            if sch.get("result_status") != "success":
                passed = False
                block_reason = f"result_status={sch.get('result_status')}，期望 success"
            if passed:
                counts = (sch.get("result_summary") or {}) if isinstance(sch.get("result_summary"), dict) else {}
                counts = (counts.get("counts") or {}) if isinstance(counts.get("counts"), dict) else {}
                failed_ops = int(counts.get("failed_ops", 0))
                if failed_ops != 0:
                    passed = False
                    block_reason = f"failed_ops={failed_ops}，期望 0"
            if passed and not sch.get("gantt_success"):
                passed = False
                block_reason = "gantt_success=false"

    version = sch.get("version")
    selected_batch_count = picked.get("batch_count", 0)
    selected_op_count = picked.get("total_ops", 0)

    lines: List[str] = []
    lines.append("# 真实库回放校验摘要")
    lines.append("")
    lines.append(f"- **开始**：{started_at}")
    lines.append(f"- **结束**：{ended_at}")
    lines.append(f"- **耗时**：{elapsed_s}s")
    lines.append(f"- **源 DB**：`{src_db.as_posix()}`")
    lines.append(f"- **副本**：`{dst_db.as_posix()}`")
    lines.append("")
    lines.append(f"- **结论**：{'PASS' if passed else 'FAIL'}")
    if block_reason:
        lines.append(f"- **阻断原因**：{block_reason}")
    lines.append("")
    lines.append("## 选中批次概况")
    lines.append("")
    lines.append(f"- batch_count：{selected_batch_count}")
    lines.append(f"- total_ops：{selected_op_count}")
    lines.append(f"- statuses：{picked.get('statuses', [])}")
    lines.append(f"- candidates_examined：{picked.get('candidates_examined', 0)}")
    lines.append("")
    lines.append("## 排产结果")
    lines.append("")
    if sch:
        counts = (sch.get("result_summary") or {}) if isinstance(sch.get("result_summary"), dict) else {}
        counts = (counts.get("counts") or {}) if isinstance(counts.get("counts"), dict) else {}
        failed_ops = counts.get("failed_ops", 0)
        lines.append(f"- version：{sch.get('version')}")
        lines.append(f"- result_status：{sch.get('result_status')}")
        lines.append(f"- failed_ops：{failed_ops}")
        lines.append(f"- gantt_success：{sch.get('gantt_success')}")
        lines.append(f"- gantt_task_count：{sch.get('gantt_task_count')}")
        lines.append(f"- week_start：{sch.get('week_start')}")
        lines.append(f"- route_time_cost_s：{sch.get('route_time_cost_s')}")
    else:
        lines.append("- 无（排产未完成）")
    lines.append("")
    lines.append("## 路由抽检结果")
    lines.append("")
    for r in (result or {}).get("reports") or []:
        ok_str = "200 OK" if r.get("status_code") == 200 else f"{r.get('status_code')} FAIL"
        lines.append(f"- {r.get('name')}: {ok_str} ({r.get('url')})")
    if not result:
        lines.append("- 排产失败，未执行抽检")
    lines.append("")

    _write_text(out_dir / "summary.md", "\n".join(lines))

    summary_json = {
        "ok": passed,
        "summary": "PASS" if passed else "FAIL",
        "elapsed_s": elapsed_s,
        "version": version,
        "selected_batch_count": selected_batch_count,
        "selected_op_count": selected_op_count,
    }
    if block_reason:
        summary_json["block_reason"] = block_reason

    print(json.dumps(summary_json, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
