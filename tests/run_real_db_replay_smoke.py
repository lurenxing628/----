from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


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
    """
    以 SQLite backup API 做一致性复制：
    - 读源库（只读打开）
    - 写入目标库（覆盖/创建）
    """
    _ensure_dir(dst_db.parent)
    if dst_db.exists():
        try:
            dst_db.unlink()
        except Exception:
            pass
    src_uri = f"file:{src_db.as_posix()}?mode=ro"
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


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


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
    source_statuses: List[str]
    candidates_examined: int


def _list_batches_with_op_counts(
    conn: sqlite3.Connection, *, statuses: Sequence[str], limit: int
) -> List[sqlite3.Row]:
    if not statuses:
        return []
    placeholders = ",".join(["?"] * len(statuses))
    sql = f"""
        SELECT
          b.batch_id,
          b.priority,
          b.due_date,
          b.status,
          COUNT(bo.id) AS op_count
        FROM Batches b
        LEFT JOIN BatchOperations bo
          ON bo.batch_id = b.batch_id
        WHERE b.status IN ({placeholders})
        GROUP BY b.batch_id
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
        LIMIT ?
    """
    rows = conn.execute(sql, tuple([*statuses, int(limit)])).fetchall()
    return list(rows or [])


def _select_batches(
    conn: sqlite3.Connection,
    *,
    min_batches: int,
    max_batches: int,
    op_limit: int,
) -> SelectedBatches:
    statuses_order = [
        ["pending"],
        ["pending", "scheduled", "processing"],
        ["scheduled", "processing"],
    ]

    for statuses in statuses_order:
        candidates = _list_batches_with_op_counts(conn, statuses=statuses, limit=max_batches * 20)
        # (batch_id, op_count, priority, due_date)
        selected: List[Tuple[str, int, str, Any]] = []
        total_ops = 0

        for r in candidates:
            bid = str(r["batch_id"] or "").strip()
            if not bid:
                continue
            op_count = int(r["op_count"] or 0)
            if op_count <= 0:
                continue
            due = r["due_date"]
            pr = str(r["priority"] or "").strip()

            # 达到 max_batches 直接停；达到 op_limit 且已满足 min_batches 则停
            if selected and len(selected) >= int(max_batches):
                break
            if selected and (total_ops + op_count > int(op_limit)) and len(selected) >= int(min_batches):
                break

            selected.append((bid, op_count, pr, due))
            total_ops += op_count

        if selected:
            # 兜底按“更稳定”的排序（避免 DB 中 due_date 类型差异导致排序不稳定）
            selected.sort(key=lambda x: (_priority_rank(x[2]), str(x[3] or ""), x[0]))
            batch_ids = [x[0] for x in selected]
            return SelectedBatches(
                batch_ids=batch_ids,
                total_ops=int(total_ops),
                source_statuses=list(statuses),
                candidates_examined=len(candidates),
            )

    return SelectedBatches(batch_ids=[], total_ops=0, source_statuses=[], candidates_examined=0)


