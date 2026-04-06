import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta


def find_repo_root():
    """
    约定：仓库根目录包含 app.py 与 schema.sql。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def write_report(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _assert_status(lines, name: str, resp, expect_code: int = 200):
    lines.append(f"- {name}：{resp.status_code}")
    if resp.status_code != expect_code:
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}")


def _parse_detail_json(detail: str) -> dict:
    try:
        return json.loads(detail) if detail else {}
    except Exception as e:
        raise RuntimeError(f"OperationLogs.detail 不是有效 JSON：{e} detail={detail!r}")


def main():
    t0 = time.time()
    lines = []
    lines.append("# Phase9（系统管理：备份/日志/历史）冒烟测试报告")
    lines.append("")
    lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Python：{sys.version.splitlines()[0]}")

    repo_root = find_repo_root()
    lines.append(f"- 项目根目录：`{repo_root}`")

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_phase9_")
    test_db = os.path.join(tmpdir, "aps_phase9_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    lines.append("")
    lines.append("## 0. 测试环境（隔离目录）")
    lines.append(f"- 临时目录：`{tmpdir}`")
    lines.append(f"- 测试 DB：`{test_db}`")
    lines.append(f"- 备份目录：`{test_backups}`")

    # 隔离：让 app.create_app() 读取测试 DB/目录
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    # 预置一条基础数据（用于“备份→删除→恢复”闭环验证）
    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP_BAK", "备份验证员", "active"))
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    import importlib

    app_mod = importlib.import_module("app")
    test_app = app_mod.create_app()
    client = test_app.test_client()

    lines.append("")
    lines.append("## 1. 页面可访问（系统管理三页）")
    _assert_status(lines, "GET /system/backup", client.get("/system/backup"), 200)
    _assert_status(lines, "GET /system/logs", client.get("/system/logs"), 200)
    _assert_status(lines, "GET /system/history", client.get("/system/history"), 200)

    lines.append("")
    lines.append("## 2. 备份文件：创建/删除/批量删除/恢复闭环（含 before_restore）")

    # 2.1 手动备份（页面动作）
    resp = client.post("/system/backup/create", data={}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/create (follow redirects)", resp, 200)

    # 找到最新备份文件（manual）
    backups = sorted([f for f in os.listdir(test_backups) if f.startswith("aps_backup_") and f.endswith(".db")], reverse=True)
    if not backups:
        raise RuntimeError("未生成备份文件（backups 目录为空）")
    manual_backup = backups[0]
    lines.append(f"- 最新备份文件：{manual_backup}")

    # 2.2 验证操作日志（backup）
    conn = get_connection(test_db)
    try:
        row = conn.execute(
            "SELECT id, detail FROM OperationLogs WHERE module='system' AND action='backup' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("未写入备份操作日志（OperationLogs module=system action=backup）")
        detail = _parse_detail_json(row["detail"])
        if detail.get("filename") != manual_backup:
            # 允许时间上有并发导致 filename 不一致，但至少应有 filename
            if not detail.get("filename"):
                raise RuntimeError(f"备份操作日志 detail.filename 缺失：{detail}")
        lines.append(f"- 备份操作日志：通过（log_id={row['id']}）")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 2.2 备份删除（单个）
    time.sleep(1.1)
    resp = client.post("/system/backup/create", data={}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/create#2 (follow redirects)", resp, 200)
    backups2 = sorted([f for f in os.listdir(test_backups) if f.startswith("aps_backup_") and f.endswith(".db")], reverse=True)
    if len(backups2) < 2:
        raise RuntimeError("第二个备份文件未生成（期望 >= 2 个）")
    to_delete_one = backups2[0] if backups2[0] != manual_backup else backups2[1]
    resp = client.post("/system/backup/delete", data={"filename": to_delete_one}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/delete (follow redirects)", resp, 200)
    if os.path.exists(os.path.join(test_backups, to_delete_one)):
        raise RuntimeError("备份删除失败：文件仍存在")
    lines.append(f"- 备份删除：通过（{to_delete_one} 已删除）")

    # 2.3 备份批量删除
    time.sleep(1.1)
    resp = client.post("/system/backup/create", data={}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/create#3 (follow redirects)", resp, 200)
    backups3 = sorted([f for f in os.listdir(test_backups) if f.startswith("aps_backup_") and f.endswith(".db")], reverse=True)
    if not backups3:
        raise RuntimeError("未找到第三个备份文件用于批量删除")
    to_delete_batch = backups3[0]
    if to_delete_batch == manual_backup:
        if len(backups3) < 2:
            raise RuntimeError("批量删除测试缺少可删除备份文件")
        to_delete_batch = backups3[1]
    resp = client.post("/system/backup/delete-batch", data={"filenames": [to_delete_batch]}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/delete-batch (follow redirects)", resp, 200)
    if os.path.exists(os.path.join(test_backups, to_delete_batch)):
        raise RuntimeError("备份批量删除失败：文件仍存在")
    lines.append(f"- 备份批量删除：通过（{to_delete_batch} 已删除）")

    # 2.3 删除数据（模拟误操作/回滚需求）
    conn = get_connection(test_db)
    try:
        conn.execute("DELETE FROM Operators WHERE operator_id='OP_BAK'")
        conn.commit()
        exists = conn.execute("SELECT 1 FROM Operators WHERE operator_id='OP_BAK'").fetchone()
        if exists is not None:
            raise RuntimeError("删除数据失败：OP_BAK 仍存在")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    lines.append("- 已删除 OP_BAK（用于验证恢复）")

    # 2.4 恢复（页面动作）
    resp = client.post("/system/backup/restore", data={"filename": manual_backup}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/restore (follow redirects)", resp, 200)

    # 2.5 验证数据已恢复
    conn = get_connection(test_db)
    try:
        exists = conn.execute("SELECT 1 FROM Operators WHERE operator_id='OP_BAK'").fetchone()
        if exists is None:
            raise RuntimeError("恢复后数据未回归：OP_BAK 不存在")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    lines.append("- 恢复校验：通过（OP_BAK 已回归）")

    # 2.6 验证 before_restore 备份生成
    before_restore = [f for f in os.listdir(test_backups) if f.startswith("aps_backup_") and "_before_restore" in f and f.endswith(".db")]
    if not before_restore:
        raise RuntimeError("未发现 before_restore 备份文件（期望 restore 前自动备份）")
    lines.append(f"- before_restore 备份：通过（{len(before_restore)} 个）")

    # 2.7 验证 restore 操作日志
    conn = get_connection(test_db)
    try:
        row = conn.execute(
            "SELECT id, detail FROM OperationLogs WHERE module='system' AND action='restore' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("未写入恢复操作日志（OperationLogs module=system action=restore）")
        detail = _parse_detail_json(row["detail"])
        if detail.get("filename") != manual_backup:
            if not detail.get("filename"):
                raise RuntimeError(f"恢复操作日志 detail.filename 缺失：{detail}")
        lines.append(f"- 恢复操作日志：通过（log_id={row['id']}）")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    lines.append("")
    lines.append("## 3. 清理过期备份（cleanup）")
    # 3.1 构造一个“过期”备份文件（仅需匹配前缀与 mtime）
    old_name = "aps_backup_20000101_000000_manual.db"
    old_path = os.path.join(test_backups, old_name)
    with open(old_path, "wb") as f:
        f.write(b"")  # 不需要是有效 sqlite 文件，cleanup 只按文件名与 mtime 删除
    # 设置 mtime 为 30 天前（默认 keep_days=7 一定会被删）
    old_mtime = time.time() - 30 * 24 * 3600
    os.utime(old_path, (old_mtime, old_mtime))

    resp = client.post("/system/backup/cleanup", data={}, follow_redirects=True)
    _assert_status(lines, "POST /system/backup/cleanup (follow redirects)", resp, 200)
    if os.path.exists(old_path):
        raise RuntimeError("清理过期备份失败：旧备份文件仍存在")
    lines.append("- 清理过期备份：通过（旧文件已删除）")

    # 3.2 验证 cleanup 操作日志
    conn = get_connection(test_db)
    try:
        row = conn.execute(
            "SELECT id, detail FROM OperationLogs WHERE module='system' AND action='cleanup' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("未写入清理操作日志（OperationLogs module=system action=cleanup）")
        _ = _parse_detail_json(row["detail"])
        lines.append(f"- 清理操作日志：通过（log_id={row['id']}）")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    lines.append("")
    lines.append("## 4. 日志筛选（按时间）与排产历史展示 + 日志删除/批量删除")
    # 4.1 插入一条很早的日志，用于时间筛选验证
    conn = get_connection(test_db)
    try:
        conn.execute(
            """
            INSERT INTO OperationLogs (log_time, log_level, module, action, detail)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2000-01-01 00:00:00", "INFO", "system", "backup", json.dumps({"note": "old"}, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 4.2 直接调用仓库查询验证（避免解析 HTML）
    from data.repositories import OperationLogRepository

    conn = get_connection(test_db)
    try:
        repo = OperationLogRepository(conn)
        rows = repo.list_recent(limit=200, module="system", action="backup", start_time="2020-01-01 00:00:00")
        if any((r.log_time or "").startswith("2000-01-01") for r in rows):
            raise RuntimeError("按 start_time 过滤失败：返回结果包含 2000 年的旧日志")
        lines.append("- OperationLogs 按时间过滤：通过（start_time 生效）")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # 4.3 插入一条排产历史记录，用于页面回看
    conn = get_connection(test_db)
    try:
        summary = {"strategy_params": {"priority_weight": 0.4, "due_weight": 0.5, "ready_weight": 0.1}, "overdue_batches": {"count": 0, "items": []}}
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "priority_first", 1, 1, "success", json.dumps(summary, ensure_ascii=False), "smoke"),
        )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    _assert_status(lines, "GET /system/history?version=1", client.get("/system/history?version=1"), 200)

    # 4.4 删除单条日志（页面动作）
    conn = get_connection(test_db)
    try:
        row = conn.execute(
            "SELECT id FROM OperationLogs WHERE module='system' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            raise RuntimeError("未找到可删除的操作日志记录（module=system）")
        del_id = int(row["id"])
    finally:
        try:
            conn.close()
        except Exception:
            pass

    resp = client.post("/system/logs/delete", data={"log_id": str(del_id)}, follow_redirects=True)
    _assert_status(lines, "POST /system/logs/delete (follow redirects)", resp, 200)
    conn = get_connection(test_db)
    try:
        still = conn.execute("SELECT 1 FROM OperationLogs WHERE id = ?", (del_id,)).fetchone()
        if still is not None:
            raise RuntimeError("日志删除失败：记录仍存在")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    lines.append(f"- 日志删除：通过（id={del_id} 已删除）")

    # 4.5 批量删除日志（页面动作）
    conn = get_connection(test_db)
    try:
        rows = conn.execute("SELECT id FROM OperationLogs WHERE module='system' ORDER BY id DESC LIMIT 3").fetchall()
        ids = [int(r["id"]) for r in rows if r and r["id"] is not None]
        ids = ids[:2] if len(ids) >= 2 else ids[:1]
        if not ids:
            raise RuntimeError("批量删除日志测试：找不到可删除日志")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    resp = client.post("/system/logs/delete-batch", data={"log_ids": [str(x) for x in ids]}, follow_redirects=True)
    _assert_status(lines, "POST /system/logs/delete-batch (follow redirects)", resp, 200)
    conn = get_connection(test_db)
    try:
        still = conn.execute(
            f"SELECT COUNT(1) FROM OperationLogs WHERE id IN ({','.join(['?']*len(ids))})",
            tuple(ids),
        ).fetchone()[0]
        if int(still) != 0:
            raise RuntimeError("日志批量删除失败：仍有记录存在")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    lines.append(f"- 日志批量删除：通过（ids={ids} 已删除）")

    lines.append("")
    lines.append("## 5. 自动任务（按请求触发）：自动备份 / 自动清理备份 / 自动清理日志")

    from core.services.system import SystemMaintenanceService

    # 5.1 配置自动备份 + 自动清理备份（不 follow_redirects，避免立即触发）
    resp = client.post(
        "/system/backup/settings",
        data={
            "auto_backup_enabled": "on",
            "auto_backup_interval_minutes": "1",
            "auto_backup_cleanup_enabled": "on",
            "auto_backup_keep_days": "7",
            "auto_backup_cleanup_interval_minutes": "1",
        },
        follow_redirects=False,
    )
    _assert_status(lines, "POST /system/backup/settings", resp, 302)

    # 构造一个“过期”备份文件，等待自动清理删除
    old_name2 = "aps_backup_20000102_000000_auto.db"
    old_path2 = os.path.join(test_backups, old_name2)
    with open(old_path2, "wb") as f:
        f.write(b"")
    old_mtime2 = time.time() - 30 * 24 * 3600
    os.utime(old_path2, (old_mtime2, old_mtime2))

    # 系统维护带节流：等待超过阈值再触发一次请求
    time.sleep(SystemMaintenanceService.CHECK_THROTTLE_SECONDS + 1)
    _assert_status(lines, "GET /system/backup (trigger maintenance)", client.get("/system/backup"), 200)

    # 5.2 验证自动备份生成（*_auto.db）
    auto_backups = [f for f in os.listdir(test_backups) if f.startswith("aps_backup_") and "_auto.db" in f]
    if not auto_backups:
        raise RuntimeError("自动备份未触发：未发现 *_auto.db")
    lines.append(f"- 自动备份：通过（{len(auto_backups)} 个，示例：{auto_backups[0]}）")

    # 5.3 验证自动清理备份生效（old_name2 被删除）
    if os.path.exists(old_path2):
        raise RuntimeError("自动清理备份未生效：过期备份仍存在")
    lines.append("- 自动清理备份：通过（过期文件已删除）")

    # 5.4 准备足够多的日志并开启自动清理（保证总量 > MIN_KEEP_LOGS 才会删）
    conn = get_connection(test_db)
    try:
        for i in range(20):
            conn.execute(
                "INSERT INTO OperationLogs (log_time, log_level, module, action, detail) VALUES (?, ?, ?, ?, ?)",
                (
                    f"2000-01-01 00:00:{i:02d}",
                    "INFO",
                    "system",
                    "backup",
                    json.dumps({"note": "old", "i": i}, ensure_ascii=False),
                ),
            )
        for i in range(60):
            conn.execute(
                "INSERT INTO OperationLogs (log_level, module, action, detail) VALUES (?, ?, ?, ?)",
                ("INFO", "system", "backup", json.dumps({"note": "new", "i": i}, ensure_ascii=False)),
            )
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    resp = client.post(
        "/system/logs/settings",
        data={"auto_log_cleanup_enabled": "on", "auto_log_cleanup_keep_days": "1", "auto_log_cleanup_interval_minutes": "1"},
        follow_redirects=False,
    )
    _assert_status(lines, "POST /system/logs/settings", resp, 302)

    time.sleep(SystemMaintenanceService.CHECK_THROTTLE_SECONDS + 1)
    _assert_status(lines, "GET /system/logs (trigger maintenance)", client.get("/system/logs"), 200)

    conn = get_connection(test_db)
    try:
        old_cnt = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE log_time LIKE '2000-%'").fetchone()[0])
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if old_cnt >= 20:
        raise RuntimeError("日志自动清理未生效：2000 年旧日志数量未减少")
    lines.append(f"- 自动清理日志：通过（2000 年旧日志剩余 {old_cnt} 条 < 20）")

    lines.append("")
    lines.append("## 结论")
    lines.append("- 通过：Phase9（系统管理：备份/日志/历史）冒烟测试通过。")
    lines.append(f"- 总耗时：{int((time.time() - t0) * 1000)} ms")

    report_path = os.path.join(repo_root, "evidence", "Phase9", "smoke_phase9_report.md")
    write_report(report_path, lines)
    print("OK")
    print(report_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        repo_root = None
        try:
            repo_root = find_repo_root()
        except Exception:
            pass

        lines = []
        lines.append("# Phase9（系统管理：备份/日志/历史）冒烟测试报告（失败）")
        lines.append("")
        lines.append(f"- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 错误：{e}")
        lines.append("")
        lines.append("## Traceback")
        lines.append("```")
        lines.append(traceback.format_exc())
        lines.append("```")

        if repo_root:
            report_path = os.path.join(repo_root, "evidence", "Phase9", "smoke_phase9_report.md")
            write_report(report_path, lines)
            print("FAIL")
            print(report_path)
        raise

