"""回归测试：/system/logs/delete 不应把 log_id=0/-1 夹逼成 1 而误删 OperationLogs.id=1；/system/logs/delete-batch 混入非法编号时应整批拒绝并提示「日志编号不合法」，不偷删合法 id；合法 log_id=1 仍能正常删除。"""

from __future__ import annotations

from core.infrastructure.database import get_connection


def test_system_logs_delete_no_clamp(db_env) -> None:
    import importlib

    # 插入 2 条操作日志，确保存在 id=1（seed 必须先于 create_app：空库 seed 落 id=1/2，
    # app 启动写的 plugins-load 日志落 id>=3，不挤占被测的 id=1/2）
    conn = get_connection(db_env)
    try:
        cur1 = conn.execute(
            """
            INSERT INTO OperationLogs (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("INFO", "system", "seed", "operation_log", "1", "regression", None, None, None),
        )
        cur2 = conn.execute(
            """
            INSERT INTO OperationLogs (log_level, module, action, target_type, target_id, operator, detail, error_code, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("INFO", "system", "seed", "operation_log", "2", "regression", None, None, None),
        )
        conn.commit()
        id1 = int(cur1.lastrowid or 0)
        id2 = int(cur2.lastrowid or 0)
        if id1 != 1:
            raise RuntimeError(f"前置条件失败：期望第一条 OperationLogs.id=1，实际 id={id1}")
        if id2 != 2:
            raise RuntimeError(f"前置条件失败：期望第二条 OperationLogs.id=2，实际 id={id2}")
    finally:
        conn.close()

    client = importlib.import_module("app").create_app().test_client()

    # log_id=0/负数 不应夹逼为 1（不应误删 id=1）
    r0 = client.post("/system/logs/delete", data={"log_id": "0"}, follow_redirects=True)
    if r0.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=0 返回 {r0.status_code}，期望 200")
    rn = client.post("/system/logs/delete", data={"log_id": "-1"}, follow_redirects=True)
    if rn.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=-1 返回 {rn.status_code}，期望 200")

    conn = get_connection(db_env)
    try:
        c1 = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE id=1").fetchone()[0])
        if c1 != 1:
            raise RuntimeError("log_id=0/-1 不应删除 OperationLogs.id=1（但查询不到 id=1）")
    finally:
        conn.close()

    # 批量删除混入非法编号时应整批拒绝，不应悄悄只删除合法 id=1。
    rb = client.post(
        "/system/logs/delete-batch",
        data={"log_ids": ["1", "abc", "0", "-1", "1000000000001"]},
        follow_redirects=True,
    )
    if rb.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete-batch 混入非法编号返回 {rb.status_code}，期望 200")
    if "日志编号不合法" not in rb.get_data(as_text=True):
        raise RuntimeError("批量删除混入非法编号时，应向用户提示日志编号不合法")

    conn = get_connection(db_env)
    try:
        c1 = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE id=1").fetchone()[0])
        if c1 != 1:
            raise RuntimeError("批量删除混入非法编号时不应删除 OperationLogs.id=1（但查询不到 id=1）")
    finally:
        conn.close()

    # log_id=1 应能正常删除
    r1 = client.post("/system/logs/delete", data={"log_id": "1"}, follow_redirects=True)
    if r1.status_code != 200:
        raise RuntimeError(f"POST /system/logs/delete log_id=1 返回 {r1.status_code}，期望 200")

    conn = get_connection(db_env)
    try:
        c1 = int(conn.execute("SELECT COUNT(1) FROM OperationLogs WHERE id=1").fetchone()[0])
        if c1 != 0:
            raise RuntimeError("log_id=1 删除后仍能查询到 OperationLogs.id=1")
    finally:
        conn.close()