def _latest_schedule_history(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    row = conn.execute(
        """
        SELECT
          id,
          schedule_time,
          version,
          strategy,
          batch_count,
          op_count,
          result_status,
          result_summary,
          created_by
        FROM ScheduleHistory
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return row


def _min_start_date(conn: sqlite3.Connection, *, version: int) -> Optional[str]:
    r = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (int(version),)).fetchone()
    if not r:
        return None
    st = r["st"]
    if st is None:
        return None
    return str(st)[:10]


def _assert_status(name: str, resp, expect_code: int = 200) -> None:
    if getattr(resp, "status_code", None) != expect_code:
        body = ""
        try:
            body = (resp.data or b"").decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {getattr(resp, 'status_code', None)}，期望 {expect_code}；body={body[:500]}")


def _run_replay(
    *,
    app,
    db_path: Path,
    out_dir: Path,
    view: str,
    min_batches: int,
    max_batches: int,
    op_limit: int,
    start_dt: str,
) -> Dict[str, Any]:
    client = app.test_client()

    # 选择批次
    conn = _connect_rw(db_path)
    try:
        picked = _select_batches(conn, min_batches=int(min_batches), max_batches=int(max_batches), op_limit=int(op_limit))
    finally:
        conn.close()

    if not picked.batch_ids:
        raise RuntimeError("未能从 DB 中选出可排产批次（pending/scheduled/processing 均为空或无工序）")

    # 排产（走 Web 路由）
    t0 = time.time()
    resp = client.post("/scheduler/run", data={"batch_ids": picked.batch_ids, "start_dt": str(start_dt)}, follow_redirects=True)
    _assert_status("POST /scheduler/run (follow redirects)", resp, 200)
    t1 = time.time()

    # 读最新版本 + 结果摘要
    conn = _connect_rw(db_path)
    try:
        hist = _latest_schedule_history(conn)
        if not hist:
            raise RuntimeError("未写入 ScheduleHistory（无法获取 version）")
        version = int(hist["version"])
        week_start = _min_start_date(conn, version=version)
        if not week_start:
            week_start = str(_tomorrow_8am().date().isoformat())
        result_summary = _safe_json_loads(hist["result_summary"])
        result_status = str(hist["result_status"] or "").strip()

        # 写一份 schedule history 解析结果，便于后续追溯
        _write_text(
            out_dir / f"schedule_history_v{version}.json",
            json.dumps(
                {
                    "version": version,
                    "result_status": result_status,
                    "result_summary": result_summary,
                    "schedule_time": hist["schedule_time"],
                    "strategy": hist["strategy"],
                    "batch_count": hist["batch_count"],
                    "op_count": hist["op_count"],
                    "created_by": hist["created_by"],
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n",
        )
    finally:
        conn.close()

    # 甘特数据
    gantt = client.get(f"/scheduler/gantt/data?view={view}&week_start={week_start}&version={version}")
    _assert_status("GET /scheduler/gantt/data", gantt, 200)
    _write_bytes(out_dir / f"gantt_{view}_v{version}.json", gantt.data or b"")

    # 周计划导出
    wp = client.get(f"/scheduler/week-plan/export?week_start={week_start}&version={version}")
    _assert_status("GET /scheduler/week-plan/export", wp, 200)
    _write_bytes(out_dir / f"week_plan_v{version}.xlsx", wp.data or b"")

    # 报表页抽检（只要能访问即可；不引入强断言避免因真实库差异误报）
    report_checks = [
        ("GET /reports/", "/reports/"),
        ("GET /reports/overdue", f"/reports/overdue?version={version}"),
        ("GET /reports/utilization", f"/reports/utilization?version={version}&start_date={week_start}&end_date={week_start}"),
        ("GET /reports/downtime", f"/reports/downtime?version={version}&start_date={week_start}&end_date={week_start}"),
    ]
    report_results: List[Dict[str, Any]] = []
    for name, url in report_checks:
        rr = client.get(url)
        report_results.append({"name": name, "url": url, "status_code": int(getattr(rr, "status_code", 0) or 0)})

    return {
        "db": str(db_path),
        "out_dir": str(out_dir),
        "view": view,
        "picked": {
            "batch_count": len(picked.batch_ids),
            "total_ops": picked.total_ops,
            "statuses": picked.source_statuses,
            "candidates_examined": picked.candidates_examined,
            "batch_ids": picked.batch_ids,
        },
        "schedule": {
            "start_dt": start_dt,
            "version": version,
            "week_start": week_start,
            "route_time_cost_s": round(t1 - t0, 3),
            "result_status": result_status,
            "result_summary": result_summary,
        },
        "reports": report_results,
    }


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="基于真实库 db/aps.db 的副本进行排产回放抽检（不污染原库）。")
    p.add_argument("--out", default=os.path.join("evidence", "RealDbReplay"), help="证据输出根目录（仓库内相对路径）")
    p.add_argument("--view", choices=("machine", "operator"), default="machine", help="甘特视图")
    p.add_argument("--min-batches", type=int, default=20, help="尽量选取的最小批次数（达到 op_limit 可提前停止）")
    p.add_argument("--max-batches", type=int, default=50, help="最多选取批次数")
    p.add_argument("--op-limit", type=int, default=2500, help="工序总量上限（用于控制耗时）")
    p.add_argument("--start-dt", default=None, help="排产开始时间（默认：明天 08:00:00）")
    args = p.parse_args(argv)

    repo_root = _find_repo_root()
    src_db = repo_root / "db" / "aps.db"
    if not src_db.exists():
        raise FileNotFoundError(f"找不到真实库：{src_db.as_posix()}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = repo_root / str(args.out) / ts
    _ensure_dir(out_dir)

    # 1) 一致性复制到 evidence（不污染原库）
    dst_db = out_dir / "aps_copy.db"
    try:
        _sqlite_backup_copy(src_db, dst_db)
    except Exception:
        # 兜底：文件复制（极端情况下 backup API 可能被锁影响）
        shutil.copy2(str(src_db), str(dst_db))
        for suf in ("-wal", "-shm", "-journal"):
            sp = Path(str(src_db) + suf)
            if sp.exists():
                shutil.copy2(str(sp), str(Path(str(dst_db) + suf)))

    # 2) 隔离运行目录（避免污染仓库根 logs/backups/templates_excel）
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(dst_db)
    os.environ["APS_LOG_DIR"] = str(out_dir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(out_dir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(out_dir / "templates_excel")

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # 注意：app.py 模块级会创建 app，因此必须在设置 env 之后再导入
    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()

    start_dt = str(args.start_dt).strip() if args.start_dt is not None else _fmt_dt(_tomorrow_8am())
    result = _run_replay(
        app=app,
        db_path=dst_db,
        out_dir=out_dir,
        view=str(args.view),
        min_batches=int(args.min_batches),
        max_batches=int(args.max_batches),
        op_limit=int(args.op_limit),
        start_dt=start_dt,
    )

    # 3) 写 summary（面向人工快速判定）
    sch = result.get("schedule") or {}
    picked = result.get("picked") or {}
    rs = (sch.get("result_summary") or {}) if isinstance(sch.get("result_summary"), dict) else {}
    counts = (rs.get("counts") or {}) if isinstance(rs.get("counts"), dict) else {}
    overdue = (rs.get("overdue_batches") or {}) if isinstance(rs.get("overdue_batches"), dict) else {}
    algo = (rs.get("algo") or {}) if isinstance(rs.get("algo"), dict) else {}
    metrics = (algo.get("metrics") or {}) if isinstance(algo.get("metrics"), dict) else {}

    lines: List[str] = []
    lines.append("# 真实库回放抽检摘要")
    lines.append("")
    lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 源库：`{src_db.as_posix()}`")
    lines.append(f"- 副本：`{dst_db.as_posix()}`")
    lines.append(f"- out_dir：`{out_dir.as_posix()}`")
    lines.append("")
    lines.append("## 批次选择")
    lines.append("")
    lines.append(f"- statuses：{picked.get('statuses')}")
    lines.append(f"- batch_count：{picked.get('batch_count')}")
    lines.append(f"- total_ops（预估）：{picked.get('total_ops')}")
    lines.append(f"- candidates_examined：{picked.get('candidates_examined')}")
    lines.append("")
    lines.append("## 排产结果")
    lines.append("")
    lines.append(f"- start_dt：`{sch.get('start_dt')}`")
    lines.append(f"- version：`{sch.get('version')}`")
    lines.append(f"- week_start：`{sch.get('week_start')}`")
    lines.append(f"- route_time_cost_s：`{sch.get('route_time_cost_s')}`")
    lines.append(f"- result_status：`{sch.get('result_status')}`")
    lines.append(f"- ops：{counts.get('scheduled_ops')}/{counts.get('op_count')} failed={counts.get('failed_ops')}")
    lines.append(f"- overdue_count：{overdue.get('count')}")
    if algo:
        lines.append(
            f"- algo：mode={algo.get('mode')} objective={algo.get('objective')} budget_s={algo.get('time_budget_seconds')}"
        )
    if metrics:
        lines.append(
            "- metrics："
            + " ".join(
                [
                    f"{k}={metrics.get(k)}"
                    for k in (
                        "overdue_count",
                        "total_tardiness_hours",
                        "makespan_hours",
                        "machine_util_avg",
                        "operator_util_avg",
                        "machine_load_cv",
                        "operator_load_cv",
                    )
                ]
            )
        )
    lines.append("")
    lines.append("## 接口可用性抽检")
    lines.append("")
    for r in result.get("reports") or []:
        lines.append(f"- {r.get('name')}: {r.get('status_code')} ({r.get('url')})")
    lines.append("")
    lines.append("## 产物")
    lines.append("")
    lines.append(f"- `schedule_history_v{sch.get('version')}.json`")
    lines.append(f"- `gantt_{args.view}_v{sch.get('version')}.json`")
    lines.append(f"- `week_plan_v{sch.get('version')}.xlsx`")
    lines.append("")

    _write_text(out_dir / "summary.md", "\n".join(lines) + "\n")
    _write_text(out_dir / "result.json", json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")

    print(str(out_dir / "summary.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

